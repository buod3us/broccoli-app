"""Фото: локальный файл, URL, цепочка fallback (в т.ч. встроенный PNG).

Повторные edit_media/answer_photo используют кэш file_id Telegram — без повторной
загрузки файла (важно при URLInputFile: иначе каждый раз скачивание с интернета).
"""

import base64
from pathlib import Path

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    FSInputFile,
    InputMediaPhoto,
    Message,
    URLInputFile,
)

from config import WELCOME_IMAGE_URL
from image_files import image_path

# 1×1 PNG — если все URL недоступны, Telegram всё равно примет файл из памяти
_PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

# Логический ключ → file_id последнего успешно отправленного фото этого экрана
_FILE_ID_CACHE: dict[str, str] = {}


def placeholder_input_file() -> BufferedInputFile:
    return BufferedInputFile(_PLACEHOLDER_PNG, filename="photo.png")


def input_photo(
    image_url: str,
    local_path: Path | None = None,
    *,
    folder_key: str | None = None,
):
    """
    Приоритет: images/<folder_key>.* → явный local_path → URL.
    Для меню и старта: folder_key=\"welcome\".
    """
    if folder_key:
        p = image_path(folder_key)
        if p:
            return FSInputFile(p)
    if local_path and local_path.is_file():
        return FSInputFile(local_path)
    return URLInputFile(image_url)


def single_url_photo_inputs(
    url: str,
    *,
    folder_keys: tuple[str, ...] = ("welcome",),
) -> list:
    """Локальное фото: первый существующий из folder_keys, затем URL и плейсхолдер."""
    items: list = []
    for key in folder_keys:
        p = image_path(key)
        if p:
            items.append(FSInputFile(p))
            break
    items.append(URLInputFile(url))
    items.append(placeholder_input_file())
    return items


def _remember_file_id(cache_key: str | None, result: Message | bool) -> None:
    if not cache_key or not isinstance(result, Message) or not result.photo:
        return
    _FILE_ID_CACHE[cache_key] = result.photo[-1].file_id


async def answer_photo_cached(
    message: Message,
    *,
    cache_key: str,
    caption: str,
    reply_markup,
    photo_input,
) -> None:
    """answer_photo с приоритетом file_id из кэша (для /start и т.п.)."""
    fid = _FILE_ID_CACHE.get(cache_key)
    if fid:
        try:
            sent = await message.answer_photo(
                photo=fid,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup,
            )
            _remember_file_id(cache_key, sent)
            return
        except TelegramBadRequest:
            _FILE_ID_CACHE.pop(cache_key, None)
    sent = await message.answer_photo(
        photo=photo_input,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=reply_markup,
    )
    _remember_file_id(cache_key, sent)


async def apply_photo_via_callback(
    cq: CallbackQuery,
    *,
    caption: str,
    reply_markup,
    photo_inputs: list,
    cache_key: str | None = None,
) -> bool:
    """Перебирает источники; при cache_key сначала пробует сохранённый file_id."""
    msg = cq.message
    if not msg:
        return False
    err_net = (TelegramNetworkError, TelegramBadRequest)

    candidates: list = []
    if cache_key:
        fid = _FILE_ID_CACHE.get(cache_key)
        if fid:
            candidates.append(fid)
    candidates.extend(photo_inputs)

    for inp in candidates:
        try:
            if msg.photo:
                result = await msg.edit_media(
                    media=InputMediaPhoto(
                        media=inp,
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN_V2,
                    ),
                    reply_markup=reply_markup,
                )
            else:
                result = await msg.answer_photo(
                    photo=inp,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=reply_markup,
                )
            _remember_file_id(cache_key, result)
            return True
        except TelegramBadRequest:
            if cache_key and isinstance(inp, str):
                _FILE_ID_CACHE.pop(cache_key, None)
            continue
        except TelegramNetworkError:
            continue
    return False
