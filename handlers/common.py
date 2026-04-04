from aiogram.types import CallbackQuery

import database as db


async def ensure_goal_chosen(user_id: int, cq: CallbackQuery) -> bool:
    goal = await db.get_user_goal(user_id)
    if goal:
        return True
    await cq.answer("Сначала выберите цель в опросе.", show_alert=True)
    return False
