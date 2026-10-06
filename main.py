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
        [InlineKeyboardButton("🛍️️ مشاهده محصولات", callback_data="user_view_products")],
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
        [InlineKeyboardButton("📋 لیست و مدیریت محصولات", callback_data="admin_list_products")],
        [InlineKeyboardButton("✏️ ویرایش اطلاعات فروشگاه/پشتیبانی", callback_data="admin_edit_info")],
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
            [InlineKeyboardButton("🛍️️ مشاهده محصولات", callback_data="user_view_products")],
            [InlineKeyboardButton("🛒 ثبت سفارش", callback_data="user_order")],
            [InlineKeyboardButton("📖 معرفی فروشگاه", callback_data="user_about")],
            [InlineKeyboardButton("📞 راه‌های ارتباطی با پشتیبانی", callback_data="user_support")],
            [InlineKeyboardButton("⚙️ پنل مدیریت ادمین", callback_data="admin_panel")],
            [InlineKeyboardButton("❌ انصراف", callback_data="user_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        reply_markup = get_main_menu_keyboard()

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

            text = "✨ **لیست محصولات هیوه:**\n\n"
            for p in products:
                text += f"🔖 کد محصول: {p.get('code')}\n"
                text += f"💎 نام: {p.get('name')}\n"
                text += f"💰 قیمت: {p.get('price')}\n"
                text += f"📝 توضیحات: {p.get('description')}\n"
                text += "-------------------\n"
            
            await query.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
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
        await query.message.edit_text("⚙️ **پنل مدیریت ادمین هیوه**\n\nیک گزینه را انتخاب کنید:", reply_markup=get_admin_menu_keyboard(), parse_mode="Markdown")

    elif data == "admin_list_products":
        if user_id != ADMIN_ID:
            return
        try:
            response = supabase.table("products").select("*").execute()
            products = response.data
            
            if not products:
                keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل ادمین", callback_data="admin_panel")]]
                await query.message.edit_text("📦 هیچ محصولی برای مدیریت وجود ندارد.", reply_markup=InlineKeyboardMarkup(keyboard))
                return

            text = "📋 **مدیریت محصولات (برای حذف یا ویرایش):**\n\n"
            keyboard = []
            for p in products:
                p_code = p.get('code')
                p_name = p.get('name')
                text += f"کد: {p_code} | نام: {p_name}\n"
                keyboard.append([InlineKeyboardButton(f"❌ حذف {p_name} (کد: {p_code})", callback_data=f"admin_del_{p_code}")])
            
            keyboard.append([InlineKeyboardButton("🔙 بازگشت به پنل ادمین", callback_data="admin_panel")])
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        except Exception as e:
            logger.error(e)
            await query.message.edit_text("خطا در بارگذاری محصولات.", reply_markup=get_admin_menu_keyboard())

    elif data.startswith("admin_del_"):
        if user_id != ADMIN_ID:
            return
        p_code = data.replace("admin_del_", "")
        try:
            supabase.table("products").delete().eq("code", p_code).execute()
            await query.answer("محصول با موفقیت حذف شد!", show_alert=True)
            await button_handler(update, context)
        except Exception as e:
            logger.error(e)
            await query.answer("خطا در حذف محصول!", show_alert=True)

    elif data == "admin_add_product":
        if user_id != ADMIN_ID:
            return
        context.user_data['waiting_for_product'] = True
        add_instructions = (
            "➕ **افزودن محصول جدید**\n\n"
            "لطفاً اطلاعات محصول را دقیقاً به این صورت و در یک پیام بفرستید:\n\n"
            "کد: 101\n"
            "نام: دستبند نقره\n"
            "قیمت: ۲۵۰ هزار تومان\n"
            "توضیحات: استیل رنگ ثابت\n"
            "لینک عکس: https://...\n\n"
            "یا ارسال دستور /cancel برای انصراف."
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="admin_panel")]]
        await query.message.edit_text(add_instructions, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "admin_edit_info":
        if user_id != ADMIN_ID:
            return
        await query.message.edit_text(
            "✏ برای ویرایش اطلاعات فروشگاه یا پشتیبانی، می‌توانید متون را در کد بات به‌روزرسانی کنید.",
            reply_markup=get_admin_menu_keyboard()
        )

# دریافت پیام متنی ادمین برای ثبت محصول جدید
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID and context.user_data.get('waiting_for_product'):
        text = update.message.text
        try:
            lines = text.split('\n')
            p_data = {}
            for line in lines:
                if ":" in line:
                    key, val = line.split(":", 1)
                    key = key.strip()
                    val = val.strip()
                    if "کد" in key: p_data['code'] = val
                    elif "نام" in key: p_data['name'] = val
                    elif "قیمت" in key: p_data['price'] = val
                    elif "توضیحات" in key: p_data['description'] = val
                    elif "عکس" in key: p_data['image_url'] = val

            if 'code' in p_data and 'name' in p_data:
                supabase.table("products").insert(p_data).execute()
                context.user_data['waiting_for_product'] = False
                await update.message.reply_text("✅ محصول جدید با موفقیت در دیتابیس ثبت شد!", reply_markup=get_admin_menu_keyboard())
            else:
                await update.message.reply_text("❌ فرمت اطلاعات وارد شده اشتباه است. لطفاً طبق الگو دوباره ارسال کنید.")
        except Exception as e:
            logger.error(e)
            await update.message.reply_text(f"❌ خطا در ثبت محصول: {e}")

# ----------------- اجرای اصلی ربات با Event Loop صریح -----------------
def main():
    # استارت سرور فلاسک در ترد جداگانه
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # ساخت حلقه رویداد صریح برای رفع خطای پایتون ۳.۱۴
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is starting polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
