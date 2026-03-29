import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import database as db
from config import ADMIN_ID
import messages as msg
from keyboards import (
    kb_admin_order_after_preparation,
    kb_admin_order_cancelled_only,
    kb_admin_order_confirmed_only,
    kb_promo_list,
)
from md2 import escape_md2

log = logging.getLogger(__name__)

router = Router(name="admin")

_ACTION_SUFFIX = {
    db.STATUS_CONFIRMED: (
        "\n\n*Решение администратора:* ✅ *Подтверждён* "
        "\\— заказ учитывается в `/admin_stats`\\."
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


@router.message(Command("admin_stats"))
async def admin_stats(message: Message) -> None:
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
    )


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
    if len(parts) != 3 or parts[0] != "admord":
        await cq.answer()
        return
    action, oid_s = parts[1], parts[2]
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
        next_kb = kb_admin_order_after_preparation(oid)
    elif new_status == db.STATUS_CONFIRMED:
        next_kb = kb_admin_order_confirmed_only(oid)
    elif new_status == db.STATUS_CANCELLED:
        next_kb = kb_admin_order_cancelled_only(oid)
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
    """/add_promo MEKKA10 10 Абдулла"""
    if not text:
        return None
    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    rest = parts[1].split()
    if len(rest) < 2:
        return None
    code = rest[0].strip().upper()
    try:
        discount = int(rest[1])
    except ValueError:
        return None
    name = " ".join(rest[2:]).strip() if len(rest) > 2 else ""
    return code, discount, name


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


@router.message(Command("add_promo"))
async def cmd_add_promo(message: Message) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    parsed = _parse_add_promo(message.text or "")
    if not parsed:
        await message.answer(
            "Использование: /add_promo КОД СКИДКА ИМЯ\n"
            "Пример: /add_promo MEKKA10 10 Абдулла",
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


@router.message(Command("promo_list"))
async def cmd_promo_list(message: Message) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    rows = await db.list_promos()
    if not rows:
        await message.answer(
            "Промокодов пока нет. Создайте: /add_promo КОД СКИДКА ИМЯ",
            parse_mode=None,
        )
        return
    pairs = [(r["code"], r["discount_percent"]) for r in rows]
    await message.answer(
        "Промокоды (нажмите для отчёта):",
        reply_markup=kb_promo_list(pairs),
        parse_mode=None,
    )


@router.message(Command("promo_info"))
async def cmd_promo_info(message: Message) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /promo_info КОД", parse_mode=None)
        return
    code = parts[1].strip()
    await _send_promo_report(message, code)


@router.callback_query(F.data.startswith("admprm:"))
async def cb_promo_from_list(cq: CallbackQuery) -> None:
    if not cq.from_user or cq.from_user.id != ADMIN_ID:
        await cq.answer(msg.ADMIN_NO_ACCESS_PLAIN, show_alert=True)
        return
    if not cq.data or len(cq.data) < 8:
        await cq.answer()
        return
    code = cq.data[7:]
    await cq.answer()
    await _send_promo_report(cq, code)


@router.message(Command("del_promo"))
async def cmd_del_promo(message: Message) -> None:
    if not message.from_user or message.from_user.id != ADMIN_ID:
        await message.answer(msg.admin_no_access())
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Использование: /del_promo КОД", parse_mode=None)
        return
    code = parts[1].strip()
    ok = await db.delete_promo(code)
    if ok:
        await message.answer(f"Промокод {code.upper()} удалён.", parse_mode=None)
    else:
        await message.answer(f"Промокод «{code}» не найден.", parse_mode=None)
