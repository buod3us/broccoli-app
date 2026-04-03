import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

from certificate_files import list_certificate_pdfs
from config import ADMIN_ID, WELCOME_IMAGE_URL
from handlers.common import ensure_goal_chosen, send_shop_reply_keyboard
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


@router.callback_query(F.data == "menu:shop")
async def menu_shop(cq: CallbackQuery, state: FSMContext) -> None:
    """Инлайн «Магазин» — показывает reply\\-клавиатуру с Web App \\(sendData\\)."""
    if not cq.from_user or not cq.message:
        await cq.answer()
        return
    if not await ensure_goal_chosen(cq.from_user.id, cq):
        return
    await state.set_state(Menu.main)
    await cq.answer("Ниже появилась кнопка «Магазин»", show_alert=False)
    await send_shop_reply_keyboard(cq.message)


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
        reply_markup=kb_main_menu(is_admin=cq.from_user.id == ADMIN_ID),
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
        reply_markup=kb_main_menu(is_admin=cq.from_user.id == ADMIN_ID),
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


@router.callback_query(F.data == "menu:delivery")
async def menu_delivery(cq: CallbackQuery, state: FSMContext) -> None:
    if not cq.from_user or not cq.message:
        await cq.answer()
        return
    if not await ensure_goal_chosen(cq.from_user.id, cq):
        return
    await state.set_state(Menu.main)
    await cq.answer()
    try:
        if cq.message.photo:
            await cq.message.edit_caption(
                caption=msg.caption_delivery(),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=kb_main_menu(is_admin=cq.from_user.id == ADMIN_ID),
            )
        else:
            await cq.message.answer_photo(
                photo=input_photo(WELCOME_IMAGE_URL, folder_key="welcome"),
                caption=msg.caption_delivery(),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=kb_main_menu(is_admin=cq.from_user.id == ADMIN_ID),
            )
    except Exception as e:
        if "message is not modified" in str(e):
            pass # Игнорируем ошибку, так как кнопка уже нажата
        else:
            log.exception("Error in menu_delivery")
