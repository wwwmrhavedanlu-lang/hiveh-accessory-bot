import os
import logging
import asyncio
from flask import Flask
from threading import Thread
from supabase import create_client, Client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ----------------- تنظیمات لاگ و محیط -----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
PORT = int(os.getenv("PORT", 10000))

ADMIN_ID = 8521643361  # آیدی عددی ادمین

# اتصال به Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------- سرور فلاسک برای رندر -----------------
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Hiveh Bot is running!", 200

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ----------------- منوی اصلی مشتریان -----------------
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🛍 مشاهده محصولات", callback_data="user_view_products")],
        [InlineKeyboardButton("🛒 ثبت سفارش", callback_data="user_order")],
        [InlineKeyboardButton("📖 معرفی فروشگاه", callback_data="user_about")],
        [InlineKeyboardButton("📞 راه‌های ارتباطی با پشتیبانی", callback_data="user_support")],
        [InlineKeyboardButton("❌ انصراف", callback_data="user_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ----------------- منوی ادمین -----------------
def get_admin_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ افزودن محصول", callback_data="admin_add_product")],
        [InlineKeyboardButton("✏️ ویرایش محصول", callback_data="admin_edit_product_start")],
        [InlineKeyboardButton("❌ حذف محصول", callback_data="admin_delete_product_start")],
        [InlineKeyboardButton("✏️ ویرایش اطلاعات فروشگاه/پشتیبانی", callback_data="admin_edit_info_start")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="user_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# دستور شروع (Start)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name or "دوست"
    
    welcome_text = (
        f"سلام {user_name} عزیز 🙌\n"
        f"به فروشگاه آنلاین بدلیجات و اکسسوری هیوه خوش آمدید! ☺️\n"
        f"برای شروع یکی از گزینه‌های زیر رو انتخاب کنید 🙏"
    )
    
    if user.id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("🛍 مشاهده محصولات", callback_data="user_view_products")],
            [InlineKeyboardButton("🛒 ثبت سفارش", callback_data="user_order")],
            [InlineKeyboardButton("📖 معرفی فروشگاه", callback_data="user_about")],
            [InlineKeyboardButton("📞 راه‌های ارتباطی با پشتیبانی", callback_data="user_support")],
            [InlineKeyboardButton("⚙️ پنل مدیریت ادمین", callback_data="admin_panel")],
            [InlineKeyboardButton("❌ انصراف", callback_data="user_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        reply_markup = get_main_menu_keyboard()

    context.user_data.clear() # پاکسازی وضعیت‌های قبلی
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup)

# مدیریت کلیک دکمه‌ها
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "user_view_products":
        try:
            response = supabase.table("products").select("*").execute()
            products = response.data
            
            if not products:
                await query.message.edit_text(
                    "📦 در حال حاضر محصولی در فروشگاه ثبت نشده است.",
                    reply_markup=get_main_menu_keyboard()
                )
                return

            for p in products:
                caption = (
                    f"🔖 کد محصول: {p.get('code')}\n"
                    f"💎 نام: {p.get('name')}\n"
                    f"💰 قیمت: {p.get('price')}\n"
                    f"📝 توضیحات: {p.get('description')}"
                )
                image_url = p.get('image_url')
                if image_url:
                    await query.message.reply_photo(photo=image_url, caption=caption)
                else:
                    await query.message.reply_text(caption)
            
            await query.message.reply_text("✨ برای انتخاب و بررسی بیشتر از منوی زیر استفاده کنید:", reply_markup=get_main_menu_keyboard())
        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            await query.message.edit_text("خطا در دریافت لیست محصولات از دیتابیس.", reply_markup=get_main_menu_keyboard())

    elif data == "user_order":
        order_text = (
            "🛒 **ثبت سفارش:**\n\n"
            "برای ثبت سفارش، لطفاً کد محصول مورد نظر خود را به همراه مشخصات و آدرس به پشتیبانی ارسال کنید:\n"
            "📞 پشتیبانی: @HivahSupport"
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="user_back_to_main")]]
        await query.message.edit_text(order_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "user_about":
        about_text = (
            "✨ به «هیوه» خوش اومدی ✨\n\n"
            "اینجا قراره دنیای کوچیک و جذابی از بدلیجات و اکسسوری‌های خاص و شیک رو تجربه کنی 💎🤍\n\n"
            "ما در «هیوه» تلاش می‌کنیم مدل‌هایی رو انتخاب کنیم که هم برای استفاده روزمره جذاب باشن، هم برای تکمیل استایل و هدیه دادن انتخابی خاص و دوست‌داشتنی باشن 🎁✨\n\n"
            "💍 بدلیجات و زیورآلات شیک\n"
            "👜 اکسسوری‌های جذاب و خاص\n"
            "🎀 مناسب برای سلیقه‌های مختلف\n"
            "📦 ارسال به سراسر کشور\n\n"
            "اگه دنبال یه اکسسوری خاص برای خودت یا یه هدیه قشنگ برای کسی که دوستش داری هستی، خوشحال می‌شیم «هیوه» رو ببینی 🤍\n\n"
            "هیوه؛ جزئیات کوچیک، تغییر بزرگ در استایل ✨"
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="user_back_to_main")]]
        await query.message.edit_text(about_text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "user_support":
        support_text = (
            "📞 **راه‌های ارتباطی با پشتیبانی هیوه:**\n\n"
            "👤 آیدی تلگرام: @HivahSupport\n"
            "📱 شماره تماس: 09384336991\n"
            "🔗 لینک کانال: https://t.me/Hiveh_Accessory\n\n"
            "پاسخگوی سوالات و سفارشات شما هستیم 🤍"
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="user_back_to_main")]]
        await query.message.edit_text(support_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "user_cancel" or data == "user_back_to_main":
        await start(update, context)

    elif data == "admin_panel":
        if user_id != ADMIN_ID:
            await query.answer("شما دسترسی به پنل مدیریت ندارید!", show_alert=True)
            return
        context.user_data.clear()
        await query.message.edit_text("⚙️️ **پنل مدیریت ادمین هیوه**\n\nیک گزینه را انتخاب کنید:", reply_markup=get_admin_menu_keyboard(), parse_mode="Markdown")

    # ---- افزودن محصول مرحله‌به‌مرحله ----
    elif data == "admin_add_product":
        if user_id != ADMIN_ID:
            return
        context.user_data.clear()
        context.user_data['state'] = 'add_code'
        keyboard = [[InlineKeyboardButton("🔙 انصراف", callback_data="admin_panel")]]
        await query.message.edit_text("➕ **مرحله ۱ از ۵:**\nلطفاً **کد محصول** را وارد کنید:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # ---- حذف محصول با تاییدیه ----
    elif data == "admin_delete_product_start":
        if user_id != ADMIN_ID:
            return
        context.user_data.clear()
        context.user_data['state'] = 'delete_get_code'
        keyboard = [[InlineKeyboardButton("🔙 انصراف", callback_data="admin_panel")]]
        await query.message.edit_text("❌ **حذف محصول**\n\nلطفاً **کد محصولی** که می‌خواهید حذف کنید را وارد نمایید:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("confirm_del_"):
        if user_id != ADMIN_ID:
            return
        p_code = data.replace("confirm_del_", "")
        try:
            supabase.table("products").delete().eq("code", p_code).execute()
            await query.message.edit_text("✅ محصول با موفقیت از دیتابیس حذف شد!", reply_markup=get_admin_menu_keyboard())
        except Exception as e:
            logger.error(e)
            await query.message.edit_text("❌ خطا در حذف محصول.", reply_markup=get_admin_menu_keyboard())

    # ---- ویرایش محصول مرحله‌به‌مرحله ----
    elif data == "admin_edit_product_start":
        if user_id != ADMIN_ID:
            return
        context.user_data.clear()
        context.user_data['state'] = 'edit_get_code'
        keyboard = [[InlineKeyboardButton("🔙 انصراف", callback_data="admin_panel")]]
        await query.message.edit_text("✏️ **ویرایش محصول**\n\nلطفاً **کد محصولی** که قصد ویرایش آن را دارید وارد کنید:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # ---- ویرایش اطلاعات فروشگاه/پشتیبانی ----
    elif data == "admin_edit_info_start":
        if user_id != ADMIN_ID:
            return
        context.user_data.clear()
        context.user_data['state'] = 'edit_info_text'
        keyboard = [[InlineKeyboardButton("🔙 انصراف", callback_data="admin_panel")]]
        await query.message.edit_text("✏️ **ویرایش اطلاعات فروشگاه/پشتیبانی**\n\nلطفاً متن جدید معرفی فروشگاه یا راه‌های ارتباطی را بفرستید:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# مدیریت پیام‌ها و مراحل قدم‌به‌قدم ادمین
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    state = context.user_data.get('state')

    # 1. افزودن محصول
    if state == 'add_code':
        context.user_data['new_code'] = update.message.text.strip()
        context.user_data['state'] = 'add_name'
        await update.message.reply_text("➕ **مرحله ۲ از ۵:**\nحالا **نام محصول** را وارد کنید:")
    
    elif state == 'add_name':
        context.user_data['new_name'] = update.message.text.strip()
        context.user_data['state'] = 'add_price'
        await update.message.reply_text("➕ **مرحله ۳ از ۵:**\nحالا **قیمت محصول** را وارد کنید:")

    elif state == 'add_price':
        context.user_data['new_price'] = update.message.text.strip()
        context.user_data['state'] = 'add_desc'
        await update.message.reply_text("➕ **مرحله ۴ از ۵:**\nحالا **توضیحات محصول** را وارد کنید:")

    elif state == 'add_desc':
        context.user_data['new_desc'] = update.message.text.strip()
        context.user_data['state'] = 'add_photo'
        await update.message.reply_text("➕ **مرحله ۵ از ۵ (پایانی):**\nلطفاً **تصویر (عکس) محصول** را مستقیماً ارسال کنید:")

    elif state == 'add_photo':
        if not update.message.photo:
            await update.message.reply_text("❌ لطفاً یک عکس ارسال کنید.")
            return
        
        photo_file = await update.message.photo[-1].get_file()
        photo_url = photo_file.file_path

        p_data = {
            'code': context.user_data.get('new_code'),
            'name': context.user_data.get('new_name'),
            'price': context.user_data.get('new_price'),
            'description': context.user_data.get('new_desc'),
            'image_url': photo_url
        }

        try:
            supabase.table("products").insert(p_data).execute()
            context.user_data.clear()
            await update.message.reply_text("✅ محصول جدید با تصویر و مشخصات کامل ثبت شد!", reply_markup=get_admin_menu_keyboard())
        except Exception as e:
            logger.error(e)
            await update.message.reply_text(f"❌ خطا در ثبت محصول در دیتابیس: {e}", reply_markup=get_admin_menu_keyboard())

    # 2. حذف محصول (گرفتن کد و تاییدیه)
    elif state == 'delete_get_code':
        p_code = update.message.text.strip()
        try:
            res = supabase.table("products").select("*").eq("code", p_code).execute()
            if not res.data:
                await update.message.reply_text("❌ محصولی با این کد پیدا نشد. دوباره تلاش کنید یا به پنل برگردید.")
                return
            
            p_name = res.data[0].get('name')
            context.user_data.clear()
            keyboard = [
                [InlineKeyboardButton(f"✅ بله، حذف شود ({p_name})", callback_data=f"confirm_del_{p_code}")],
                [InlineKeyboardButton("❌ خیر، انصراف", callback_data="admin_panel")]
            ]
            await update.message.reply_text(
                f"⚠️ **اختار اطمینان از حذف**\n\nآیا از حذف محصول «{p_name}» با کد {p_code} اطمینان دارید؟",
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(e)
            await update.message.reply_text("خطا در بررسی کد محصول.")

    # 3. ویرایش محصول
    elif state == 'edit_get_code':
        p_code = update.message.text.strip()
        res = supabase.table("products").select("*").eq("code", p_code).execute()
        if not res.data:
            await update.message.reply_text("❌ محصولی با این کد یافت نشد. کد دیگری وارد کنید:")
            return
        
        context.user_data['edit_code'] = p_code
        context.user_data['state'] = 'edit_name'
        await update.message.reply_text(f"✏️ محصول یافت شد ({res.data[0].get('name')}).\nحالا **نام جدید محصول** را وارد کنید:")

    elif state == 'edit_name':
        context.user_data['edit_name'] = update.message.text.strip()
        context.user_data['state'] = 'edit_price'
        await update.message.reply_text("حالا **قیمت جدید** را وارد کنید:")

    elif state == 'edit_price':
        context.user_data['edit_price'] = update.message.text.strip()
        context.user_data['state'] = 'edit_desc'
        await update.message.reply_text("حالا **توضیحات جدید** را وارد کنید:")

    elif state == 'edit_desc':
        context.user_data['edit_desc'] = update.message.text.strip()
        context.user_data['state'] = 'edit_photo'
        await update.message.reply_text("حالا **تصویر جدید محصول** را ارسال کنید:")

    elif state == 'edit_photo':
        if not update.message.photo:
            await update.message.reply_text("❌ لطفاً یک عکس معتبر بفرستید.")
            return
        
        photo_file = await update.message.photo[-1].get_file()
        photo_url = photo_file.file_path
        p_code = context.user_data.get('edit_code')

        updated_data = {
            'name': context.user_data.get('edit_name'),
            'price': context.user_data.get('edit_price'),
            'description': context.user_data.get('edit_desc'),
            'image_url': photo_url
        }

        try:
            supabase.table("products").update(updated_data).eq("code", p_code).execute()
            context.user_data.clear()
            await update.message.reply_text("✅ اطلاعات و تصویر محصول با موفقیت ویرایش و در دیتابیس آپدیت شد!", reply_markup=get_admin_menu_keyboard())
        except Exception as e:
            logger.error(e)
            await update.message.reply_text(f"❌ خطا در ویرایش محصول: {e}", reply_markup=get_admin_menu_keyboard())

    # 4. ویرایش اطلاعات فروشگاه یا پشتیبانی
    elif state == 'edit_info_text':
        new_text = update.message.text.strip()
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ اطلاعات جدید دریافت و ثبت شد:\n\n{new_text}\n\n(برای اعمال نهایی متن‌ها در بخش معرفی یا پشتیبانی می‌توانید آن را در کد نیز به‌روز کنید)",
            reply_markup=get_admin_menu_keyboard()
        )

# ----------------- اجرای اصلی ربات -----------------
def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO & ~filters.COMMAND, handle_message))

    logger.info("Bot is starting polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
