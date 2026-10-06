import os
import logging
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from supabase import create_client, Client

# تنظیمات لاگینگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# اطلاعات اتصال از متغیرهای محیطی
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_ID = 8521643361  # آیدی تلگرام مدیر

# راه‌اندازی Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# راه‌اندازی وب‌سرور Flask برای رندر
app = Flask(__name__)

@app.route('/')
def home():
    return "Hiveh Accessory Bot is active and running! 💙", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# منوی اصلی مشتریان
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("💎 مشاهده محصولات", callback_data="view_products")],
        [InlineKeyboardButton("🛒 ثبت سفارش", callback_data="order_guide"),
         InlineKeyboardButton("ℹ️ درباره ما", callback_data="about_us")],
        [InlineKeyboardButton("❌ لغو / خروج", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# دستور /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name if update.effective_user else "کاربر"
    welcome_text = (
        f"سلام {user_name} عزیز! به گالری بدلیجات و اکسسوری **هیوه** خوش آمدید. 💙\n\n"
        "لطفاً از منوی زیر یکی از گزینه‌ها را انتخاب کنید:"
    )
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")

# مدیریت دکمه‌های شیشه‌ای منو
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "view_products":
        products_text = "💎 **لیست محصولات هیوه:**\n\n"
        try:
            if supabase:
                response = supabase.table("products").select("*").execute()
                products = response.data
                if products:
                    for p in products:
                        products_text += f"• {p.get('name')} - {p.get('price')} تومان\n"
                else:
                    products_text += "هنوز محصولی در دیتابیس ثبت نشده است."
            else:
                products_text += "ارتباط با دیتابیس برقرار نیست."
        except Exception:
            products_text += "در حال حاضر دریافت لیست محصولات با خطا مواجه شد."

        keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_home")]]
        await query.edit_message_text(products_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "order_guide":
        text = (
            "🛒 **راهنمای ثبت سفارش:**\n\n"
            "برای ثبت سفارش محصول مورد نظر، لطفاً عکس یا نام محصول را به همراه مشخصات ارسال به ادمین بفرستید تا فاکتور برای شما صادر شود. 💙"
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "about_us":
        text = (
            "ℹ️ **درباره گالری هیوه:**\n\n"
            "تولید و عرضه زیباترین اکسسوری‌ها و بدلیجات دست‌ساز با بالاترین کیفیت. همراه شما هستیم در لحظات خاص! 💙"
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_home")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "cancel":
        await query.edit_message_text("عملیات لغو شد. هر زمان خواستید دوباره شروع کنید، دستور /start را ارسال کنید. 💙")

    elif data == "back_to_home":
        await start(update, context)

def main():
    if not BOT_TOKEN:
        logger.error("توکن ربات (BOT_TOKEN) تنظیم نشده است!")
        return

    # اجرای سرور Flask روی ترد جداگانه برای جلوگیری از ارور پورت رندر
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("وب‌سرور Flask استارت شد.")

    # ساخت اپلیکیشن ربات تلگرام
    application = Application.builder().token(BOT_TOKEN).build()

    # ثبت هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    # شروع کار ربات
    logger.info("ربات تلگرام شروع به کار کرد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()