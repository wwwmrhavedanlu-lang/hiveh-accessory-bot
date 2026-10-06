import os
from telegram.ext import Application
from supabase import create_client, Client

# خواندن متغیرهای محیطی
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# اتصال به سوپابیس
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def main():
    # ساخت اپلیکیشن با متد جدید و استاندارد
    application = Application.builder().token(BOT_TOKEN).build()

    # در اینجا می‌توانید هندلرها را اضافه کنید (مثلاً: application.add_handler(...))

    print("Bot is starting...")
    # اجرای استاندارد ربات که خودش ایونت لوپ رو مدیریت می‌کنه
    application.run_polling()

if __name__ == "__main__":
    main()
