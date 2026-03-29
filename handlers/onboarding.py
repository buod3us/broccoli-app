from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import database as db
from config import WELCOME_IMAGE_URL
from handlers.common import send_shop_reply_keyboard
from keyboards import kb_goal_choice, kb_main_menu
import messages as msg
from media_input import answer_photo_cached, input_photo
from states import Menu, Onboarding

router = Router(name="onboarding")

GOAL_BY_CALLBACK = {
    "goal:byt": "Быт",
    "goal:sport": "Спорт",
    "goal:hajj": "Хадж",
}


@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user
    if not user:
        return
    await db.upsert_user(user.id, user.username)
    goal = await db.get_user_goal(user.id)

    photo = input_photo(WELCOME_IMAGE_URL, folder_key="welcome")

    if goal:
        await state.set_state(Menu.main)
        await answer_photo_cached(
            message,
            cache_key="welcome",
            caption=msg.main_menu_caption(),
            reply_markup=kb_main_menu(),
            photo_input=photo,
        )
        await send_shop_reply_keyboard(message)
        return

    await state.set_state(Onboarding.choosing_goal)
    await answer_photo_cached(
        message,
        cache_key="welcome",
        caption=msg.welcome_caption(),
        reply_markup=kb_goal_choice(),
        photo_input=photo,
    )


@router.callback_query(
    Onboarding.choosing_goal,
    F.data.in_(GOAL_BY_CALLBACK.keys()),
)
async def on_goal_chosen(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or not cq.message:
        await cq.answer()
        return
    key = cq.data or ""
    goal = GOAL_BY_CALLBACK[key]
    await db.set_user_goal(cq.from_user.id, goal)
    await state.set_state(Menu.main)
    await cq.answer()

    try:
        await cq.message.edit_caption(
            caption=msg.main_menu_caption(),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb_main_menu(),
        )
        await send_shop_reply_keyboard(cq.message)
    except Exception:
        await answer_photo_cached(
            cq.message,
            cache_key="welcome",
            caption=msg.main_menu_caption(),
            reply_markup=kb_main_menu(),
            photo_input=input_photo(WELCOME_IMAGE_URL, folder_key="welcome"),
        )
        await send_shop_reply_keyboard(cq.message)
