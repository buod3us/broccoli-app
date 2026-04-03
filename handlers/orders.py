import json
import logging
from typing import Any

from aiogram import Bot, F, Router
from aiogram.enums import ContentType
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

import database as db
from catalog import MINI_APP_PRODUCT_IDS
from config import ADMIN_ID
from keyboards import kb_admin_order_actions
import messages as msg

router = Router(name="orders")

log = logging.getLogger(__name__)


def _str_field(data: dict, key: str) -> str:
    """JSON null / отсутствие ключа → пустая строка (не строка \"None\")."""
    v = data.get(key)
    if v is None:
        return ""
    return str(v).strip()


def _applied_promo_field(data: dict) -> str:
    """Только непустой осмысленный код; пусто → заказ без промокода."""
    v = data.get("applied_promo")
    if v is None:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    low = s.lower()
    if low in ("none", "null", "undefined", "0", "-", "false"):
        return ""
    return s


def _parse_items(raw_items: Any) -> list[dict] | None:
    if not isinstance(raw_items, list) or not raw_items:
        return None
    out: list[dict] = []
    for it in raw_items:
        if not isinstance(it, dict):
            return None
        pid = str(it.get("id", "")).strip()
        if pid not in MINI_APP_PRODUCT_IDS:
            return None
        try:
            qty = int(float(it.get("qty", 0)))
            price = int(round(float(it.get("price", 0))))
        except (TypeError, ValueError):
            return None
        if qty < 1 or price < 0:
            return None
        title = str(it.get("title", pid))
        out.append(
            {"id": pid, "title": title, "qty": qty, "price": price},
        )
    return out


def _summaries(items: list[dict]) -> tuple[str, str]:
    parts = [f"{x['title']} ×{x['qty']}" for x in items]
    product_summary_plain = ", ".join(parts)
    total_qty = sum(x["qty"] for x in items)
    return product_summary_plain, str(total_qty)


def _admin_order_text(
    *,
    order_id: int,
    goal: str,
    username: str | None,
    phone: str,
    city: str,
    address: str,
    total_price: str,
    promo_used: str,
    discount_percent: int,
    discount_amount: str,
    final_price: str,
    comment: str,
) -> str:
    client = f"@{username}" if username else "—"
    cmt = comment if comment else "—"
    lines = [
        "📦 Новый заказ!",
        f"🔢 Номер: {order_id}",
        f"🎯 Цель: {goal}",
        f"👤 Клиент: {client}",
        f"📞 Телефон: {phone}",
        f"📍 Город: {city}",
        f"🏠 Адрес: {address}",
    ]
    if promo_used:
        lines.append(f"🎟 Промокод: {promo_used} (-{discount_percent}%)")
        lines.append(f"💸 Скидка: {discount_amount} ₽")
        lines.append(f"💰 К оплате: {final_price} ₽ (без скидки: {total_price} ₽)")
    else:
        lines.append(f"💰 Сумма: {total_price} ₽")
    lines.append(f"💬 Комментарий: {cmt}")
    return "\n".join(lines)


async def _notify_admin_order(
    bot: Bot,
    *,
    order_id: int,
    goal: str,
    username: str | None,
    phone: str,
    city: str,
    address: str,
    total_price: str,
    promo_used: str,
    discount_percent: int,
    discount_amount: str,
    final_price: str,
    comment: str,
) -> bool:
    if not ADMIN_ID:
        log.warning("ADMIN_ID не задан — уведомление о заказе не отправлено.")
        return False
    text = _admin_order_text(
        order_id=order_id,
        goal=goal,
        username=username,
        phone=phone,
        city=city,
        address=address,
        total_price=total_price,
        promo_used=promo_used,
        discount_percent=discount_percent,
        discount_amount=discount_amount,
        final_price=final_price,
        comment=comment,
    )
    try:
        await bot.send_message(
            ADMIN_ID,
            text,
            parse_mode=None,
            reply_markup=kb_admin_order_actions(order_id),
        )
        log.info("Заказ #%s: уведомление отправлено администратору %s", order_id, ADMIN_ID)
        return True
    except TelegramBadRequest as e:
        log.warning(
            "Заказ #%s: send_message админу с клавиатурой не удался (%s), пробуем без кнопок",
            order_id,
            e,
        )
        try:
            await bot.send_message(ADMIN_ID, text, parse_mode=None)
            log.info("Заказ #%s: уведомление админу отправлено без inline-кнопок", order_id)
            return True
        except TelegramBadRequest as e2:
            log.exception(
                "Заказ #%s: не удалось уведомить администратора %s: %s",
                order_id,
                ADMIN_ID,
                e2,
            )
            return False
    except Exception as e:
        log.exception("Заказ #%s: ошибка при отправке админу: %s", order_id, e)
        return False


@router.message(F.chat.type == "private", F.content_type == ContentType.WEB_APP_DATA)
async def on_web_app_data(message: Message) -> None:
    if not message.from_user or not message.web_app_data:
        log.warning("WEB_APP_DATA: пустое сообщение или нет web_app_data (message_id=%s)", message.message_id)
        return
    uid = message.from_user.id
    log.info("Получены данные Mini App от user_id=%s", uid)
    goal = await db.get_user_goal(uid)
    if not goal:
        await message.answer(msg.webapp_need_goal_plain(), parse_mode=None)
        return
    raw = message.web_app_data.data
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("web_app_data JSON error: %s", raw[:200])
        await message.answer(msg.webapp_bad_data_plain(), parse_mode=None)
        return
    if not isinstance(data, dict):
        log.warning("web_app_data: ожидался объект JSON, user_id=%s", uid)
        await message.answer(msg.webapp_bad_data_plain(), parse_mode=None)
        return

    items = _parse_items(data.get("items"))
    if not items:
        raw_items = data.get("items")
        log.warning(
            "web_app_data: невалидные items или пустая корзина, user_id=%s keys=%s sample=%s",
            uid,
            list(data.keys()),
            repr(raw_items)[:400],
        )
        await message.answer(msg.webapp_bad_data_plain(), parse_mode=None)
        return

    unavailable_ids = await db.get_unavailable_product_ids([item["id"] for item in items])
    if unavailable_ids:
        unavailable_titles = [item["title"] for item in items if item["id"] in unavailable_ids]
        log.info(
            "web_app_data: товары не в наличии user_id=%s ids=%s",
            uid,
            sorted(unavailable_ids),
        )
        await message.answer(
            msg.webapp_out_of_stock_plain(unavailable_titles),
            parse_mode=None,
        )
        return

    phone = _str_field(data, "phone")
    city = _str_field(data, "city")
    address = _str_field(data, "address")
    comment = _str_field(data, "comment")

    # Старое веб-приложение без поля «Адрес» шлёт address_len=0 — заказ не отклоняем.
    if len(address) < 1:
        address = "— (адрес не передан из приложения; уточнить у клиента)"

    # Сумму считаем на сервере по ценам из каталога — так не ломается заказ при
    # расхождении цен в GitHub Pages и в боте или при float в JSON.
    computed_total = sum(x["qty"] * x["price"] for x in items)
    subtotal_str = str(computed_total)
    client_total = data.get("total_price")
    if client_total is not None:
        try:
            ct = int(round(float(client_total)))
            if ct != computed_total:
                log.info(
                    "web_app_data: клиент прислал другую сумму user_id=%s client=%s server=%s",
                    uid,
                    ct,
                    computed_total,
                )
        except (TypeError, ValueError):
            pass

    raw_promo = _applied_promo_field(data)
    promo_used = ""
    discount_amount = "0"
    discount_percent = 0
    final_price = computed_total
    if raw_promo:
        pinf = await db.get_promo_info(raw_promo)
        if not pinf:
            log.warning(
                "web_app_data: неверный промокод user_id=%s code=%r",
                uid,
                raw_promo[:80],
            )
            await message.answer(
                "Промокод недействителен. Оформите заказ без промокода или введите верный код.",
                parse_mode=None,
            )
            return
        discount_percent = int(pinf["discount_percent"])
        final_price = int(round(computed_total * (1 - discount_percent / 100.0)))
        if final_price < 0:
            final_price = 0
        promo_used = str(pinf["code"])
        discount_amount = str(computed_total - final_price)

    final_price_str = str(final_price)

    if len(city) < 2 or len(phone) < 5:
        log.warning(
            "web_app_data: короткие поля user_id=%s city=%r phone_len=%s",
            uid,
            city,
            len(phone),
        )
        await message.answer(msg.webapp_bad_data_fields(), parse_mode=None)
        return

    product_plain, quantity_summary = _summaries(items)
    items_json = json.dumps(items, ensure_ascii=False)

    try:
        oid = await db.create_order_webapp(
            uid,
            goal=goal,
            phone=phone,
            city=city,
            address=address,
            total_price=subtotal_str,
            promo_used=promo_used,
            discount_amount=discount_amount,
            final_price=final_price_str,
            comment=comment,
            product_summary=product_plain,
            quantity_summary=quantity_summary,
            items_json=items_json,
        )
    except Exception:
        log.exception("create_order_webapp")
        await message.answer(msg.webapp_order_error_plain(), parse_mode=None)
        return

    u = message.from_user
    admin_ok = False
    bot = message.bot
    if bot is not None:
        admin_ok = await _notify_admin_order(
            bot,
            order_id=oid,
            goal=goal,
            username=u.username,
            phone=phone,
            city=city,
            address=address,
            total_price=subtotal_str,
            promo_used=promo_used,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            final_price=final_price_str,
            comment=comment,
        )
    reply = msg.order_accepted_plain(city)
    if not admin_ok:
        reply = f"{reply}\n\n{msg.ORDER_ADMIN_NOTIFY_FAILED_PLAIN}"
    await message.answer(reply, parse_mode=None)
