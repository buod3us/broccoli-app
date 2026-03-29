import logging

from aiogram.types import CallbackQuery, Message

import database as db
from keyboards import kb_reply_shop_webapp

log = logging.getLogger(__name__)

# Один непробельный символ: невидимые/нулевой ширины Telegram часто отбрасывает,
# из‑за чего сообщение не отправляется и reply-клавиатура с «Магазин» не появляется.
_SHOP_KB_PLACEHOLDER = "🛍"


async def send_shop_reply_keyboard(message: Message) -> None:
    """Reply KeyboardButton web_app — нужен для Telegram.WebApp.sendData()."""
    try:
        await message.answer(
            _SHOP_KB_PLACEHOLDER,
            reply_markup=kb_reply_shop_webapp(),
            parse_mode=None,
        )
    except Exception:
        log.exception("Не удалось показать reply-клавиатуру «Магазин» (первая попытка)")
        try:
            await message.answer(
                ".",
                reply_markup=kb_reply_shop_webapp(),
                parse_mode=None,
            )
        except Exception:
            log.exception("Не удалось показать reply-клавиатуру «Магазин» (повтор)")


async def ensure_goal_chosen(user_id: int, cq: CallbackQuery) -> bool:
    goal = await db.get_user_goal(user_id)
    if goal:
        return True
    await cq.answer("Сначала выберите цель в опросе.", show_alert=True)
    return False
