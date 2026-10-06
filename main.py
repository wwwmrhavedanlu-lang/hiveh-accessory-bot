import os
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from supabase import create_client, Client

# راه‌اندازی سرور سبک Flask برای پاسخ به پورت رندر
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# خواندن متغیرهای محیطی
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# اتصال به سوپابیس
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# تابع پاسخ به دستور استارت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    welcome_message = (
        f"سلام {user_name} عزیز! 💙\n"
        "به ربات فروشگاهی زیورآلات **هیوه** خوش آمدید.\n\n"
        "به زودی امکانات کامل فروشگاه در دسترسی شما قرار می‌گیرد."
    )
    await update.message.reply_text(welcome_message)

def main():
    # اجرای سرور Flask در یک نخ جداگانه
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # ساخت اپلیکیشن ربات تلگرام
    application = Application.builder().token(BOT_TOKEN).build()

    # اضافه کردن هندلر دستور start
    application.add_handler(CommandHandler("start", start))

    # ایجاد و تنظیم صریح ایونت لوپ
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    print("Bot is starting successfully with Flask and Telegram...")
    
    # راه‌اندازی ربات
    application.run_polling()

if __name__ == "__main__":
    main()
