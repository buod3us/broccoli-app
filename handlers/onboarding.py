import asyncio
import html
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

import database as db
from config import ADMIN_ID, WELCOME_IMAGE_URL
from keyboards import kb_goal_choice, kb_main_menu
import messages as msg
from media_input import answer_photo_cached, input_photo
from states import Menu, Onboarding

router = Router(name="onboarding")
log = logging.getLogger(__name__)

GOAL_BY_CALLBACK = {
    "goal:byt": "Быт",
    "goal:sport": "Спорт",
    "goal:hajj": "Хадж",
}


async def _notify_admin_about_new_user(bot: Bot, user: User) -> None:
    if not ADMIN_ID or user.id == ADMIN_ID:
        return
    username = f"@{html.escape(user.username)}" if user.username else "—"
    language = html.escape(user.language_code or "—")
    user_link = f"<a href='tg://user?id={user.id}'>{html.escape(user.full_name)}</a>"
    text = (
        "👤 <b>Новый пользователь открыл бота</b>\n\n"
        f"Имя: {user_link}\n"
        f"Username: {username}\n"
        f"ID: <code>{user.id}</code>\n"
        f"Язык Telegram: {language}"
    )
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=text,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        log.warning("Не удалось отправить уведомление о новом пользователе: %s", e)


@router.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user
    if not user:
        return
    goal, is_new_user = await db.upsert_user_and_get_goal_info(user.id, user.username)
    if is_new_user and message.bot:
        asyncio.create_task(_notify_admin_about_new_user(message.bot, user))

    photo = input_photo(WELCOME_IMAGE_URL, folder_key="welcome")

    if goal:
        await state.set_state(Menu.main)
        await answer_photo_cached(
            message,
            cache_key="welcome",
            caption=msg.main_menu_caption(),
            reply_markup=kb_main_menu(is_admin=user.id == ADMIN_ID),
            photo_input=photo,
        )
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
    await cq.answer()
    key = cq.data or ""
    goal = GOAL_BY_CALLBACK[key]
    await db.set_user_goal(cq.from_user.id, goal)
    await state.set_state(Menu.main)

    try:
        await cq.message.edit_caption(
            caption=msg.main_menu_caption(),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb_main_menu(is_admin=cq.from_user.id == ADMIN_ID),
        )
    except Exception:
        await answer_photo_cached(
            cq.message,
            cache_key="welcome",
            caption=msg.main_menu_caption(),
            reply_markup=kb_main_menu(is_admin=cq.from_user.id == ADMIN_ID),
            photo_input=input_photo(WELCOME_IMAGE_URL, folder_key="welcome"),
        )
