import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from catalog import MINI_APP_PRODUCT_TITLES
import database as db
from config import ADMIN_ID, WELCOME_IMAGE_URL
import messages as msg
from handlers.ai import generate_ai_promo_message
from keyboards import (
    kb_admin_panel_broadcast_menu,
    kb_admin_panel_cancel,
    kb_admin_panel_main,
    kb_admin_panel_orders_list,
    kb_admin_panel_orders_menu,
    kb_admin_order_after_preparation,
    kb_admin_order_cancelled_only,
    kb_admin_order_confirmed_only,
    kb_admin_panel_promo_menu,
    kb_admin_panel_stats,
    kb_admin_order_actions,
    kb_main_menu,
    kb_promo_list,
    kb_product_stock,
)
from media_input import input_photo
from md2 import escape_md2
from states import AdminPanel

log = logging.getLogger(__name__)

router = Router(name="admin")

_ACTION_SUFFIX = {
    db.STATUS_CONFIRMED: (
        "\n\n*Решение администратора:* ✅ *Подтверждён* "
        "\\— заказ учитывается в `/stats`\\."
    ),
    db.STATUS_CANCELLED: (
        "\n\n*Решение администратора:* ❌ *Отменён* "
        "\\— в статистику не входит\\."
    ),
    db.STATUS_PREPARATION: (
        "\n\n*Решение администратора:* 📦 *Подготовка* "
        "\\— в статистике не учитывается, пока не нажмёте *Подтвердить*\\."
    ),
}


def _stock_panel_text(rows: list[dict]) -> str:
    available = sum(1 for row in rows if row["in_stock"])
    unavailable = len(rows) - available
    return (
        "Управление наличием товаров\n\n"
        "Нажмите на товар, чтобы переключить статус.\n"
        f"✅ В наличии: {available}\n"
        f"❌ Нет в наличии: {unavailable}"
    )


def _stock_panel_markup(rows: list[dict]):
    return kb_product_stock(
        [
            (str(row["id"]), str(row["title"]), bool(row["in_stock"]))
            for row in rows
        ]
    )


def _admin_main_text() -> str:
    return (
        "Админ-панель\n\n"
        "Выберите раздел ниже. Все основные действия доступны через кнопки, без ввода команд."
    )


def _promo_menu_text() -> str:
    return (
        "Промокоды\n\n"
        "Здесь можно посмотреть список кодов, добавить новый или удалить старый.\n"
        "Чтобы открыть отчёт по коду, зайдите в список и нажмите на нужный промокод."
    )


def _broadcast_menu_text() -> str:
    return (
        "Рассылка\n\n"
        "Бот сгенерирует персонализированные сообщения по истории заказов и отправит их пользователям.\n"
        "Нажмите кнопку ниже, затем отправьте текст акции одним сообщением."
    )


def _promo_add_prompt_text() -> str:
    return (
        "Добавление или обновление промокода\n\n"
        "Отправьте одной строкой: КОД СКИДКА ИМЯ\n"
        "Пример: MEKKA10 10 Абдулла"
    )


def _promo_delete_prompt_text() -> str:
    return (
        "Удаление промокода\n\n"
        "Отправьте код промокода одним сообщением.\n"
        "Пример: MEKKA10"
    )


def _broadcast_prompt_text() -> str:
    return (
        "Текст рассылки\n\n"
        "Отправьте текст акции одним сообщением.\n"
        "Пример: Скидка 10% на баранину сегодня"
    )


def _promo_list_text(rows: list[dict]) -> str:
    if not rows:
        return "Промокодов пока нет. Нажмите «Добавить» и отправьте данные нового кода."
    return "Промокоды\n\nНажмите на код, чтобы открыть отчёт по нему."


def _orders_menu_text() -> str:
    return (
        "Заказы\n\n"
        "Выберите нужный список: новые, в подготовке или история обработанных заказов."
    )


def _order_status_label(status: str) -> str:
    mapping = {
        db.STATUS_PENDING_ADMIN: "Новый",
        db.STATUS_PREPARATION: "Подготовка",
        db.STATUS_CONFIRMED: "Подтверждён",
        db.STATUS_CANCELLED: "Отменён",
    }
    return mapping.get(status, status or "—")


def _orders_filter_meta(filter_key: str) -> tuple[str, list[str]]:
    mapping = {
        "new": ("Новые заказы", [db.STATUS_PENDING_ADMIN]),
        "prep": ("Подготовка", [db.STATUS_PREPARATION]),
        "done": ("История заказов", [db.STATUS_CONFIRMED, db.STATUS_CANCELLED]),
    }
    return mapping.get(filter_key, mapping["new"])


def _order_list_button_text(row: dict) -> str:
    oid = int(row.get("id") or 0)
    city = str(row.get("city") or "—").strip() or "—"
    goal = str(row.get("goal") or "—").strip() or "—"
    return f"#{oid} • {city} • {goal}"


def _orders_list_text(title: str, rows: list[dict]) -> str:
    if not rows:
        return f"{title}\n\nСписок пуст."
    lines = [title, "", "Откройте заказ кнопкой ниже:"]
    for row in rows:
        oid = int(row.get("id") or 0)
        city = str(row.get("city") or "—").strip() or "—"
        goal = str(row.get("goal") or "—").strip() or "—"
        status = _order_status_label(str(row.get("status") or ""))
        lines.append(f"#{oid} • {status} • {city} • {goal}")
    return "\n".join(lines)


def _format_order_timestamp(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return "—"
    return s.replace("T", " ").split(".")[0]


def _panel_order_text(order: dict) -> str:
    promo_used = str(order.get("promo_used") or "").strip()
    comment = str(order.get("comment") or "").strip() or "—"
    username = str(order.get("username") or "").strip()
    client = f"@{username}" if username else "—"
    lines = [
        f"📦 Заказ #{int(order.get('id') or 0)}",
        f"📌 Статус: {_order_status_label(str(order.get('status') or ''))}",
        f"🕒 Дата: {_format_order_timestamp(str(order.get('timestamp') or ''))}",
        f"🎯 Цель: {str(order.get('goal') or '—')}",
        f"👤 Клиент: {client}",
        f"📞 Телефон: {str(order.get('phone') or '—')}",
        f"📍 Город: {str(order.get('city') or '—')}",
        f"🏠 Адрес: {str(order.get('address') or '—')}",
        f"🚚 Доставка: {str(order.get('delivery_type') or '—')}",
        f"💳 Оплата: {str(order.get('payment') or '—')}",
        f"🧾 Товары: {str(order.get('product') or '—')}",
        f"🔢 Кол-во: {str(order.get('quantity') or '—')}",
    ]
    if promo_used:
        lines.append(f"🎟 Промокод: {promo_used}")
        lines.append(f"💸 Скидка: {str(order.get('discount_amount') or '0')} ₽")
        lines.append(
            "💰 К оплате: "
            f"{str(order.get('final_price') or order.get('total_price') or '0')} ₽ "
            f"(без скидки: {str(order.get('total_price') or '0')} ₽)"
        )
    else:
        lines.append(f"💰 Сумма: {str(order.get('total_price') or '0')} ₽")
    lines.append(f"💬 Комментарий: {comment}")
    return "\n".join(lines)


def _order_detail_markup(order_id: int, status: str, context: str):
    if status == db.STATUS_PREPARATION:
        return kb_admin_order_after_preparation(order_id, context=context)
    if status == db.STATUS_CONFIRMED:
        return kb_admin_order_confirmed_only(order_id, context=context)
    if status == db.STATUS_CANCELLED:
        return kb_admin_order_cancelled_only(order_id, context=context)
    return kb_admin_order_actions(order_id, context=context)


async def _show_admin_panel(
    message: Message,
    state: FSMContext,
    text: str,
    *,
    reply_markup,
    parse_mode: str | None = None,
) -> None:
    await state.set_state(AdminPanel.main)
    await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


async def _edit_admin_panel(
    cq: CallbackQuery,
    state: FSMContext,
    text: str,
    *,
    reply_markup,
    parse_mode: str | None = None,
) -> None:
    if not cq.message:
        await cq.answer()
        return
    await state.set_state(AdminPanel.main)
    try:
        await cq.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            log.exception("Не удалось обновить админ-панель: %s", e)
    await cq.answer()


def _parse_add_promo_payload(text: str) -> tuple[str, int, str] | None:
    parts = str(text or "").strip().split()
    if len(parts) < 2:
        return None
    code = parts[0].strip().upper()
    try:
        discount = int(parts[1])
    except ValueError:
        return None
    name = " ".join(parts[2:]).strip() if len(parts) > 2 else ""
    return code, discount, name
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    await _show_admin_panel(
        message,
        state,
        _admin_main_text(),
        reply_markup=kb_admin_panel_main(),
        parse_mode=None,
    )


@router.callback_query(F.data == "menu:admin")
async def open_admin_panel_from_menu(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID or not cq.message:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    await state.set_state(AdminPanel.main)
    await cq.answer()
    await cq.message.answer(
        _admin_main_text(),
        reply_markup=kb_admin_panel_main(),
        parse_mode=None,
    )


@router.callback_query(F.data == "admp:home")
async def cb_admin_panel_home(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    await _edit_admin_panel(
        cq,
        state,
        _admin_main_text(),
        reply_markup=kb_admin_panel_main(),
        parse_mode=None,
    )


@router.callback_query(F.data == "admp:exit")
async def cb_admin_panel_exit(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID or not cq.message:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    await state.clear()
    await cq.answer()
    await cq.message.answer_photo(
        photo=input_photo(WELCOME_IMAGE_URL, folder_key="welcome"),
        caption=msg.main_menu_caption(),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=kb_main_menu(is_admin=True),
    )


@router.callback_query(F.data == "admp:promo")
async def cb_admin_panel_promo(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    await _edit_admin_panel(
        cq,
        state,
        _promo_menu_text(),
        reply_markup=kb_admin_panel_promo_menu(),
        parse_mode=None,
    )


@router.callback_query(F.data == "admp:orders")
async def cb_admin_panel_orders(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    await _edit_admin_panel(
        cq,
        state,
        _orders_menu_text(),
        reply_markup=kb_admin_panel_orders_menu(),
        parse_mode=None,
    )


@router.callback_query(F.data.startswith("admo:list:"))
async def cb_admin_orders_list(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    filter_key = (cq.data or "").split(":", 2)[2] if cq.data else "new"
    title, statuses = _orders_filter_meta(filter_key)
    rows = await db.list_orders_by_statuses(statuses)
    await _edit_admin_panel(
        cq,
        state,
        _orders_list_text(title, rows),
        reply_markup=kb_admin_panel_orders_list(
            [(int(row["id"]), _order_list_button_text(row)) for row in rows],
            context=filter_key,
        ),
        parse_mode=None,
    )


@router.callback_query(F.data.startswith("admo:open:"))
async def cb_admin_order_open(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    if not cq.data:
        await cq.answer()
        return
    parts = cq.data.split(":")
    if len(parts) != 4:
        await cq.answer()
        return
    try:
        order_id = int(parts[2])
    except ValueError:
        await cq.answer()
        return
    context = parts[3].strip() or "new"
    order = await db.get_order_details(order_id)
    if not order:
        await cq.answer("Заказ не найден.", show_alert=True)
        return
    await _edit_admin_panel(
        cq,
        state,
        _panel_order_text(order),
        reply_markup=_order_detail_markup(order_id, str(order.get("status") or ""), context),
        parse_mode=None,
    )


@router.callback_query(F.data == "admp:promo:list")
async def cb_admin_panel_promo_list(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    rows = await db.list_promos()
    pairs = [(r["code"], r["discount_percent"]) for r in rows]
    await _edit_admin_panel(
        cq,
        state,
        _promo_list_text(rows),
        reply_markup=kb_promo_list(pairs),
        parse_mode=None,
    )


@router.callback_query(F.data == "admp:promo:add")
async def cb_admin_panel_promo_add(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    if not cq.message:
        await cq.answer()
        return
    await state.set_state(AdminPanel.waiting_promo_add)
    await cq.message.edit_text(
        _promo_add_prompt_text(),
        reply_markup=kb_admin_panel_cancel("admp:promo"),
        parse_mode=None,
    )
    await cq.answer()


@router.callback_query(F.data == "admp:promo:del")
async def cb_admin_panel_promo_delete(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    if not cq.message:
        await cq.answer()
        return
    await state.set_state(AdminPanel.waiting_promo_delete)
    await cq.message.edit_text(
        _promo_delete_prompt_text(),
        reply_markup=kb_admin_panel_cancel("admp:promo"),
        parse_mode=None,
    )
    await cq.answer()


@router.callback_query(F.data == "admp:stats")
async def cb_admin_panel_stats(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    total = await db.count_orders()
    by_goal = await db.orders_by_goal()
    byt = by_goal.get("Быт", 0)
    sport = by_goal.get("Спорт", 0)
    hajj = by_goal.get("Хадж", 0)
    await _edit_admin_panel(
        cq,
        state,
        msg.admin_stats_text(total=total, byt=byt, sport=sport, hajj=hajj),
        reply_markup=kb_admin_panel_stats(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


@router.callback_query(F.data == "admp:broadcast")
async def cb_admin_panel_broadcast(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    await _edit_admin_panel(
        cq,
        state,
        _broadcast_menu_text(),
        reply_markup=kb_admin_panel_broadcast_menu(),
        parse_mode=None,
    )


@router.callback_query(F.data == "admp:broadcast:start")
async def cb_admin_panel_broadcast_start(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    if not cq.message:
        await cq.answer()
        return
    await state.set_state(AdminPanel.waiting_ai_promo_text)
    await cq.message.edit_text(
        _broadcast_prompt_text(),
        reply_markup=kb_admin_panel_cancel("admp:broadcast"),
        parse_mode=None,
    )
    await cq.answer()


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not message.from_user:
        return
    if message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    total = await db.count_orders()
    by_goal = await db.orders_by_goal()
    byt = by_goal.get("Быт", 0)
    sport = by_goal.get("Спорт", 0)
    hajj = by_goal.get("Хадж", 0)
    await message.answer(
        msg.admin_stats_text(total=total, byt=byt, sport=sport, hajj=hajj),
        reply_markup=kb_admin_panel_stats(),
    )


@router.callback_query(F.data == "admp:stock")
async def cb_admin_panel_stock(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    rows = await db.list_product_stock()
    await _edit_admin_panel(
        cq,
        state,
        _stock_panel_text(rows),
        reply_markup=_stock_panel_markup(rows),
        parse_mode=None,
    )


@router.message(Command("stock"))
async def cmd_stock(message: Message) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    rows = await db.list_product_stock()
    await message.answer(
        _stock_panel_text(rows),
        reply_markup=_stock_panel_markup(rows),
        parse_mode=None,
    )


@router.callback_query(F.data.startswith("admstk:"))
async def cb_stock_toggle(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    if not cq.data or not cq.message:
        await cq.answer()
        return
    await state.set_state(AdminPanel.main)
    parts = cq.data.split(":")
    if len(parts) != 3 or parts[0] != "admstk":
        await cq.answer()
        return
    product_id = parts[1].strip()
    in_stock = parts[2] == "1"
    ok = await db.set_product_stock(product_id, in_stock)
    if not ok:
        await cq.answer("Товар не найден.", show_alert=True)
        return
    rows = await db.list_product_stock()
    await cq.message.edit_text(
        _stock_panel_text(rows),
        reply_markup=_stock_panel_markup(rows),
        parse_mode=None,
    )
    title = MINI_APP_PRODUCT_TITLES.get(product_id, "Товар")
    await cq.answer(f"{title}: {'в наличии' if in_stock else 'нет в наличии'}.")


@router.callback_query(F.data.startswith("admord:"))
async def admin_order_decision(cq: CallbackQuery) -> None:
    if not cq.from_user:
        await cq.answer()
        return
    if cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    if not cq.data or not cq.message:
        await cq.answer()
        return
    parts = cq.data.split(":")
    if len(parts) not in (3, 4) or parts[0] != "admord":
        await cq.answer()
        return
    action, oid_s = parts[1], parts[2]
    context = parts[3].strip() if len(parts) == 4 else ""
    try:
        oid = int(oid_s)
    except ValueError:
        await cq.answer()
        return

    if action == "i":
        await cq.answer()
        return

    action_map = {
        "c": db.STATUS_CONFIRMED,
        "x": db.STATUS_CANCELLED,
        "p": db.STATUS_PREPARATION,
    }
    if action not in action_map:
        await cq.answer()
        return
    new_status = action_map[action]
    ok = await db.try_update_order_status(oid, new_status)
    if not ok:
        st = await db.get_order_status(oid)
        if st is None:
            await cq.answer(msg.admin_order_not_found(), show_alert=True)
        else:
            await cq.answer(msg.admin_order_already_done(), show_alert=True)
        return
    suffix = _ACTION_SUFFIX.get(new_status, "")

    if new_status == db.STATUS_PREPARATION:
        next_kb = kb_admin_order_after_preparation(oid, context=context)
    elif new_status == db.STATUS_CONFIRMED:
        next_kb = kb_admin_order_confirmed_only(oid, context=context)
    elif new_status == db.STATUS_CANCELLED:
        next_kb = kb_admin_order_cancelled_only(oid, context=context)
    else:
        next_kb = None

    # cq.message.text — уже «плоский» текст без разметки; суффикс в MDV2.
    # Склеивать без экранирования базы нельзя: символы из данных клиента ломают parse.
    try:
        if cq.message.text is not None:
            new_content = escape_md2(cq.message.text) + suffix
            await cq.message.edit_text(
                text=new_content,
                reply_markup=next_kb,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        elif cq.message.caption is not None:
            new_content = escape_md2(cq.message.caption) + suffix
            await cq.message.edit_caption(
                caption=new_content,
                reply_markup=next_kb,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        else:
            await cq.message.edit_reply_markup(reply_markup=next_kb)
    except Exception as e:
        log.exception("Полное редактирование сообщения заказа не удалось: %s", e)
        try:
            await cq.message.edit_reply_markup(reply_markup=next_kb)
            await cq.answer(msg.admin_buttons_only_plain(), show_alert=True)
            return
        except Exception:
            log.exception("Не удалось обновить даже клавиатуру заказа")
            await cq.answer("Не удалось обновить сообщение.", show_alert=True)  # plain
            return

    await cq.answer(msg.ADMIN_SAVED_PLAIN)


def _parse_add_promo(text: str) -> tuple[str, int, str] | None:
    """/padd MEKKA10 10 Абдулла"""
    if not text:
        return None
    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    return _parse_add_promo_payload(parts[1])


async def _start_ai_promo_broadcast(message: Message, promo_text: str) -> bool:
    status_msg = await message.answer(
        "⏳ Начинаю генерацию и рассылку персонализированных сообщений (работает в фоне)...",
        parse_mode=None,
    )
    users = await db.get_all_users_for_promo()
    if not users:
        await status_msg.edit_text("База пользователей пуста.")
        return False
    asyncio.create_task(_run_background_promo(message, status_msg, users, promo_text))
    return True


async def _send_promo_report(target: Message | CallbackQuery, code: str) -> None:
    info = await db.get_promo_info(code)
    if not info:
        text = f"Промокод «{code}» не найден."
        if isinstance(target, CallbackQuery) and target.message:
            await target.message.answer(text, parse_mode=None)
        else:
            await target.answer(text, parse_mode=None)
        return
    st = await db.get_promo_stats(code)
    rev = st["revenue"]
    text = (
        f"📊 Отчёт по промокоду: {info['code']}\n"
        f"— Партнёр: {info['ambassador_name'] or '—'}\n"
        f"— Скидка: {info['discount_percent']}%\n"
        f"📦 Заказов: {st['count']} шт.\n"
        f"💰 Чистый оборот (в кассе): {rev} ₽\n"
        f"📉 Сумма скидок клиентам: {st['total_discount']} ₽\n"
        f"Для выплаты: долю амбассадора от суммы {rev} ₽ рассчитайте вручную."
    )
    if isinstance(target, CallbackQuery) and target.message:
        await target.message.answer(text, parse_mode=None)
    elif isinstance(target, Message):
        await target.answer(text, parse_mode=None)


@router.message(AdminPanel.waiting_promo_add, F.text, ~F.text.startswith("/"))
async def admin_panel_add_promo_input(message: Message, state: FSMContext) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    parsed = _parse_add_promo_payload(message.text or "")
    if not parsed:
        await message.answer(
            "Не понял формат. Отправьте: КОД СКИДКА ИМЯ\n"
            "Пример: MEKKA10 10 Абдулла",
            parse_mode=None,
        )
        return
    code, discount, name = parsed
    try:
        await db.add_new_promo(code, discount, name)
    except ValueError as e:
        await message.answer(f"Ошибка: {e}", parse_mode=None)
        return
    await message.answer(
        f"Промокод сохранён: {code}, скидка {discount}%, партнёр: {name or '—'}",
        parse_mode=None,
    )
    await _show_admin_panel(
        message,
        state,
        _promo_menu_text(),
        reply_markup=kb_admin_panel_promo_menu(),
        parse_mode=None,
    )


@router.message(AdminPanel.waiting_promo_delete, F.text, ~F.text.startswith("/"))
async def admin_panel_delete_promo_input(message: Message, state: FSMContext) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    code = (message.text or "").strip()
    if not code:
        await message.answer("Отправьте код промокода одним сообщением.", parse_mode=None)
        return
    ok = await db.delete_promo(code)
    if ok:
        await message.answer(f"Промокод {code.upper()} удалён.", parse_mode=None)
    else:
        await message.answer(f"Промокод «{code}» не найден.", parse_mode=None)
    await _show_admin_panel(
        message,
        state,
        _promo_menu_text(),
        reply_markup=kb_admin_panel_promo_menu(),
        parse_mode=None,
    )


@router.message(AdminPanel.waiting_ai_promo_text, F.text, ~F.text.startswith("/"))
async def admin_panel_ai_promo_input(message: Message, state: FSMContext) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    promo_text = (message.text or "").strip()
    if not promo_text:
        await message.answer("Отправьте текст акции одним сообщением.", parse_mode=None)
        return
    await state.set_state(AdminPanel.main)
    await _start_ai_promo_broadcast(message, promo_text)
    await message.answer(
        _broadcast_menu_text(),
        reply_markup=kb_admin_panel_broadcast_menu(),
        parse_mode=None,
    )


@router.message(Command("padd"))
async def cmd_padd(message: Message) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    parsed = _parse_add_promo(message.text or "")
    if not parsed:
        await message.answer(
            "Использование: /padd КОД СКИДКА ИМЯ\n"
            "Пример: /padd MEKKA10 10 Абдулла",
            parse_mode=None,
        )
        return
    code, discount, name = parsed
    try:
        await db.add_new_promo(code, discount, name)
    except ValueError as e:
        await message.answer(f"Ошибка: {e}", parse_mode=None)
        return
    await message.answer(
        f"Промокод сохранён: {code}, скидка {discount}%, партнёр: {name or '—'}",
        parse_mode=None,
    )


@router.message(Command("plist"))
async def cmd_plist(message: Message) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    rows = await db.list_promos()
    if not rows:
        await message.answer(
            "Промокодов пока нет. Создайте: /padd КОД СКИДКА ИМЯ",
            parse_mode=None,
        )
        return
    pairs = [(r["code"], r["discount_percent"]) for r in rows]
    await message.answer(
        "Промокоды (нажмите для отчёта):",
        reply_markup=kb_promo_list(pairs),
        parse_mode=None,
    )


@router.message(Command("pinfo"))
async def cmd_pinfo(message: Message) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /pinfo КОД", parse_mode=None)
        return
    code = parts[1].strip()
    await _send_promo_report(message, code)


@router.callback_query(F.data.startswith("admprm:"))
async def cb_promo_from_list(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    if not cq.data or len(cq.data) < 8:
        await cq.answer()
        return
    await state.set_state(AdminPanel.main)
    code = cq.data[7:]
    await cq.answer()
    await _send_promo_report(cq, code)


@router.message(Command("pdel"))
async def cmd_pdel(message: Message) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /pdel КОД", parse_mode=None)
        return
    code = parts[1].strip()
    ok = await db.delete_promo(code)
    if ok:
        await message.answer(f"Промокод {code.upper()} удалён.", parse_mode=None)
    else:
        await message.answer(f"Промокод «{code}» не найден.", parse_mode=None)

@router.message(Command("aipromo"))
async def cmd_aipromo(message: Message) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /aipromo <текст акции>\nПример: /aipromo Скидка 10% на баранину сегодня", parse_mode=None)
        return

    promo_text = parts[1].strip()
    await _start_ai_promo_broadcast(message, promo_text)

async def _run_background_promo(message: Message, status_msg: Message, users: list[dict], promo_text: str) -> None:
    success_count = 0
    fail_count = 0
    
    # Пакетная отправка: создаем задачи пачками по 5 человек
    batch_size = 5
    for i in range(0, len(users), batch_size):
        batch = users[i:i + batch_size]
        tasks = []
        
        for u in batch:
            tasks.append(_process_single_user_promo(message, u, promo_text))
            
        # Ждем выполнения всей пачки
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results:
            if res is True:
                success_count += 1
            else:
                fail_count += 1
                
        # Минимальная задержка между пачками, чтобы избежать лимитов Telegram (30 msg/sec)
        await asyncio.sleep(0.3)

    await status_msg.edit_text(
        f"✅ Рассылка завершена!\nУспешно отправлено: {success_count}\nОшибок отправки (боты/заблокировали): {fail_count}",
        parse_mode=None
    )

async def _process_single_user_promo(message: Message, user_data: dict, promo_text: str) -> bool:
    user_id = user_data["user_id"]
    username = user_data["username"]
    
    # Получаем историю покупок
    summary = await db.get_user_order_summary(user_id)
    
    # Генерируем уникальный текст
    personalized_text = await generate_ai_promo_message(username, summary, promo_text)
    
    try:
        if message.bot:
            await message.bot.send_message(
                chat_id=user_id,
                text=personalized_text,
                parse_mode=ParseMode.HTML
            )
        return True
    except Exception as e:
        log.error(f"Failed to send ai promo to {user_id}: {e}")
        return False
 
