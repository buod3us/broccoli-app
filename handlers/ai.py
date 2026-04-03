import asyncio
import html
import logging
import re

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from google import genai
from google.genai import types
from collections import deque

from config import GEMINI_MODEL, WELCOME_IMAGE_URL, ADMIN_ID
from handlers.common import ensure_goal_chosen
import messages as msg
from keyboards import kb_ai_exit, kb_main_menu
from media_input import apply_photo_via_callback, input_photo
from states import AIConsultant, Menu

router = Router(name="ai")

log = logging.getLogger(__name__)

_client: genai.Client | None = None
_system_instruction: str = ""

# Хранилище истории: user_id -> deque[dict(role, parts)]
# deque(maxlen=10) автоматически удаляет старые сообщения, сохраняя только последние 10.
_user_history: dict[int, deque] = {}

_BOLD_PAIR = re.compile(r"<b>(.*?)</b>", re.IGNORECASE | re.DOTALL)
_STRONG_PAIR = re.compile(r"<strong[^>]*>(.*?)</strong>", re.IGNORECASE | re.DOTALL)


def _flatten_lists_and_misc_html(text: str) -> str:
    """
    Модель часто вставляет <ul>/<li> — в Telegram HTML они не поддерживаются и мешают.
    Оставляем только пары <b>...</b> (после нормализации strong→b); списки → строки с «•».
    """
    if not text:
        return text
    t = _STRONG_PAIR.sub(r"<b>\1</b>", text)
    protected: list[str] = []

    def _shield_bold(m: re.Match[str]) -> str:
        protected.append(m.group(0))
        return f"__TG_BOLD_{len(protected) - 1}__"

    t = re.sub(r"<b[^>]*>.*?</b>", _shield_bold, t, flags=re.IGNORECASE | re.DOTALL)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"<li[^>]*>(.*?)</li>", r"• \1\n", t, flags=re.IGNORECASE | re.DOTALL)
    t = re.sub(
        r"</?(?:ul|ol|p|div|span|h[1-6])[^>]*>",
        "\n",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"<[^>]+>", "", t)
    for i, block in enumerate(protected):
        t = t.replace(f"__TG_BOLD_{i}__", block)
    return t


def _strip_markdown_stars(text: str) -> str:
    """Убираем * из ответов — жирное оформляем через <b> (Telegram HTML)."""
    return text.replace("*", "") if text else text


def _telegram_safe_html(text: str) -> str:
    """Экранирует HTML, оставляя только пары <b>...</b> для Telegram (parse_mode HTML)."""
    if not text:
        return text
    parts: list[str] = []
    pos = 0
    for m in _BOLD_PAIR.finditer(text):
        parts.append(html.escape(text[pos : m.start()]))
        inner = m.group(1).strip()
        if inner:
            parts.append(f"<b>{html.escape(inner)}</b>")
        pos = m.end()
    parts.append(html.escape(text[pos:]))
    return "".join(parts)


def configure_gemini(api_key: str, knowledge: str) -> None:
    """Ключ из `GEMINI_API_KEY` в `.env`; инструкции — из `knowledge.txt` (см. main.py)."""
    global _client, _system_instruction
    if not (api_key or "").strip():
        log.warning("GEMINI_API_KEY пуст — ИИ-консультант отключён.")
        _client = None
        _system_instruction = ""
        return
    _client = genai.Client(api_key=api_key.strip())
    _system_instruction = knowledge.strip() or "Ты вежливый помощник бота."
    log.info("ИИ-консультант: модель %s", GEMINI_MODEL)


async def _generate_reply(user_id: int, user_text: str) -> str:
    if _client is None:
        return _telegram_safe_html(
            "Консультант временно недоступен. Попробуйте позже или "
            "оформите заказ через Mini App."
        )

    # Получаем историю пользователя или создаем новую с лимитом в 10 сообщений
    if user_id not in _user_history:
        _user_history[user_id] = deque(maxlen=10)
    
    # Добавляем новое сообщение от пользователя в историю
    _user_history[user_id].append({"role": "user", "parts": [{"text": user_text}]})

    # Формируем полный контекст (список сообщений)
    contents = list(_user_history[user_id])

    try:
        resp = await _client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=_system_instruction),
        )
        raw = _flatten_lists_and_misc_html(
            _strip_markdown_stars((resp.text or "").strip()),
        )
        if not raw:
            return _telegram_safe_html(
                "Не удалось сформулировать ответ. Уточните вопрос или "
                "напишите менеджеру после заказа."
            )
        
        # Если ответ успешен, сохраняем его в историю как ответ модели
        _user_history[user_id].append({"role": "model", "parts": [{"text": raw}]})
        
        return _telegram_safe_html(raw)
    except Exception as e:
        log.exception("Gemini error: %s", e)
        return _telegram_safe_html(
            "Произошла ошибка сервиса. Попробуйте ещё раз позже."
        )


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
        reply_markup=kb_main_menu(is_admin=cq.from_user.id == ADMIN_ID),
        photo_inputs=[input_photo(WELCOME_IMAGE_URL, folder_key="welcome")],
        cache_key="welcome",
    )


@router.message(AIConsultant.chatting, F.text, ~F.text.startswith("/"))
async def ai_chat_message(message: Message) -> None:
    if not message.text or not message.from_user:
        return

    text_lower = message.text.lower().strip()

    # Пасхалки
    if text_lower in ["да ты че", "да ты чё"]:
        await message.answer("Базару нет", parse_mode=ParseMode.HTML)
        return
    elif text_lower == "ислам":
        await message.answer("Кидок номер 1", parse_mode=ParseMode.HTML)
        return
    elif text_lower == "даулет":
        await message.answer("Воздухан номер 1", parse_mode=ParseMode.HTML)
        return
    elif text_lower == "нурик":
        await message.answer("Займи до выходных номер 1", parse_mode=ParseMode.HTML)
        return
    elif text_lower == "али":
        await message.answer("Качок номер 1 💪💪", parse_mode=ParseMode.HTML)
        return

    # Перевод на менеджера (Админа)
    manager_keywords = ["менеджер", "человек", "админ", "оператор", "поддержка", "помощь"]
    if any(word in text_lower for word in manager_keywords):
        await message.answer("⏳ Перевожу ваш запрос на живого менеджера. Пожалуйста, ожидайте, вам скоро ответят.", parse_mode=ParseMode.HTML)
        
        if ADMIN_ID and message.bot:
            user_link = f"<a href='tg://user?id={message.from_user.id}'>{html.escape(message.from_user.full_name)}</a>"
            username_part = f" (@{message.from_user.username})" if message.from_user.username else ""
            
            admin_msg = (
                f"🚨 <b>Вызов менеджера из ИИ-чата!</b>\n\n"
                f"👤 Пользователь: {user_link}{username_part}\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"💬 Последнее сообщение: <i>{html.escape(message.text)}</i>\n\n"
                f"👉 <i>Чтобы ответить через бота, сделайте <b>Reply (Ответить)</b> на это сообщение и напишите текст вашего ответа.</i>"
            )
            try:
                await message.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode=ParseMode.HTML)
            except Exception as e:
                log.error(f"Не удалось отправить уведомление админу: {e}")
        return

    if message.bot:
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Выводим переписку в консоль сервера (для админа)
    log.info(f"--- ДИАЛОГ С ИИ ---")
    log.info(f"Пользователь {message.from_user.full_name} (ID: {message.from_user.id}): {message.text}")
    
    reply = await _generate_reply(message.from_user.id, message.text)
    
    log.info(f"Бот отвечает: {reply}")
    log.info(f"-------------------")

    await message.answer(reply, parse_mode=ParseMode.HTML)

async def generate_ai_promo_message(username: str, order_summary: str, promo_text: str) -> str:
    if _client is None:
        return promo_text
        
    prompt = (
        f"Напиши короткое, дружелюбное и персонализированное сообщение (не более 3 предложений) для клиента магазина халяльных товаров 'Broccoli'.\n"
        f"Имя клиента: {username or 'Уважаемый клиент'}.\n"
        f"История его покупок: {order_summary}.\n"
        f"Суть акции/сообщения, которую нужно донести: {promo_text}\n\n"
        f"Инструкции:\n"
        f"1. Текст должен быть в формате HTML (можно использовать только теги <b> и <i>).\n"
        f"2. Ответь сразу готовым текстом сообщения (без 'Привет, вот текст').\n"
        f"3. Обязательно учитывай историю покупок клиента, если она есть, чтобы сообщение выглядело индивидуальным.\n"
    )
    
    try:
        resp = await _client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        raw = _flatten_lists_and_misc_html(_strip_markdown_stars((resp.text or "").strip()))
        return _telegram_safe_html(raw) if raw else promo_text
    except Exception as e:
        log.exception("Gemini promo error: %s", e)
        return promo_text
 
