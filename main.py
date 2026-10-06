import asyncio
import html
import logging
import os
import threading
from decimal import Decimal, InvalidOperation

from flask import Flask

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from supabase import create_client, Client


# =========================================================
# تنظیمات لاگ
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# لاگ‌های اضافی کتابخانه HTTP را کمتر می‌کنیم
logging.getLogger("httpx").setLevel(logging.WARNING)


# =========================================================
# تنظیمات Environment
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()


# =========================================================
# آیدی عددی ادمین
# =========================================================

ADMIN_CHAT_ID = 8521643361


# =========================================================
# بررسی تنظیمات
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN تنظیم نشده است.")

if not SUPABASE_URL:
    raise RuntimeError("❌ SUPABASE_URL تنظیم نشده است.")

if not SUPABASE_KEY:
    raise RuntimeError("❌ SUPABASE_KEY تنظیم نشده است.")


# =========================================================
# اتصال به Supabase
# =========================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================================================
# State های Conversation
# =========================================================

(
    ADD_CODE,
    ADD_NAME,
    ADD_PRICE,
    ADD_DESC,
    ADD_PHOTO,

    EDIT_SELECT_CODE,
    EDIT_MENU,
    EDIT_NAME,
    EDIT_PRICE,
    EDIT_DESC,
    EDIT_PHOTO,

    DELETE_SELECT_CODE,
    DELETE_CONFIRM,

    CHECKOUT_NAME,
    CHECKOUT_PHONE,
    CHECKOUT_ADDRESS,
    CHECKOUT_CONFIRM,
    ADMIN_ORDERS,
    ADMIN_ORDER_STATUS,
    USER_PRODUCT_CODE,
) = range(20)


# =========================================================
# توابع کمکی
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_CHAT_ID


def format_price(price) -> str:
    """
    تبدیل قیمت به فرمت خوانا
    مثال:
    28000000 -> 28,000,000 تومان
    """

    if price is None:
        return "نامشخص"

    try:
        value = int(Decimal(str(price)))
        return f"{value:,} تومان"

    except (ValueError, InvalidOperation):
        return str(price)


def safe_text(value) -> str:
    """
    جلوگیری از خراب شدن HTML تلگرام
    """

    if value is None:
        return ""

    return html.escape(str(value))



def normalize_product_code(value: str) -> str:
    """
    تبدیل اعداد فارسی و عربی به انگلیسی تا کد محصول با هر دو شکل کار کند.
    مثال: ۱۲۳۴۵ و ١٢٣٤٥ و 12345 همگی به 12345 تبدیل می‌شوند.
    """

    if value is None:
        return ""

    translation = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )

    return str(value).translate(translation).strip()


# =========================================================
# منوی اصلی
# =========================================================

def get_main_menu_keyboard():

    keyboard = [
        [
            InlineKeyboardButton(
                "📦 مشاهده محصولات",
                callback_data="user_view_products"
            ),
            InlineKeyboardButton(
                "🛒 سبد خرید",
                callback_data="view_cart"
            ),
        ],
        [
            InlineKeyboardButton(
                "👤 پنل مدیریت",
                callback_data="admin_panel"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)

# =========================================================
# منوی مدیریت
# =========================================================

def get_admin_menu_keyboard():

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ افزودن محصول جدید",
                callback_data="admin_add_product"
            )
        ],
        [
            InlineKeyboardButton(
                "✏️ ویرایش محصول",
                callback_data="admin_edit_product"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑 حذف محصول",
                callback_data="admin_delete_product"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 مدیریت سفارش‌ها",
                callback_data="admin_orders"
            )
        ],
        [
            InlineKeyboardButton(
                "📦 مشاهده محصولات",
                callback_data="user_view_products"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت به منوی اصلی",
                callback_data="back_to_main"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# منوی ویرایش
# =========================================================

def get_edit_menu_keyboard():

    keyboard = [
        [
            InlineKeyboardButton(
                "💎 تغییر نام",
                callback_data="edit_name"
            ),
            InlineKeyboardButton(
                "💰 تغییر قیمت",
                callback_data="edit_price"
            ),
        ],
        [
            InlineKeyboardButton(
                "📝 تغییر توضیحات",
                callback_data="edit_desc"
            ),
            InlineKeyboardButton(
                "🖼 تغییر عکس",
                callback_data="edit_photo"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت به پنل",
                callback_data="admin_panel"
            )
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# دکمه لغو
# =========================================================

def get_cancel_keyboard():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "❌ لغو عملیات",
                    callback_data="cancel_operation"
                )
            ]
        ]
    )


# =========================================================
# دکمه تایید حذف
# =========================================================

def get_delete_confirm_keyboard():

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ بله، حذف شود",
                callback_data="delete_confirm_yes"
            ),
            InlineKeyboardButton(
                "❌ خیر",
                callback_data="delete_confirm_no"
            ),
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# ساخت متن محصول
# =========================================================

def product_caption(product):

    name = safe_text(product.get("name", "بدون نام"))
    code = safe_text(product.get("code", "-"))
    description = safe_text(
        product.get("description") or "توضیحی ثبت نشده است."
    )

    price = format_price(product.get("price"))

    return (
        f"💎 <b>{name}</b>\n\n"
        f"🔖 کد محصول: <code>{code}</code>\n"
        f"💰 قیمت: <b>{price}</b>\n\n"
        f"📝 توضیحات:\n"
        f"{description}"
    )


# =========================================================
# /start
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    for key in list(context.user_data.keys()):
        if key != "cart":
            context.user_data.pop(key, None)

    text = (
        "✨ <b>به فروشگاه هیوه خوش آمدید</b> ✨\n\n"
        "دنیای بدلیجات و اکسسوری‌های خاص و شیک 💎\n\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:"
    )

    if update.message:

        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard(),
        )

    elif update.callback_query:

        await update.callback_query.answer()

        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard(),
        )

    return ConversationHandler.END


# =========================================================
# مشاهده محصول با کد
# =========================================================

async def start_product_lookup(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    وقتی مشتری روی «مشاهده محصولات» می‌زند، به جای نمایش همه محصولات
    ابتدا کد محصول را می‌گیرد.
    """

    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🔎 <b>جستجوی محصول</b>\n\n"
        "لطفاً <b>کد محصول</b> را وارد کنید.\n\n"
        "🔢 کد را می‌توانید با اعداد <b>فارسی یا انگلیسی</b> وارد کنید.\n"
        "مثال: <code>۱۲۳۴۵</code> یا <code>12345</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard(),
    )

    return USER_PRODUCT_CODE


async def find_product_by_code(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """جستجوی محصول بر اساس کد، با پشتیبانی از اعداد فارسی و انگلیسی."""

    raw_code = update.message.text or ""
    code = normalize_product_code(raw_code)

    if not code:
        await update.message.reply_text(
            "❌ لطفاً کد محصول را وارد کنید.",
            reply_markup=get_cancel_keyboard(),
        )
        return USER_PRODUCT_CODE

    if not code.isdigit():
        await update.message.reply_text(
            "❌ کد محصول فقط باید شامل عدد باشد.\n\n"
            "مثال: <code>12345</code> یا <code>۱۲۳۴۵</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_keyboard(),
        )
        return USER_PRODUCT_CODE

    try:
        result = (
            supabase
            .table("products")
            .select("*")
            .eq("code", code)
            .limit(1)
            .execute()
        )

        if not result.data:
            await update.message.reply_text(
                "❌ محصولی با این کد پیدا نشد.\n\n"
                "کد محصول را بررسی کنید و دوباره وارد کنید:",
                reply_markup=get_cancel_keyboard(),
            )
            return USER_PRODUCT_CODE

        product = result.data[0]
        product_id = product.get("id")
        image_id = product.get("image_url")
        caption = product_caption(product)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🛒 افزودن به سبد",
                    callback_data=f"add_to_cart:{product_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🛒 مشاهده سبد خرید",
                    callback_data="view_cart"
                ),
                InlineKeyboardButton(
                    "🔎 جستجوی محصول دیگر",
                    callback_data="user_view_products"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔙 منوی اصلی",
                    callback_data="back_to_main"
                )
            ],
        ])

        # پیام درخواست کد را حذف می‌کنیم تا نتیجه تمیز نمایش داده شود.
        try:
            await update.message.delete()
        except Exception:
            pass

        if image_id:
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=image_id,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
            except Exception as e:
                logger.error(f"خطا در ارسال عکس محصول: {e}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )

        return ConversationHandler.END

    except Exception:
        logger.exception("خطا در جستجوی محصول با کد")
        await update.message.reply_text(
            "❌ خطایی هنگام جستجوی محصول رخ داد.\n"
            "لطفاً دوباره تلاش کنید.",
            reply_markup=get_main_menu_keyboard(),
        )
        return ConversationHandler.END


# =========================================================
# سفارش و تسویه حساب
# =========================================================

def get_checkout_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ تأیید و ثبت سفارش",
                callback_data="checkout_confirm"
            )
        ],
        [
            InlineKeyboardButton(
                "✏️ تغییر اطلاعات",
                callback_data="checkout_restart"
            ),
            InlineKeyboardButton(
                "❌ لغو",
                callback_data="checkout_cancel"
            )
        ],
    ])


def get_admin_orders_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📋 سفارش‌های جدید",
                callback_data="admin_orders_pending"
            )
        ],
        [
            InlineKeyboardButton(
                "📦 همه سفارش‌ها",
                callback_data="admin_orders_all"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت به پنل",
                callback_data="admin_panel"
            )
        ],
    ])


def get_order_status_keyboard(order_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⏳ در حال بررسی",
                callback_data=f"order_status:{order_id}:processing"
            ),
            InlineKeyboardButton(
                "📦 آماده ارسال",
                callback_data=f"order_status:{order_id}:shipped"
            ),
        ],
        [
            InlineKeyboardButton(
                "🚚 ارسال شد",
                callback_data=f"order_status:{order_id}:delivered"
            ),
            InlineKeyboardButton(
                "❌ لغو سفارش",
                callback_data=f"order_status:{order_id}:cancelled"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 لیست سفارش‌ها",
                callback_data="admin_orders_all"
            )
        ]
    ])


def order_status_fa(status):
    return {
        "pending": "🆕 جدید",
        "processing": "⏳ در حال بررسی",
        "shipped": "📦 آماده ارسال",
        "delivered": "🚚 ارسال شد",
        "cancelled": "❌ لغو شده",
    }.get(status, status)


async def start_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not get_cart(context):
        await query.answer(
            "🛒 سبد خرید شما خالی است.",
            show_alert=True
        )
        return ConversationHandler.END

    context.user_data["checkout"] = {}

    await query.edit_message_text(
        "🧾 <b>ثبت سفارش</b>\n\n"
        "لطفاً نام و نام خانوادگی خود را وارد کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard(),
    )
    return CHECKOUT_NAME


async def checkout_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()

    if len(name) < 2:
        await update.message.reply_text(
            "❌ نام واردشده معتبر نیست. دوباره وارد کنید:"
        )
        return CHECKOUT_NAME

    context.user_data.setdefault("checkout", {})["name"] = name

    await update.message.reply_text(
        "📱 شماره موبایل خود را وارد کنید:\n\n"
        "مثال: <code>09123456789</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard(),
    )
    return CHECKOUT_PHONE


async def checkout_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip().replace(" ", "").replace("-", "")

    if not phone.isdigit() or len(phone) < 10 or len(phone) > 15:
        await update.message.reply_text(
            "❌ شماره موبایل معتبر نیست. لطفاً دوباره وارد کنید:"
        )
        return CHECKOUT_PHONE

    context.user_data.setdefault("checkout", {})["phone"] = phone

    await update.message.reply_text(
        "📍 آدرس کامل گیرنده را وارد کنید:\n\n"
        "استان، شهر، خیابان، کوچه، پلاک و واحد",
        reply_markup=get_cancel_keyboard(),
    )
    return CHECKOUT_ADDRESS


async def checkout_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()

    if len(address) < 10:
        await update.message.reply_text(
            "❌ آدرس خیلی کوتاه است. لطفاً آدرس کامل را وارد کنید:"
        )
        return CHECKOUT_ADDRESS

    context.user_data.setdefault("checkout", {})["address"] = address

    checkout = context.user_data["checkout"]
    lines = [
        "🧾 <b>بررسی نهایی سفارش</b>",
        "",
        f"👤 نام: <b>{safe_text(checkout['name'])}</b>",
        f"📱 موبایل: <code>{safe_text(checkout['phone'])}</code>",
        f"📍 آدرس: {safe_text(checkout['address'])}",
        "",
        "🛒 <b>اقلام سفارش:</b>",
    ]

    for item in get_cart(context).values():
        subtotal = int(item["price"]) * int(item["quantity"])
        lines.append(
            f"• {safe_text(item['name'])} × {item['quantity']} = "
            f"{format_price(subtotal)}"
        )

    lines.append("")
    lines.append(f"💰 <b>مبلغ کل: {format_price(cart_total(context))}</b>")
    lines.append("")
    lines.append("آیا اطلاعات بالا صحیح است؟")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=get_checkout_keyboard(),
    )
    return CHECKOUT_CONFIRM


async def create_order(context, user):
    cart = get_cart(context)
    checkout = context.user_data.get("checkout", {})

    order_data = {
        "telegram_user_id": user.id,
        "username": user.username or "",
        "customer_name": checkout["name"],
        "phone": checkout["phone"],
        "address": checkout["address"],
        "total": cart_total(context),
        "status": "pending",
    }

    order_result = (
        supabase
        .table("orders")
        .insert(order_data)
        .execute()
    )

    if not order_result.data:
        raise RuntimeError("ثبت سفارش انجام نشد.")

    order = order_result.data[0]
    order_id = order["id"]

    items = []
    for product_id, item in cart.items():
        items.append({
            "order_id": order_id,
            "product_id": int(product_id),
            "product_name": item["name"],
            "price": int(item["price"]),
            "quantity": int(item["quantity"]),
            "subtotal": int(item["price"]) * int(item["quantity"]),
        })

    if items:
        supabase.table("order_items").insert(items).execute()

    return order


async def checkout_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data == "checkout_cancel":
        await query.answer("❌ ثبت سفارش لغو شد.")
        context.user_data.pop("checkout", None)
        await query.edit_message_text(
            "❌ ثبت سفارش لغو شد.",
            reply_markup=get_main_menu_keyboard(),
        )
        return ConversationHandler.END

    if query.data == "checkout_restart":
        await query.answer()
        context.user_data["checkout"] = {}
        await query.edit_message_text(
            "🧾 <b>ثبت سفارش</b>\n\n"
            "لطفاً نام و نام خانوادگی خود را وارد کنید:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_keyboard(),
        )
        return CHECKOUT_NAME

    if query.data != "checkout_confirm":
        return CHECKOUT_CONFIRM

    await query.answer("در حال ثبت سفارش...")

    try:
        order = await create_order(context, query.from_user)
        order_id = order["id"]
        total = order["total"]

        get_cart(context).clear()
        context.user_data.pop("checkout", None)

        await query.edit_message_text(
            "🎉 <b>سفارش شما با موفقیت ثبت شد!</b>\n\n"
            f"🧾 شماره سفارش: <code>#{order_id}</code>\n"
            f"💰 مبلغ سفارش: <b>{format_price(total)}</b>\n"
            "📌 وضعیت: 🆕 جدید\n\n"
            "به‌زودی سفارش شما توسط هیوه بررسی می‌شود.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard(),
        )

        if ADMIN_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=(
                        "🔔 <b>سفارش جدید</b>\n\n"
                        f"🧾 شماره سفارش: <code>#{order_id}</code>\n"
                        f"👤 مشتری: {safe_text(order['customer_name'])}\n"
                        f"📱 موبایل: <code>{safe_text(order['phone'])}</code>\n"
                        f"💰 مبلغ: <b>{format_price(order['total'])}</b>"
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_order_status_keyboard(order_id),
                )
            except Exception:
                logger.exception("خطا در اطلاع‌رسانی سفارش جدید به ادمین")

        return ConversationHandler.END

    except Exception:
        logger.exception("خطا در ثبت سفارش")
        await query.edit_message_text(
            "❌ متأسفانه ثبت سفارش انجام نشد.\n"
            "لطفاً چند لحظه بعد دوباره تلاش کنید.",
            reply_markup=get_main_menu_keyboard(),
        )
        return ConversationHandler.END


async def show_admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ دسترسی ندارید.", show_alert=True)
        return

    await query.answer()

    status_filter = None
    if query.data == "admin_orders_pending":
        status_filter = "pending"

    try:
        builder = (
            supabase
            .table("orders")
            .select("*")
            .order("created_at", desc=True)
        )

        if status_filter:
            builder = builder.eq("status", status_filter)

        result = builder.limit(20).execute()
        orders = result.data or []

        if not orders:
            await query.edit_message_text(
                "📋 سفارشی برای نمایش وجود ندارد.",
                reply_markup=get_admin_orders_keyboard(),
            )
            return

        lines = ["📋 <b>سفارش‌ها</b>\n"]

        for order in orders:
            lines.append(
                f"🧾 <b>#{order['id']}</b> | "
                f"{safe_text(order.get('customer_name', '-'))}\n"
                f"💰 {format_price(order.get('total'))} | "
                f"{order_status_fa(order.get('status', 'pending'))}"
            )

        await query.edit_message_text(
            "\n\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        f"🧾 #{order['id']}",
                        callback_data=f"admin_order:{order['id']}"
                    )
                ]
                for order in orders
            ] + [
                [
                    InlineKeyboardButton(
                        "🔙 بازگشت",
                        callback_data="admin_orders"
                    )
                ]
            ]),
        )

    except Exception:
        logger.exception("خطا در نمایش سفارش‌ها")
        await query.edit_message_text(
            "❌ خطا در دریافت سفارش‌ها.",
            reply_markup=get_admin_orders_keyboard(),
        )


async def show_admin_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ دسترسی ندارید.", show_alert=True)
        return

    await query.answer()

    try:
        order_id = int(query.data.split(":", 1)[1])

        order_result = (
            supabase
            .table("orders")
            .select("*")
            .eq("id", order_id)
            .limit(1)
            .execute()
        )

        if not order_result.data:
            await query.edit_message_text(
                "❌ سفارش پیدا نشد.",
                reply_markup=get_admin_orders_keyboard(),
            )
            return

        order = order_result.data[0]

        items_result = (
            supabase
            .table("order_items")
            .select("*")
            .eq("order_id", order_id)
            .execute()
        )

        lines = [
            f"🧾 <b>سفارش #{order_id}</b>",
            "",
            f"👤 مشتری: <b>{safe_text(order.get('customer_name', '-'))}</b>",
            f"📱 موبایل: <code>{safe_text(order.get('phone', '-'))}</code>",
            f"📍 آدرس: {safe_text(order.get('address', '-'))}",
            f"📌 وضعیت: <b>{order_status_fa(order.get('status', 'pending'))}</b>",
            "",
            "🛒 <b>اقلام:</b>",
        ]

        for item in items_result.data or []:
            lines.append(
                f"• {safe_text(item.get('product_name', '-'))} × "
                f"{item.get('quantity', 0)} = "
                f"{format_price(item.get('subtotal'))}"
            )

        lines.append("")
        lines.append(
            f"💰 <b>مبلغ کل: {format_price(order.get('total'))}</b>"
        )

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=get_order_status_keyboard(order_id),
        )

    except Exception:
        logger.exception("خطا در نمایش جزئیات سفارش")
        await query.edit_message_text(
            "❌ خطا در دریافت سفارش.",
            reply_markup=get_admin_orders_keyboard(),
        )


async def update_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not is_admin(query.from_user.id):
        await query.answer("❌ دسترسی ندارید.", show_alert=True)
        return

    try:
        _, order_id, status = query.data.split(":", 2)
        order_id = int(order_id)

        result = (
            supabase
            .table("orders")
            .update({"status": status})
            .eq("id", order_id)
            .execute()
        )

        if not result.data:
            await query.answer("❌ سفارش پیدا نشد.", show_alert=True)
            return

        await query.answer("✅ وضعیت سفارش تغییر کرد.")

        order = result.data[0]

        await query.edit_message_text(
            f"🧾 <b>سفارش #{order_id}</b>\n\n"
            f"👤 {safe_text(order.get('customer_name', '-'))}\n"
            f"💰 {format_price(order.get('total'))}\n"
            f"📌 وضعیت جدید: <b>{order_status_fa(status)}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_order_status_keyboard(order_id),
        )

        try:
            await context.bot.send_message(
                chat_id=order["telegram_user_id"],
                text=(
                    f"📦 <b>به‌روزرسانی سفارش #{order_id}</b>\n\n"
                    f"وضعیت سفارش شما تغییر کرد به:\n"
                    f"<b>{order_status_fa(status)}</b>"
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            logger.exception("خطا در ارسال وضعیت سفارش به مشتری")

    except Exception:
        logger.exception("خطا در تغییر وضعیت سفارش")
        await query.answer("❌ خطا در تغییر وضعیت سفارش.", show_alert=True)


# =========================================================
# سبد خرید مشتری
# =========================================================

def get_cart(context):
    return context.user_data.setdefault("cart", {})


async def fetch_product(product_id):
    result = (
        supabase
        .table("products")
        .select("*")
        .eq("id", product_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def cart_total(context):
    total = 0
    for item in get_cart(context).values():
        total += int(item["price"]) * int(item["quantity"])
    return total


def cart_count(context):
    return sum(int(item["quantity"]) for item in get_cart(context).values())


def get_cart_keyboard(context):
    keyboard = []
    for product_id, item in get_cart(context).items():
        keyboard.append([
            InlineKeyboardButton(
                "➖",
                callback_data=f"cart_dec:{product_id}"
            ),
            InlineKeyboardButton(
                f"{item['name']} × {item['quantity']}",
                callback_data=f"product_detail:{product_id}"
            ),
            InlineKeyboardButton(
                "➕",
                callback_data=f"cart_inc:{product_id}"
            ),
        ])
        keyboard.append([
            InlineKeyboardButton(
                "🗑 حذف از سبد",
                callback_data=f"cart_remove:{product_id}"
            )
        ])

    if get_cart(context):
        keyboard.append([
            InlineKeyboardButton(
                "🗑 خالی کردن سبد",
                callback_data="cart_clear"
            )
        ])

    if get_cart(context):
        keyboard.append([
            InlineKeyboardButton(
                "🧾 ثبت سفارش",
                callback_data="start_checkout"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "📦 مشاهده محصولات",
            callback_data="user_view_products"
        )
    ])
    keyboard.append([
        InlineKeyboardButton(
            "🔙 منوی اصلی",
            callback_data="back_to_main"
        )
    ])
    return InlineKeyboardMarkup(keyboard)


async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cart = get_cart(context)

    if not cart:
        await query.edit_message_text(
            "🛒 <b>سبد خرید شما خالی است.</b>\n\n"
            "از بخش محصولات، کالاهای موردنظر خود را به سبد اضافه کنید.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cart_keyboard(context),
        )
        return

    lines = ["🛒 <b>سبد خرید شما</b>\n"]
    for item in cart.values():
        subtotal = int(item["price"]) * int(item["quantity"])
        lines.append(
            f"💎 {safe_text(item['name'])}\n"
            f"تعداد: <b>{item['quantity']}</b> × {format_price(item['price'])} "
            f"= <b>{format_price(subtotal)}</b>"
        )

    lines.append(f"\n💰 <b>مبلغ کل: {format_price(cart_total(context))}</b>")
    lines.append(f"📦 تعداد کالا: <b>{cart_count(context)}</b>")

    await query.edit_message_text(
        "\n\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=get_cart_keyboard(context),
    )


async def add_product_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    try:
        product_id = int(query.data.split(":", 1)[1])
        product = await fetch_product(product_id)

        if not product:
            await query.answer("❌ محصول پیدا نشد.", show_alert=True)
            return

        cart = get_cart(context)
        key = str(product_id)

        if key in cart:
            cart[key]["quantity"] += 1
        else:
            cart[key] = {
                "name": product.get("name", "بدون نام"),
                "price": int(Decimal(str(product.get("price", 0)))),
                "quantity": 1,
            }

        await query.answer("✅ محصول به سبد خرید اضافه شد.")

    except Exception:
        logger.exception("خطا در افزودن محصول به سبد")
        try:
            await query.answer("❌ خطا در افزودن محصول به سبد.", show_alert=True)
        except Exception:
            pass


async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        product_id = int(query.data.split(":", 1)[1])
        product = await fetch_product(product_id)

        if not product:
            await query.edit_message_text(
                "❌ این محصول دیگر در فروشگاه موجود نیست.",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🛒 افزودن به سبد",
                    callback_data=f"add_to_cart:{product_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🛒 مشاهده سبد خرید",
                    callback_data="view_cart"
                ),
                InlineKeyboardButton(
                    "📦 بازگشت به محصولات",
                    callback_data="user_view_products"
                ),
            ],
        ])

        caption = product_caption(product)
        image_id = product.get("image_url")

        try:
            await query.message.delete()
        except Exception:
            pass

        if image_id:
            try:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=image_id,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
            except Exception:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
    except Exception:
        logger.exception("خطا در نمایش جزئیات محصول")
        await query.answer("❌ خطا در نمایش محصول.", show_alert=True)


async def cart_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        action, product_id = query.data.split(":", 1)
        cart = get_cart(context)

        if product_id not in cart:
            await show_cart(update, context)
            return

        if action == "cart_inc":
            cart[product_id]["quantity"] += 1
        elif action == "cart_dec":
            cart[product_id]["quantity"] -= 1
            if cart[product_id]["quantity"] <= 0:
                del cart[product_id]
        elif action == "cart_remove":
            del cart[product_id]

        await show_cart(update, context)

    except Exception:
        logger.exception("خطا در تغییر سبد خرید")
        await query.answer("❌ خطا در تغییر سبد خرید.", show_alert=True)


async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    get_cart(context).clear()
    await query.answer("🗑 سبد خرید خالی شد.")
    await show_cart(update, context)


# =========================================================
# شروع افزودن محصول
# =========================================================

async def start_add_product(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not is_admin(query.from_user.id):

        await query.answer(
            "❌ شما اجازه دسترسی ندارید.",
            show_alert=True
        )

        return ConversationHandler.END

    await query.answer()

    context.user_data.clear()

    await query.edit_message_text(
        "➕ <b>افزودن محصول جدید</b>\n\n"
        "🔖 لطفاً کد محصول را وارد کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard(),
    )

    return ADD_CODE


# =========================================================
# دریافت کد محصول
# =========================================================

async def add_code(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    code = update.message.text.strip()

    if not code:

        await update.message.reply_text(
            "❌ کد محصول نمی‌تواند خالی باشد."
        )

        return ADD_CODE

    try:

        existing = (
            supabase
            .table("products")
            .select("id")
            .eq("code", code)
            .execute()
        )

        if existing.data:

            await update.message.reply_text(
                "❌ این کد محصول قبلاً ثبت شده است.\n\n"
                "لطفاً کد دیگری وارد کنید:"
            )

            return ADD_CODE

    except Exception:

        logger.exception(
            "خطا در بررسی کد محصول"
        )

        await update.message.reply_text(
            "❌ خطا در بررسی کد محصول."
        )

        return ADD_CODE

    context.user_data["new_code"] = code

    await update.message.reply_text(
        "💎 حالا <b>نام محصول</b> را وارد کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard(),
    )

    return ADD_NAME


# =========================================================
# دریافت نام محصول
# =========================================================

async def add_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    name = update.message.text.strip()

    if not name:

        await update.message.reply_text(
            "❌ نام محصول نمی‌تواند خالی باشد."
        )

        return ADD_NAME

    context.user_data["new_name"] = name

    await update.message.reply_text(
        "💰 قیمت محصول را به <b>تومان</b> وارد کنید.\n\n"
        "مثال:\n"
        "<code>28000000</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard(),
    )

    return ADD_PRICE


# =========================================================
# دریافت قیمت
# =========================================================

async def add_price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    price_text = (
        update.message.text
        .strip()
        .replace(",", "")
        .replace("٬", "")
    )

    try:

        price = Decimal(price_text)

        if price <= 0:
            raise InvalidOperation

    except (InvalidOperation, ValueError):

        await update.message.reply_text(
            "❌ قیمت نامعتبر است.\n\n"
            "لطفاً فقط عدد وارد کنید.\n"
            "مثال: <code>28000000</code>",
            parse_mode=ParseMode.HTML,
        )

        return ADD_PRICE

    context.user_data["new_price"] = int(price)

    await update.message.reply_text(
        "📝 توضیحات محصول را وارد کنید:",
        reply_markup=get_cancel_keyboard(),
    )

    return ADD_DESC


# =========================================================
# دریافت توضیحات
# =========================================================

async def add_description(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    description = update.message.text.strip()

    if not description:
        description = "توضیحی ثبت نشده است."

    context.user_data["new_desc"] = description

    await update.message.reply_text(
        "🖼 حالا <b>عکس محصول</b> را ارسال کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard(),
    )

    return ADD_PHOTO


# =========================================================
# دریافت عکس و ثبت محصول
# =========================================================

async def add_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message.photo:

        await update.message.reply_text(
            "❌ لطفاً یک عکس معتبر ارسال کنید."
        )

        return ADD_PHOTO

    photo_file_id = update.message.photo[-1].file_id

    product_data = {
        "code": context.user_data.get("new_code"),
        "name": context.user_data.get("new_name"),
        "price": context.user_data.get("new_price"),
        "description": context.user_data.get("new_desc"),
        "image_url": photo_file_id,
    }

    try:

        (
            supabase
            .table("products")
            .insert(product_data)
            .execute()
        )

        context.user_data.clear()

        await update.message.reply_text(
            "✅ <b>محصول با موفقیت ثبت شد.</b> 🎉",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_menu_keyboard(),
        )

        return ConversationHandler.END

    except Exception as e:

        logger.exception(
            f"خطا در ثبت محصول: {e}"
        )

        context.user_data.clear()

        await update.message.reply_text(
            "❌ خطا در ثبت محصول در دیتابیس.\n\n"
            "جزئیات خطا در لاگ Render ثبت شده است.",
            reply_markup=get_admin_menu_keyboard(),
        )

        return ConversationHandler.END


# =========================================================
# شروع ویرایش محصول
# =========================================================

async def start_edit_product(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not is_admin(query.from_user.id):

        await query.answer(
            "❌ شما اجازه دسترسی ندارید.",
            show_alert=True
        )

        return ConversationHandler.END

    await query.answer()

    context.user_data.clear()

    await query.edit_message_text(
        "✏️ <b>ویرایش محصول</b>\n\n"
        "🔖 کد محصول موردنظر را وارد کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard(),
    )

    return EDIT_SELECT_CODE


# =========================================================
# پیدا کردن محصول برای ویرایش
# =========================================================

async def edit_select_code(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    code = update.message.text.strip()

    try:

        result = (
            supabase
            .table("products")
            .select("*")
            .eq("code", code)
            .limit(1)
            .execute()
        )

        if not result.data:

            await update.message.reply_text(
                "❌ محصولی با این کد پیدا نشد.\n\n"
                "لطفاً کد صحیح را وارد کنید:"
            )

            return EDIT_SELECT_CODE

        product = result.data[0]

        context.user_data["edit_code"] = code
        context.user_data["edit_product"] = product

        text = (
            "✏️ <b>محصول پیدا شد</b>\n\n"
            f"💎 نام: {safe_text(product.get('name', '-'))}\n"
            f"🔖 کد: {safe_text(product.get('code', '-'))}\n"
            f"💰 قیمت: {format_price(product.get('price'))}\n"
            f"📝 توضیحات: "
            f"{safe_text(product.get('description', '-'))}\n\n"
            "کدام قسمت را می‌خواهید تغییر دهید؟"
        )

        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_edit_menu_keyboard(),
        )

        return EDIT_MENU

    except Exception:

        logger.exception(
            "خطا در پیدا کردن محصول"
        )

        await update.message.reply_text(
            "❌ خطا در جستجوی محصول."
        )

        return EDIT_SELECT_CODE


# =========================================================
# منوی ویرایش
# =========================================================

async def edit_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    await query.answer()

    data = query.data

    if data == "edit_name":

        await query.edit_message_text(
            "💎 نام جدید محصول را وارد کنید:",
            reply_markup=get_cancel_keyboard(),
        )

        return EDIT_NAME

    if data == "edit_price":

        await query.edit_message_text(
            "💰 قیمت جدید محصول را به تومان وارد کنید.\n\n"
            "مثال:\n"
            "<code>28000000</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_keyboard(),
        )

        return EDIT_PRICE

    if data == "edit_desc":

        await query.edit_message_text(
            "📝 توضیحات جدید محصول را وارد کنید:",
            reply_markup=get_cancel_keyboard(),
        )

        return EDIT_DESC

    if data == "edit_photo":

        await query.edit_message_text(
            "🖼 عکس جدید محصول را ارسال کنید:",
            reply_markup=get_cancel_keyboard(),
        )

        return EDIT_PHOTO

    if data == "admin_panel":

        context.user_data.clear()

        await query.edit_message_text(
            "🛠 <b>پنل مدیریت هیوه</b>\n\n"
            "لطفاً یکی از گزینه‌ها را انتخاب کنید:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_menu_keyboard(),
        )

        return ConversationHandler.END

    return EDIT_MENU


# =========================================================
# تغییر نام
# =========================================================

async def edit_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    new_name = update.message.text.strip()

    if not new_name:

        await update.message.reply_text(
            "❌ نام محصول نمی‌تواند خالی باشد."
        )

        return EDIT_NAME

    code = context.user_data.get("edit_code")

    try:

        (
            supabase
            .table("products")
            .update({
                "name": new_name
            })
            .eq("code", code)
            .execute()
        )

        context.user_data.clear()

        await update.message.reply_text(
            "✅ نام محصول با موفقیت تغییر کرد.",
            reply_markup=get_admin_menu_keyboard(),
        )

        return ConversationHandler.END

    except Exception:

        logger.exception(
            "خطا در تغییر نام"
        )

        await update.message.reply_text(
            "❌ خطا در تغییر نام محصول."
        )

        return EDIT_NAME


# =========================================================
# تغییر قیمت
# =========================================================

async def edit_price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    price_text = (
        update.message.text
        .strip()
        .replace(",", "")
        .replace("٬", "")
    )

    try:

        price = Decimal(price_text)

        if price <= 0:
            raise InvalidOperation

    except (InvalidOperation, ValueError):

        await update.message.reply_text(
            "❌ قیمت نامعتبر است.\n\n"
            "لطفاً فقط عدد وارد کنید."
        )

        return EDIT_PRICE

    code = context.user_data.get("edit_code")

    try:

        (
            supabase
            .table("products")
            .update({
                "price": int(price)
            })
            .eq("code", code)
            .execute()
        )

        context.user_data.clear()

        await update.message.reply_text(
            "✅ قیمت محصول با موفقیت تغییر کرد.",
            reply_markup=get_admin_menu_keyboard(),
        )

        return ConversationHandler.END

    except Exception:

        logger.exception(
            "خطا در تغییر قیمت"
        )

        await update.message.reply_text(
            "❌ خطا در تغییر قیمت محصول."
        )

        return EDIT_PRICE


# =========================================================
# تغییر توضیحات
# =========================================================

async def edit_description(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    new_description = update.message.text.strip()

    if not new_description:
        new_description = "توضیحی ثبت نشده است."

    code = context.user_data.get("edit_code")

    try:

        (
            supabase
            .table("products")
            .update({
                "description": new_description
            })
            .eq("code", code)
            .execute()
        )

        context.user_data.clear()

        await update.message.reply_text(
            "✅ توضیحات محصول با موفقیت تغییر کرد.",
            reply_markup=get_admin_menu_keyboard(),
        )

        return ConversationHandler.END

    except Exception:

        logger.exception(
            "خطا در تغییر توضیحات"
        )

        await update.message.reply_text(
            "❌ خطا در تغییر توضیحات."
        )

        return EDIT_DESC


# =========================================================
# تغییر عکس
# =========================================================

async def edit_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message.photo:

        await update.message.reply_text(
            "❌ لطفاً یک عکس معتبر ارسال کنید."
        )

        return EDIT_PHOTO

    photo_file_id = update.message.photo[-1].file_id

    code = context.user_data.get("edit_code")

    try:

        (
            supabase
            .table("products")
            .update({
                "image_url": photo_file_id
            })
            .eq("code", code)
            .execute()
        )

        context.user_data.clear()

        await update.message.reply_text(
            "✅ عکس محصول با موفقیت تغییر کرد.",
            reply_markup=get_admin_menu_keyboard(),
        )

        return ConversationHandler.END

    except Exception:

        logger.exception(
            "خطا در تغییر عکس"
        )

        await update.message.reply_text(
            "❌ خطا در تغییر عکس محصول."
        )

        return EDIT_PHOTO


# =========================================================
# شروع حذف محصول
# =========================================================

async def start_delete_product(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not is_admin(query.from_user.id):

        await query.answer(
            "❌ شما اجازه دسترسی ندارید.",
            show_alert=True
        )

        return ConversationHandler.END

    await query.answer()

    context.user_data.clear()

    await query.edit_message_text(
        "🗑 <b>حذف محصول</b>\n\n"
        "🔖 کد محصولی که می‌خواهید حذف کنید را وارد کنید:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard(),
    )

    return DELETE_SELECT_CODE


# =========================================================
# پیدا کردن محصول برای حذف
# =========================================================

async def delete_select_code(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    code = update.message.text.strip()

    try:

        result = (
            supabase
            .table("products")
            .select("*")
            .eq("code", code)
            .limit(1)
            .execute()
        )

        if not result.data:

            await update.message.reply_text(
                "❌ محصولی با این کد پیدا نشد.\n\n"
                "لطفاً دوباره کد را وارد کنید:"
            )

            return DELETE_SELECT_CODE

        product = result.data[0]

        context.user_data["delete_code"] = code

        text = (
            "⚠️ <b>تأیید حذف محصول</b>\n\n"
            f"💎 نام: {safe_text(product.get('name', '-'))}\n"
            f"🔖 کد: {safe_text(product.get('code', '-'))}\n"
            f"💰 قیمت: {format_price(product.get('price'))}\n\n"
            "آیا مطمئن هستید که می‌خواهید این محصول را حذف کنید؟"
        )

        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_delete_confirm_keyboard(),
        )

        return DELETE_CONFIRM

    except Exception:

        logger.exception(
            "خطا در جستجوی محصول برای حذف"
        )

        await update.message.reply_text(
            "❌ خطا در جستجوی محصول."
        )

        return DELETE_SELECT_CODE


# =========================================================
# تایید حذف
# =========================================================

async def delete_confirm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    await query.answer()

    # لغو حذف
    if query.data == "delete_confirm_no":

        context.user_data.clear()

        await query.edit_message_text(
            "❌ حذف محصول لغو شد.",
            reply_markup=get_admin_menu_keyboard(),
        )

        return ConversationHandler.END

    # تایید حذف
    if query.data == "delete_confirm_yes":

        code = context.user_data.get("delete_code")

        try:

            (
                supabase
                .table("products")
                .delete()
                .eq("code", code)
                .execute()
            )

            context.user_data.clear()

            await query.edit_message_text(
                "✅ محصول با موفقیت حذف شد.",
                reply_markup=get_admin_menu_keyboard(),
            )

            return ConversationHandler.END

        except Exception:

            logger.exception(
                "خطا در حذف محصول"
            )

            context.user_data.clear()

            await query.edit_message_text(
                "❌ خطا در حذف محصول.",
                reply_markup=get_admin_menu_keyboard(),
            )

            return ConversationHandler.END

    return DELETE_CONFIRM


# =========================================================
# لغو عملیات
# =========================================================

async def cancel_operation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    if is_admin(query.from_user.id):

        await query.edit_message_text(
            "❌ عملیات لغو شد.",
            reply_markup=get_admin_menu_keyboard(),
        )

    else:

        await query.edit_message_text(
            "❌ عملیات لغو شد.",
            reply_markup=get_main_menu_keyboard(),
        )

    return ConversationHandler.END


# =========================================================
# مدیریت خطا
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "Exception while handling update:",
        exc_info=context.error
    )


# =========================================================
# ساخت ConversationHandler
# =========================================================

def build_conversation_handler():

    return ConversationHandler(

        entry_points=[
            CallbackQueryHandler(
                start_add_product,
                pattern="^admin_add_product$"
            ),

            CallbackQueryHandler(
                start_edit_product,
                pattern="^admin_edit_product$"
            ),

            CallbackQueryHandler(
                start_delete_product,
                pattern="^admin_delete_product$"
            ),

            CallbackQueryHandler(
                start_checkout,
                pattern="^start_checkout$"
            ),

            CallbackQueryHandler(
                start_product_lookup,
                pattern="^user_view_products$"
            ),
        ],

        states={

            # -------------------------
            # افزودن محصول
            # -------------------------

            ADD_CODE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_code
                )
            ],

            ADD_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_name
                )
            ],

            ADD_PRICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_price
                )
            ],

            ADD_DESC: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_description
                )
            ],

            ADD_PHOTO: [
                MessageHandler(
                    filters.PHOTO,
                    add_photo
                )
            ],

            # -------------------------
            # ویرایش
            # -------------------------

            EDIT_SELECT_CODE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    edit_select_code
                )
            ],

            EDIT_MENU: [
                CallbackQueryHandler(
                    edit_menu,
                    pattern="^(edit_name|edit_price|edit_desc|edit_photo|admin_panel)$"
                )
            ],

            EDIT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    edit_name
                )
            ],

            EDIT_PRICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    edit_price
                )
            ],

            EDIT_DESC: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    edit_description
                )
            ],

            EDIT_PHOTO: [
                MessageHandler(
                    filters.PHOTO,
                    edit_photo
                )
            ],

            # -------------------------
            # حذف
            # -------------------------

            DELETE_SELECT_CODE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    delete_select_code
                )
            ],

            DELETE_CONFIRM: [
                CallbackQueryHandler(
                    delete_confirm,
                    pattern="^delete_confirm_(yes|no)$"
                )
            ],

            CHECKOUT_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    checkout_name
                )
            ],

            CHECKOUT_PHONE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    checkout_phone
                )
            ],

            CHECKOUT_ADDRESS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    checkout_address
                )
            ],

            CHECKOUT_CONFIRM: [
                CallbackQueryHandler(
                    checkout_confirm,
                    pattern="^(checkout_confirm|checkout_restart|checkout_cancel)$"
                )
            ],

            USER_PRODUCT_CODE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    find_product_by_code
                )
            ],
        },

        fallbacks=[
            CallbackQueryHandler(
                cancel_operation,
                pattern="^cancel_operation$"
            ),

            CommandHandler(
                "start",
                start
            ),
        ],

        allow_reentry=True,
    )


# =========================================================
# Handler دکمه‌های عمومی
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    # --------------------------------
    # سبد خرید و محصولات
    # --------------------------------

    if data == "view_cart":
        await show_cart(update, context)
        return

    if data.startswith("add_to_cart:"):
        await add_product_to_cart(update, context)
        return

    if data.startswith("product_detail:"):
        await product_detail(update, context)
        return

    if data.startswith(("cart_inc:", "cart_dec:", "cart_remove:")):
        await cart_change(update, context)
        return

    if data == "cart_clear":
        await clear_cart(update, context)
        return

    if data == "start_checkout":
        await start_checkout(update, context)
        return

    # --------------------------------
    # بازگشت به منوی اصلی
    # --------------------------------

    if data == "back_to_main":

        await query.answer()

        for key in list(context.user_data.keys()):
            if key != "cart":
                context.user_data.pop(key, None)

        await query.edit_message_text(
            "✨ <b>به منوی اصلی هیوه برگشتید.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard(),
        )

        return

    # --------------------------------
    # مشاهده محصولات
    # --------------------------------

    if data == "user_view_products":

        await start_product_lookup(update, context)
        return

    if data == "admin_orders":
        if not is_admin(user_id):
            await query.answer("❌ دسترسی ندارید.", show_alert=True)
            return

        await query.answer()
        await query.edit_message_text(
            "📋 <b>مدیریت سفارش‌ها</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_orders_keyboard(),
        )
        return

    if data in ("admin_orders_pending", "admin_orders_all"):
        await show_admin_orders(update, context)
        return

    if data.startswith("admin_order:"):
        await show_admin_order(update, context)
        return

    if data.startswith("order_status:"):
        await update_order_status(update, context)
        return

    # --------------------------------
    # پنل مدیریت
    # --------------------------------

    if data == "admin_panel":

        if not is_admin(user_id):

            await query.answer(
                "❌ شما دسترسی به پنل مدیریت ندارید.",
                show_alert=True
            )

            return

        await query.answer()

        context.user_data.clear()

        await query.edit_message_text(
            "🛠 <b>پنل مدیریت هیوه</b>\n\n"
            "لطفاً یکی از گزینه‌ها را انتخاب کنید:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_menu_keyboard(),
        )

        return


# =========================================================
# تابع اصلی
# =========================================================

def main():

    # =====================================================
    # مهم:
    # ساخت Event Loop برای Python 3.14
    # =====================================================

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # =====================================================
    # ساخت Application
    # =====================================================

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # =====================================================
    # Conversation Handler
    # =====================================================

    application.add_handler(
        build_conversation_handler()
    )

    # =====================================================
    # /start
    # =====================================================

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # =====================================================
    # دکمه‌های عمومی
    # =====================================================

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # =====================================================
    # Error Handler
    # =====================================================

    application.add_error_handler(
        error_handler
    )

    # =====================================================
    # اجرای ربات
    # =====================================================

    logger.info(
        "🤖 ربات هیوه با موفقیت آماده اجرا شد..."
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# سرور سلامت برای Render Free Web Service
# =========================================================

health_app = Flask(__name__)


@health_app.route("/", methods=["GET"])
def health_check():
    return "HIVEH bot is running", 200


@health_app.route("/health", methods=["GET"])
def health_endpoint():
    return "OK", 200


def run_health_server():
    port = int(os.environ.get("PORT", "10000"))
    health_app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


# =========================================================
# اجرای برنامه
# =========================================================

if __name__ == "__main__":
    # Render Web Service برای رایگان ماندن نیاز به یک پورت باز دارد.
    # سرور سلامت در Thread جدا اجرا می‌شود و Telegram polling مستقل می‌ماند.
    threading.Thread(
        target=run_health_server,
        daemon=True,
        name="render-health-server",
    ).start()

    main()