from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import MINI_APP_URL


def kb_goal_choice() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🏠 Быт", callback_data="goal:byt"),
        InlineKeyboardButton(text="🏃‍♂️ Спорт", callback_data="goal:sport"),
    )
    b.row(
        InlineKeyboardButton(
            text="🕋 Хадж / Умра",
            callback_data="goal:hajj",
        ),
    )
    return b.as_markup()


def kb_reply_shop_webapp() -> ReplyKeyboardMarkup:
    """
    Mini App с этой клавиатуры поддерживает Telegram.WebApp.sendData().
    Inline-кнопка web_app sendData НЕ поддерживает (см. документацию Telegram).
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Магазин", web_app=WebAppInfo(url=MINI_APP_URL))],
        ],
        resize_keyboard=True,
    )


def kb_main_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📜 Сертификаты", callback_data="menu:certs"),
        InlineKeyboardButton(text="💬 Отзывы", callback_data="menu:reviews"),
    )
    b.row(
        InlineKeyboardButton(text="🚛 Доставка", callback_data="menu:delivery"),
        InlineKeyboardButton(text="🤖 ИИ-Консультант", callback_data="menu:ai"),
    )
    return b.as_markup()


def kb_admin_order_actions(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"admord:c:{order_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"admord:x:{order_id}",
        ),
    )
    b.row(
        InlineKeyboardButton(
            text="📌 Пометить заказ",
            callback_data=f"admord:p:{order_id}",
        ),
    )
    return b.as_markup()


def kb_admin_order_after_preparation(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"admord:c:{order_id}",
        ),
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"admord:x:{order_id}",
        ),
    )
    b.row(
        InlineKeyboardButton(
            text="В обработке...",
            callback_data=f"admord:i:{order_id}",
        ),
    )
    return b.as_markup()


def kb_admin_order_confirmed_only(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✅ Подтвержден",
            callback_data=f"admord:i:{order_id}",
        ),
    )
    return b.as_markup()


def kb_admin_order_cancelled_only(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="❌ Отменён",
            callback_data=f"admord:i:{order_id}",
        ),
    )
    return b.as_markup()


def kb_promo_list(rows: list[tuple[str, int]]) -> InlineKeyboardMarkup:
    """Одна кнопка на строку: код (процент) — callback admprm:CODE."""
    b = InlineKeyboardBuilder()
    for code, pct in rows:
        b.row(
            InlineKeyboardButton(
                text=f"{code} ({pct}%)",
                callback_data=f"admprm:{code}",
            ),
        )
    return b.as_markup()


def kb_product_stock(rows: list[tuple[str, str, bool]]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for product_id, title, in_stock in rows:
        b.row(
            InlineKeyboardButton(
                text=f"{'✅' if in_stock else '❌'} {title}",
                callback_data=f"admstk:{product_id}:{0 if in_stock else 1}",
            ),
        )
    return b.as_markup()


def kb_ai_exit() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="🔙 Выход в меню",
            callback_data="ai:exit",
        )
    )
    return b.as_markup()
