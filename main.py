import asyncio
import html
import logging
import os
from decimal import Decimal, InvalidOperation

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
) = range(13)


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
# نمایش محصولات
# =========================================================

async def show_products(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    try:
        response = (
            supabase
            .table("products")
            .select("*")
            .order("id", desc=False)
            .execute()
        )

        products = response.data or []

        if not products:
            await query.edit_message_text(
                "📦 در حال حاضر محصولی در فروشگاه ثبت نشده است.",
                reply_markup=get_main_menu_keyboard(),
            )
            return ConversationHandler.END

        try:
            await query.message.delete()
        except Exception:
            pass

        for product in products:
            caption = product_caption(product)
            image_id = product.get("image_url")
            product_id = product.get("id")

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "💎 مشاهده جزئیات",
                        callback_data=f"product_detail:{product_id}"
                    ),
                    InlineKeyboardButton(
                        "🛒 افزودن به سبد",
                        callback_data=f"add_to_cart:{product_id}"
                    ),
                ]
            ])

            if image_id:
                try:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=image_id,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
                    )
                except Exception as e:
                    logger.error(f"خطا در ارسال عکس محصول: {e}")
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

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="✨ <b>برای ادامه یکی از گزینه‌های زیر را انتخاب کنید:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard(),
        )

    except Exception:
        logger.exception("خطا در دریافت محصولات")
        try:
            await query.edit_message_text(
                "❌ خطایی هنگام دریافت محصولات رخ داد.",
                reply_markup=get_main_menu_keyboard(),
            )
        except Exception:
            pass

    return ConversationHandler.END

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

        await show_products(
            update,
            context
        )

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
# اجرای برنامه
# =========================================================

if __name__ == "__main__":
    main()