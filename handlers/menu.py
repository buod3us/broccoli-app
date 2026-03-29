import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

from certificate_files import list_certificate_pdfs
from config import WELCOME_IMAGE_URL
from handlers.common import ensure_goal_chosen
import messages as msg
from keyboards import kb_main_menu
from media_input import (
    apply_photo_via_callback,
    input_photo,
    single_url_photo_inputs,
)
from states import Menu

router = Router(name="menu")
log = logging.getLogger(__name__)


@router.callback_query(F.data == "menu:main")
async def open_main_menu(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or not cq.message:
        await cq.answer()
        return
    if not await ensure_goal_chosen(cq.from_user.id, cq):
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


@router.callback_query(F.data == "menu:certs")
async def menu_certs(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or not cq.message:
        await cq.answer()
        return
    if not await ensure_goal_chosen(cq.from_user.id, cq):
        return
    await state.set_state(Menu.main)
    await cq.answer()
    ok = await apply_photo_via_callback(
        cq,
        caption=msg.caption_certificates(),
        reply_markup=kb_main_menu(),
        photo_inputs=single_url_photo_inputs(
            WELCOME_IMAGE_URL,
            folder_keys=("certificates", "welcome"),
        ),
        cache_key="certificates",
    )
    if not ok:
        log.error("Не удалось обновить фото экрана «Сертификаты»")

    pdfs = list_certificate_pdfs()
    for pdf_path in pdfs:
        try:
            await cq.message.answer_document(FSInputFile(pdf_path))
        except Exception:
            log.exception("Не удалось отправить PDF: %s", pdf_path)
    if not pdfs:
        await cq.message.answer(msg.CERTIFICATES_NO_PDF_PLAIN, parse_mode=None)


@router.callback_query(F.data == "menu:reviews")
async def menu_reviews(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or not cq.message:
        await cq.answer()
        return
    if not await ensure_goal_chosen(cq.from_user.id, cq):
        return
    await state.set_state(Menu.main)
    await cq.answer()
    ok = await apply_photo_via_callback(
        cq,
        caption=msg.caption_reviews(),
        reply_markup=kb_main_menu(),
        photo_inputs=single_url_photo_inputs(
            WELCOME_IMAGE_URL,
            folder_keys=("reviews", "welcome"),
        ),
        cache_key="reviews",
    )
    if not ok:
        log.error("Не удалось обновить фото экрана «Отзывы»")


@router.callback_query(F.data == "menu:delivery")
async def menu_delivery(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or not cq.message:
        await cq.answer()
        return
    if not await ensure_goal_chosen(cq.from_user.id, cq):
        return
    await state.set_state(Menu.main)
    await cq.answer()
    if cq.message.photo:
        await cq.message.edit_caption(
            caption=msg.caption_delivery(),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb_main_menu(),
        )
    else:
        await cq.message.answer_photo(
            photo=input_photo(WELCOME_IMAGE_URL, folder_key="welcome"),
            caption=msg.caption_delivery(),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=kb_main_menu(),
        )
