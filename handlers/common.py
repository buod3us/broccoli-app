from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

import database as db


async def ensure_goal_chosen(user_id: int, cq: CallbackQuery) -> bool:
    try:
        await cq.answer()
    except TelegramBadRequest:
        pass
    goal = await db.get_user_goal(user_id)
    if goal:
        return True
    if cq.message:
        await cq.message.answer("Сначала выберите цель в опросе.", parse_mode=None)
    return False
