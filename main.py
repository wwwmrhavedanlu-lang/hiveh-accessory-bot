import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from supabase import create_client, Client

# تنظیمات لاگ‌گیری
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# اطلاعات اتصال به Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# آیدی عددی ادمین
ADMIN_CHAT_ID = 8521643361

# وضعیت‌های مکالمه (States) برای مراحل ثبت و ویرایش
(
    ADMIN_MENU,
    ADD_CODE,
    ADD_NAME,
    ADD_PRICE,
    ADD_DESC,
    ADD_PHOTO,
    EDIT_SELECT_CODE,
    EDIT_CHOICE,
    EDIT_NAME,
    EDIT_PRICE,
    EDIT_DESC,
    EDIT_PHOTO,
) = range(12)


# کیبوردهای کمکی
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📦 مشاهده محصولات", callback_data="user_view_products")],
        [InlineKeyboardButton("👤 پنل مدیریت", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ افزودن محصول جدید", callback_data="admin_add_product")],
        [InlineKeyboardButton("✏️ ویرایش محصول", callback_data="admin_edit_product")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


# استارت ربات
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = "سلام! به فروشگاه ما خوش آمدید. لطفاً از منوی زیر گزینه‌ای را انتخاب کنید:"
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=get_main_menu_keyboard())
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(welcome_text, reply_markup=get_main_menu_keyboard())


# مدیریت دکمه‌های شیشه‌ای (Callback Queries)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "back_to_main":
        context.user_data.clear()
        await query.edit_message_text(
            "به منوی اصلی برگشتید:",
            reply_markup=get_main_menu_keyboard()
        )
        return

    elif data == "user_view_products":
        try:
            response = supabase.table("products").select("*").execute()
            products = response.data
            
            if not products:
                await query.message.edit_text(
                    "📦 در حال حاضر محصولی در فروشگاه ثبت نشده است.",
                    reply_markup=get_main_menu_keyboard()
                )
                return

            await query.message.delete()
            for p in products:
                caption = (
                    f"🔖 کد محصول: {p.get('code')}\n"
                    f"💎 نام: {p.get('name')}\n"
                    f"💰 قیمت: {p.get('price')}\n"
                    f"📝 توضیحات: {p.get('description')}"
                )
                image_id = p.get('image_url')
                if image_id:
                    await context.bot.send_photo(chat_id=query.message.chat_id, photo=image_id, caption=caption)
                else:
                    await context.bot.send_message(chat_id=query.message.chat_id, text=caption)
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="✨ برای ادامه از منوی زیر استفاده کنید:",
                reply_markup=get_main_menu_keyboard()
            )
        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            await query.edit_message_text("❌ خطا در دریافت لیست محصولات از دیتابیس.", reply_markup=get_main_menu_keyboard())

    elif data == "admin_panel":
        if user_id != ADMIN_CHAT_ID:
            await query.answer("❌ شما دسترسی به پنل مدیریت ندارید!", show_alert=True)
            return
        context.user_data.clear()
        await query.edit_message_text("🛠 به پنل مدیریت خوش آمدید:", reply_markup=get_admin_menu_keyboard())

    elif data == "admin_add_product":
        if user_id != ADMIN_CHAT_ID:
            return
        context.user_data['state'] = ADD_CODE
        await query.edit_message_text("لطفاً **کد محصول** را وارد کنید:")

    elif data == "admin_edit_product":
        if user_id != ADMIN_CHAT_ID:
            return
        context.user_data['state'] = EDIT_SELECT_CODE
        await query.edit_message_text("لطفاً **کد محصولی** که می‌خواهید ویرایش کنید را وارد کنید:")


# مدیریت پیام‌های متنی و روند مراحل ثبت/ویرایش
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_CHAT_ID:
        return

    state = context.user_data.get('state')
    text = update.message.text.strip() if update.message.text else ""

    # --- مراحل افزودن محصول ---
    if state == ADD_CODE:
        context.user_data['new_code'] = text
        context.user_data['state'] = ADD_NAME
        await update.message.reply_text("نام محصول را وارد کنید:")

    elif state == ADD_NAME:
        context.user_data['new_name'] = text
        context.user_data['state'] = ADD_PRICE
        await update.message.reply_text("قیمت محصول را وارد کنید:")

    elif state == ADD_PRICE:
        context.user_data['new_price'] = text
        context.user_data['state'] = ADD_DESC
        await update.message.reply_text("توضیحات محصول را وارد کنید:")

    elif state == ADD_DESC:
        context.user_data['new_desc'] = text
        context.user_data['state'] = ADD_PHOTO
        await update.message.reply_text("📸 حالا عکس محصول را ارسال کنید:")

    elif state == ADD_PHOTO:
        if not update.message.photo:
            await update.message.reply_text("❌ لطفاً یک عکس معتبر ارسال کنید.")
            return
        
        photo_file_id = update.message.photo[-1].file_id

        p_data = {
            'code': context.user_data.get('new_code'),
            'name': context.user_data.get('new_name'),
            'price': context.user_data.get('new_price'),
            'description': context.user_data.get('new_desc'),
            'image_url': photo_file_id
        }

        try:
            supabase.table("products").insert(p_data).execute()
            context.user_data.clear()
            await update.message.reply_text("✅ محصول جدید با تصویر و مشخصات کامل ثبت شد!", reply_markup=get_admin_menu_keyboard())
        except Exception as e:
            logger.error(e)
            context.user_data.clear()
            await update.message.reply_text(f"❌ خطا در ثبت محصول در دیتابیس: {e}", reply_markup=get_admin_menu_keyboard())

    # --- مراحل ویرایش محصول ---
    elif state == EDIT_SELECT_CODE:
        p_code = text
        try:
            res = supabase.table("products").select("*").eq("code", p_code).execute()
            if not res.data:
                await update.message.reply_text("❌ محصولی با این کد پیدا نشد. لطفاً دوباره کد را وارد کنید:")
                return
            
            product = res.data[0]
            context.user_data['edit_code'] = p_code
            context.user_data['edit_name'] = product.get('name')
            context.user_data['edit_price'] = product.get('price')
            context.user_data['edit_desc'] = product.get('description')
            
            context.user_data['state'] = EDIT_PHOTO
            await update.message.reply_text(
                f"محصول پیدا شد: {product.get('name')}\n"
                "لطفاً **عکس جدید** محصول را ارسال کنید:"
            )
        except Exception as e:
            logger.error(e)
            await update.message.reply_text(f"❌ خطا در جستجوی محصول: {e}")

    elif state == EDIT_PHOTO:
        if not update.message.photo:
            await update.message.reply_text("❌ لطفاً یک عکس معتبر بفرستید.")
            return
        
        photo_file_id = update.message.photo[-1].file_id
        p_code = context.user_data.get('edit_code')

        updated_data = {
            'name': context.user_data.get('edit_name'),
            'price': context.user_data.get('edit_price'),
            'description': context.user_data.get('edit_desc'),
            'image_url': photo_file_id
        }

        try:
            supabase.table("products").update(updated_data).eq("code", p_code).execute()
            context.user_data.clear()
            await update.message.reply_text("✅ اطلاعات و تصویر محصول با موفقیت ویرایش و آپدیت شد!", reply_markup=get_admin_menu_keyboard())
        except Exception as e:
            logger.error(e)
            context.user_data.clear()
            await update.message.reply_text(f"❌ خطا در ویرایش محصول: {e}", reply_markup=get_admin_menu_keyboard())


def main():
    TOKEN = os.environ.get("BOT_TOKEN", "")
    
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, message_handler))

    print("🤖 ربات با موفقیت روشن شد و آماده به کار است...")
    
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
