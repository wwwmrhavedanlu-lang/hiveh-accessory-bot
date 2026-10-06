import os
import threading
from flask import Flask
from telegram.ext import Application
from supabase import create_client, Client

# راه‌اندازی سرور سبک Flask برای پاسخ به درخواست‌های پورت در رندر
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# خواندن متغیرهای محیطی
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# اتصال به سوپابیس
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def main():
    # راه‌اندازی سرور Flask در یک نخ جداگانه
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # ساخت اپلیکیشن ربات تلگرام
    application = Application.builder().token(BOT_TOKEN).build()

    print("Bot is starting with web server...")
    # اجرای ربات
    application.run_polling()

if __name__ == "__main__":
    main()
