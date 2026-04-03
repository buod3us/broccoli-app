from __future__ import annotations

from pathlib import Path

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InputMediaPhoto,
    InlineKeyboardButton,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import BASE_DIR
from handlers.common import ensure_goal_chosen
import database as db
from md2 import escape_md2
from states import Menu

router = Router(name="reviews")

REVIEWS_DIR = BASE_DIR / "assets" / "reviews"

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def get_review_files() -> list[Path]:
    """Сканирует `assets/reviews/`, сортирует по имени и возвращает список путей."""
    if not REVIEWS_DIR.exists() or not REVIEWS_DIR.is_dir():
        return []
    files: list[Path] = []
    for p in REVIEWS_DIR.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in _IMG_EXTS:
            continue
        files.append(p)
    files.sort(key=lambda x: x.name.lower())
    return files


def build_reviews_kb(*, idx: int, total: int):
    kb = InlineKeyboardBuilder()
    prev_idx = idx
    next_idx = idx

    kb.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data=f"reviews_nav:prev:{prev_idx}",
        ),
        InlineKeyboardButton(
            text=f"[{idx + 1}/{total}]",
            callback_data=f"reviews_nav:noop:{idx}",
        ),
        InlineKeyboardButton(
            text="Вперед ➡️",
            callback_data=f"reviews_nav:next:{next_idx}",
        ),
    )

    kb.row(
        InlineKeyboardButton(
            text="🛍 Перейти в магазин",
            callback_data="menu:shop",
        ),
    )
    kb.row(
        InlineKeyboardButton(
            text="🏠 В главное меню",
            callback_data="menu:main",
        ),
    )
    return kb.as_markup()


def reviews_caption(*, idx: int, total: int) -> str:
    return f"💬 Отзывы наших клиентов ({idx + 1}/{total})"


def _format_empty_reviews_text() -> str:
    return "Мы скоро добавим сюда первые отзывы! Станьте первым, кто попробует Бро Кколи!"


async def _show_reviews_page(
    *,
    cq: CallbackQuery | None,
    message: Message | None,
    state: FSMContext,
    start_idx: int,
) -> None:
    if cq is not None:
        if not cq.from_user or not cq.message:
            await cq.answer()
            return
        if not await ensure_goal_chosen(cq.from_user.id, cq):
            return
        await state.set_state(Menu.main)
        await cq.answer()
        chat_message = cq.message
    else:
        if message is None:
            return
        if not message.from_user:
            return
        # Для команды /reviews — цель уже задана через /start, но проверку сделаем одинаково.
        # Здесь нет CallbackQuery, поэтому просто выставляем state.
        await state.set_state(Menu.main)
        chat_message = message

    files = get_review_files()
    if not files:
        text = _format_empty_reviews_text()
        if cq is not None:
            await cq.answer(text, show_alert=True)
        else:
            await chat_message.answer(text, parse_mode=None)
        return

    total = len(files)
    idx = start_idx % total
    path = files[idx]
    caption = escape_md2(reviews_caption(idx=idx, total=total))
    media = InputMediaPhoto(
        media=FSInputFile(path),
        caption=caption,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    kb = build_reviews_kb(idx=idx, total=total)

    # Изначально пытаемся отредактировать текущее сообщение (оно обычно с фото).
    if cq is not None and cq.message.photo:
        await cq.message.edit_media(media=media, reply_markup=kb)
    else:
        if cq is not None:
            await chat_message.answer_photo(
                photo=FSInputFile(path),
                caption=caption,
                reply_markup=kb,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        else:
            await chat_message.answer_photo(
                photo=FSInputFile(path),
                caption=caption,
                reply_markup=kb,
                parse_mode=ParseMode.MARKDOWN_V2,
            )


@router.callback_query(F.data == "menu:reviews")
async def menu_reviews(cq: CallbackQuery, state: FSMContext) -> None:
    await _show_reviews_page(cq=cq, message=None, state=state, start_idx=0)


@router.message(Command("reviews"))
async def cmd_reviews(message: Message, state: FSMContext) -> None:
    if not message.from_user:
        return
    goal = await db.get_user_goal(message.from_user.id)
    if not goal:
        await message.answer("Сначала выберите цель в опросе.", parse_mode=None)
        return
    await _show_reviews_page(cq=None, message=message, state=state, start_idx=0)


@router.callback_query(F.data.startswith("reviews_nav:"))
async def nav_reviews(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.data or not cq.from_user or not cq.message:
        await cq.answer()
        return
    if not await ensure_goal_chosen(cq.from_user.id, cq):
        return
    await state.set_state(Menu.main)

    parts = cq.data.split(":")
    if len(parts) < 3:
        await cq.answer()
        return
    action = parts[1]
    try:
        idx = int(parts[2])
    except ValueError:
        idx = 0

    files = get_review_files()
    if not files:
        await cq.answer(_format_empty_reviews_text(), show_alert=True)
        return

    total = len(files)
    if action == "noop":
        await cq.answer()
        return
    if action == "next":
        new_idx = (idx + 1) % total
    elif action == "prev":
        new_idx = (idx - 1 + total) % total
    else:
        await cq.answer()
        return

    path = files[new_idx]
    caption = escape_md2(reviews_caption(idx=new_idx, total=total))
    media = InputMediaPhoto(
        media=FSInputFile(path),
        caption=caption,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    kb = build_reviews_kb(idx=new_idx, total=total)

    await cq.message.edit_media(media=media, reply_markup=kb)
    await cq.answer()

