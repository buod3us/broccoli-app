import json
import logging
from dataclasses import dataclass
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

import database as db
from catalog import MINI_APP_PRODUCT_BY_ID, MINI_APP_PRODUCT_IDS
from config import ADMIN_ID
from keyboards import kb_admin_order_actions
import messages as msg

log = logging.getLogger(__name__)


@dataclass(slots=True)
class OrderProcessingError(Exception):
    public_message: str
    log_message: str = ""

    def __str__(self) -> str:
        return self.log_message or self.public_message


@dataclass(slots=True)
class OrderProcessingResult:
    order_id: int
    user_message: str
    admin_notified: bool


def _str_field(data: dict, key: str) -> str:
    value = data.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _applied_promo_field(data: dict) -> str:
    value = data.get("applied_promo")
    if value is None:
        return ""
    normalized = str(value).strip()
    if not normalized:
        return ""
    if normalized.lower() in {"none", "null", "undefined", "0", "-", "false"}:
        return ""
    return normalized


def _parse_items(raw_items: Any) -> list[dict] | None:
    if not isinstance(raw_items, list) or not raw_items:
        return None
    parsed: list[dict] = []
    for item in raw_items:
        if not isinstance(item, dict):
            return None
        product_id = str(item.get("id", "")).strip()
        if product_id not in MINI_APP_PRODUCT_IDS:
            return None
        try:
            qty = int(float(item.get("qty", 0)))
        except (TypeError, ValueError):
            return None
        if qty < 1 or qty > 999:
            return None
        catalog_item = MINI_APP_PRODUCT_BY_ID[product_id]
        parsed.append(
            {
                "id": product_id,
                "title": str(catalog_item["title"]),
                "qty": qty,
                "price": int(catalog_item["price"]),
            }
        )
    return parsed


def _summaries(items: list[dict]) -> tuple[str, str]:
    parts = [f"{item['title']} ×{item['qty']}" for item in items]
    total_qty = sum(item["qty"] for item in items)
    return ", ".join(parts), str(total_qty)


def _admin_order_text(
    *,
    order_id: int,
    goal: str,
    username: str | None,
    phone: str,
    city: str,
    address: str,
    delivery_type: str,
    payment: str,
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
        f"🚚 Доставка: {delivery_type or '—'}",
        f"💳 Оплата: {payment or '—'}",
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
    delivery_type: str,
    payment: str,
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
        delivery_type=delivery_type,
        payment=payment,
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


async def _notify_user_order(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text, parse_mode=None)
        return True
    except Exception as e:
        log.exception("Заказ: не удалось отправить клиенту сообщение user_id=%s: %s", user_id, e)
        return False


async def process_order_payload(
    data: dict,
    *,
    user_id: int,
    username: str | None,
    bot: Bot | None = None,
    notify_user: bool = False,
) -> OrderProcessingResult:
    goal = await db.get_user_goal(user_id)
    if not goal:
        raise OrderProcessingError(
            msg.webapp_need_goal_plain(),
            f"user_id={user_id}: цель пользователя не выбрана",
        )

    items = _parse_items(data.get("items"))
    if not items:
        raise OrderProcessingError(
            msg.webapp_bad_data_plain(),
            f"user_id={user_id}: невалидные items keys={list(data.keys())}",
        )

    unavailable_ids = await db.get_unavailable_product_ids([item["id"] for item in items])
    if unavailable_ids:
        unavailable_titles = [item["title"] for item in items if item["id"] in unavailable_ids]
        raise OrderProcessingError(
            msg.webapp_out_of_stock_plain(unavailable_titles),
            f"user_id={user_id}: товары не в наличии ids={sorted(unavailable_ids)}",
        )

    phone = _str_field(data, "phone")
    city = _str_field(data, "city")
    address = _str_field(data, "address")
    comment = _str_field(data, "comment")
    delivery_type = _str_field(data, "deliveryType") or _str_field(data, "delivery_type")
    payment = _str_field(data, "payment")

    if len(address) < 1:
        address = "— (адрес не передан из приложения; уточнить у клиента)"

    computed_total = sum(item["qty"] * item["price"] for item in items)
    subtotal_str = str(computed_total)

    raw_promo = _applied_promo_field(data)
    promo_used = ""
    discount_amount = "0"
    discount_percent = 0
    final_price = computed_total
    if raw_promo:
        promo_info = await db.get_promo_info(raw_promo)
        if not promo_info:
            raise OrderProcessingError(
                "Промокод недействителен. Оформите заказ без промокода или введите верный код.",
                f"user_id={user_id}: неверный промокод {raw_promo[:80]!r}",
            )
        discount_percent = int(promo_info["discount_percent"])
        final_price = int(round(computed_total * (1 - discount_percent / 100.0)))
        if final_price < 0:
            final_price = 0
        promo_used = str(promo_info["code"])
        discount_amount = str(computed_total - final_price)

    if len(city) < 2 or len(phone) < 5:
        raise OrderProcessingError(
            msg.webapp_bad_data_fields(),
            f"user_id={user_id}: короткие поля city={city!r} phone_len={len(phone)}",
        )

    product_summary, quantity_summary = _summaries(items)
    items_json = json.dumps(items, ensure_ascii=False)
    final_price_str = str(final_price)

    try:
        order_id = await db.create_order_webapp(
            user_id,
            goal=goal,
            phone=phone,
            city=city,
            address=address,
            delivery_type=delivery_type,
            payment=payment,
            total_price=subtotal_str,
            promo_used=promo_used,
            discount_amount=discount_amount,
            final_price=final_price_str,
            comment=comment,
            product_summary=product_summary,
            quantity_summary=quantity_summary,
            items_json=items_json,
        )
    except Exception as e:
        log.exception("create_order_webapp user_id=%s: %s", user_id, e)
        raise OrderProcessingError(msg.webapp_order_error_plain(), f"create_order_webapp failed user_id={user_id}") from e

    admin_ok = False
    if bot is not None:
        admin_ok = await _notify_admin_order(
            bot,
            order_id=order_id,
            goal=goal,
            username=username,
            phone=phone,
            city=city,
            address=address,
            delivery_type=delivery_type,
            payment=payment,
            total_price=subtotal_str,
            promo_used=promo_used,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            final_price=final_price_str,
            comment=comment,
        )

    user_message = msg.order_accepted_plain(city)
    if not admin_ok:
        user_message = f"{user_message}\n\n{msg.ORDER_ADMIN_NOTIFY_FAILED_PLAIN}"

    if bot is not None and notify_user:
        await _notify_user_order(bot, user_id, user_message)

    return OrderProcessingResult(
        order_id=order_id,
        user_message=user_message,
        admin_notified=admin_ok,
    )
