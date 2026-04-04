from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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

def kb_main_menu(*, is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="🛍 Магазин",
            web_app=WebAppInfo(url=MINI_APP_URL),
        ),
    )
    b.row(
        InlineKeyboardButton(text="📜 Сертификаты", callback_data="menu:certs"),
        InlineKeyboardButton(text="💬 Отзывы", callback_data="menu:reviews"),
    )
    b.row(
        InlineKeyboardButton(text="🚛 Доставка", callback_data="menu:delivery"),
        InlineKeyboardButton(text="🤖 ИИ-Консультант", callback_data="menu:ai"),
    )
    if is_admin:
        b.row(
            InlineKeyboardButton(text="🛠 Админка", callback_data="menu:admin"),
        )
    return b.as_markup()


def kb_admin_order_actions(
    order_id: int,
    *,
    context: str = "",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    suffix = f":{context}" if context else ""
    b.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"admord:c:{order_id}{suffix}",
        ),
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"admord:x:{order_id}{suffix}",
        ),
    )
    b.row(
        InlineKeyboardButton(
            text="📌 Пометить заказ",
            callback_data=f"admord:p:{order_id}{suffix}",
        ),
    )
    if context:
        b.row(
            InlineKeyboardButton(text="⬅ Назад", callback_data=f"admo:list:{context}"),
        )
        b.row(
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"),
        )
    return b.as_markup()


def kb_admin_order_after_preparation(
    order_id: int,
    *,
    context: str = "",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    suffix = f":{context}" if context else ""
    b.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"admord:c:{order_id}{suffix}",
        ),
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"admord:x:{order_id}{suffix}",
        ),
    )
    b.row(
        InlineKeyboardButton(
            text="В обработке...",
            callback_data=f"admord:i:{order_id}{suffix}",
        ),
    )
    if context:
        b.row(
            InlineKeyboardButton(text="⬅ Назад", callback_data=f"admo:list:{context}"),
        )
        b.row(
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"),
        )
    return b.as_markup()


def kb_admin_order_confirmed_only(
    order_id: int,
    *,
    context: str = "",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    suffix = f":{context}" if context else ""
    b.row(
        InlineKeyboardButton(
            text="✅ Подтвержден",
            callback_data=f"admord:i:{order_id}{suffix}",
        ),
    )
    if context:
        b.row(
            InlineKeyboardButton(text="⬅ Назад", callback_data=f"admo:list:{context}"),
        )
        b.row(
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"),
        )
    return b.as_markup()


def kb_admin_order_cancelled_only(
    order_id: int,
    *,
    context: str = "",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    suffix = f":{context}" if context else ""
    b.row(
        InlineKeyboardButton(
            text="❌ Отменён",
            callback_data=f"admord:i:{order_id}{suffix}",
        ),
    )
    if context:
        b.row(
            InlineKeyboardButton(text="⬅ Назад", callback_data=f"admo:list:{context}"),
        )
        b.row(
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"),
        )
    return b.as_markup()


def kb_promo_list(
    rows: list[tuple[str, int]],
    *,
    back_callback: str = "admp:promo",
) -> InlineKeyboardMarkup:
    """Одна кнопка на строку: код (процент) — callback admprm:CODE."""
    b = InlineKeyboardBuilder()
    for code, pct in rows:
        b.row(
            InlineKeyboardButton(
                text=f"{code} ({pct}%)",
                callback_data=f"admprm:{code}",
            ),
        )
    b.row(InlineKeyboardButton(text="⬅ Назад", callback_data=back_callback))
    b.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"))
    return b.as_markup()


def kb_product_stock(
    rows: list[tuple[str, str, bool]],
    *,
    back_callback: str = "admp:home",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for product_id, title, in_stock in rows:
        b.row(
            InlineKeyboardButton(
                text=f"{'✅' if in_stock else '❌'} {title}",
                callback_data=f"admstk:{product_id}:{0 if in_stock else 1}",
            ),
        )
    b.row(InlineKeyboardButton(text="⬅ Назад", callback_data=back_callback))
    b.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"))
    return b.as_markup()


def kb_admin_panel_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📦 Наличие товара", callback_data="admp:stock"),
        InlineKeyboardButton(text="🎟 Промокоды", callback_data="admp:promo"),
    )
    b.row(
        InlineKeyboardButton(text="🧾 Заказы", callback_data="admp:orders"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admp:stats"),
    )
    b.row(
        InlineKeyboardButton(text="📣 Рассылка", callback_data="admp:broadcast"),
    )
    b.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"))
    return b.as_markup()


def kb_admin_panel_orders_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🆕 Новые", callback_data="admo:list:new"),
        InlineKeyboardButton(text="📦 Подготовка", callback_data="admo:list:prep"),
    )
    b.row(
        InlineKeyboardButton(text="🗂 История", callback_data="admo:list:done"),
    )
    b.row(InlineKeyboardButton(text="⬅ Назад", callback_data="admp:home"))
    b.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"))
    return b.as_markup()


def kb_admin_panel_orders_list(
    rows: list[tuple[int, str]],
    *,
    context: str,
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for order_id, label in rows:
        b.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"admo:open:{order_id}:{context}",
            ),
        )
    b.row(InlineKeyboardButton(text="⬅ Назад", callback_data="admp:orders"))
    b.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"))
    return b.as_markup()


def kb_admin_panel_promo_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📋 Список кодов", callback_data="admp:promo:list"),
    )
    b.row(
        InlineKeyboardButton(text="➕ Добавить", callback_data="admp:promo:add"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data="admp:promo:del"),
    )
    b.row(InlineKeyboardButton(text="⬅ Назад", callback_data="admp:home"))
    b.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"))
    return b.as_markup()


def kb_admin_panel_stats() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="admp:stats"),
    )
    b.row(InlineKeyboardButton(text="⬅ Назад", callback_data="admp:home"))
    b.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"))
    return b.as_markup()


def kb_admin_panel_broadcast_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✍️ Ввести текст акции", callback_data="admp:broadcast:start"),
    )
    b.row(InlineKeyboardButton(text="⬅ Назад", callback_data="admp:home"))
    b.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"))
    return b.as_markup()


def kb_admin_panel_cancel(back_callback: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="⬅ Назад", callback_data=back_callback))
    b.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="admp:exit"))
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
