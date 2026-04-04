import json
import logging

from aiogram import F, Router
from aiogram.enums import ContentType
from aiogram.types import Message

import messages as msg
from order_service import OrderProcessingError, process_order_payload

router = Router(name="orders")

log = logging.getLogger(__name__)


@router.message(F.chat.type == "private", F.content_type == ContentType.WEB_APP_DATA)
async def on_web_app_data(message: Message) -> None:
    if not message.from_user or not message.web_app_data:
        log.warning(
            "WEB_APP_DATA: пустое сообщение или нет web_app_data (message_id=%s)",
            message.message_id,
        )
        return

    raw = message.web_app_data.data
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("web_app_data JSON error: %s", raw[:200])
        await message.answer(msg.webapp_bad_data_plain(), parse_mode=None)
        return
    if not isinstance(data, dict):
        log.warning(
            "web_app_data: ожидался объект JSON, user_id=%s",
            message.from_user.id,
        )
        await message.answer(msg.webapp_bad_data_plain(), parse_mode=None)
        return

    try:
        result = await process_order_payload(
            data,
            user_id=message.from_user.id,
            username=message.from_user.username,
            bot=message.bot,
        )
    except OrderProcessingError as e:
        log.warning("web_app_data rejected: %s", e)
        await message.answer(e.public_message, parse_mode=None)
        return

    await message.answer(result.user_message, parse_mode=None)
