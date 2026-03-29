import asyncio
import logging

import google.generativeai as genai
from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import GOOGLE_API_KEY, WELCOME_IMAGE_URL
from handlers.common import ensure_goal_chosen, send_shop_reply_keyboard
import messages as msg
from keyboards import kb_ai_exit, kb_main_menu
from media_input import apply_photo_via_callback, input_photo
from states import AIConsultant, Menu

router = Router(name="ai")

log = logging.getLogger(__name__)

_model: genai.GenerativeModel | None = None


def configure_gemini(api_key: str, knowledge: str) -> None:
    global _model
    if not api_key.strip():
        log.warning("GOOGLE_API_KEY пуст — ИИ-консультант отключён.")
        _model = None
        return
    genai.configure(api_key=api_key)
    _model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=knowledge,
    )


async def _generate_reply(user_text: str) -> str:
    if _model is None:
        return (
            "Консультант временно недоступен. Попробуйте позже или "
            "оформите заказ через Mini App."
        )
    loop = asyncio.get_event_loop()

    def _call():
        return _model.generate_content(user_text)

    try:
        resp = await loop.run_in_executor(None, _call)
        text = (resp.text or "").strip()
        if not text:
            return (
                "Не удалось сформулировать ответ. Уточните вопрос или "
                "напишите менеджеру после заказа."
            )
        return text
    except Exception as e:
        log.exception("Gemini error: %s", e)
        return "Произошла ошибка сервиса. Попробуйте ещё раз позже."


@router.callback_query(F.data == "menu:ai")
async def open_ai(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or not cq.message:
        await cq.answer()
        return
    if not await ensure_goal_chosen(cq.from_user.id, cq):
        return
    await state.set_state(AIConsultant.chatting)
    await cq.answer()
    if cq.message.photo:
        await cq.message.edit_caption(
            caption=msg.ai_intro_caption(),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb_ai_exit(),
        )
    else:
        await cq.message.answer_photo(
            photo=input_photo(WELCOME_IMAGE_URL, folder_key="welcome"),
            caption=msg.ai_intro_caption(),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb_ai_exit(),
        )


@router.callback_query(AIConsultant.chatting, F.data == "ai:exit")
async def close_ai(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.message:
        await cq.answer()
        return
    await state.set_state(Menu.main)
    await cq.answer()
    await apply_photo_via_callback(
        cq,
        caption=msg.main_menu_caption(),
        reply_markup=kb_main_menu(),
        photo_inputs=[input_photo(WELCOME_IMAGE_URL, folder_key="welcome")],
        cache_key="welcome",
    )
    await send_shop_reply_keyboard(cq.message)


@router.message(AIConsultant.chatting, F.text, ~F.text.startswith("/"))
async def ai_chat_message(message: Message) -> None:
    if not message.text:
        return
    reply = await _generate_reply(message.text)
    await message.answer(reply, parse_mode=None)
