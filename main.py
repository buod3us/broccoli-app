import asyncio
import logging
import os
import sys
from typing import TextIO

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import ADMIN_ID, BASE_DIR, BOT_RUN_MODE, GEMINI_API_KEY, TELEGRAM_TOKEN, WEBHOOK_URL
from database import close_db, init_db
from handlers import setup_routers
from handlers.ai import configure_gemini


_BOT_LOCK_HANDLE: TextIO | None = None


def _acquire_bot_lock() -> None:
    global _BOT_LOCK_HANDLE
    lock_path = BASE_DIR / ".bot.polling.lock"
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        handle.seek(0)
        if os.name == "nt":
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        print(
            "Бот уже запущен на этом сервере. Остановите старый процесс main.py и повторите запуск.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    _BOT_LOCK_HANDLE = handle


def _release_bot_lock() -> None:
    global _BOT_LOCK_HANDLE
    handle = _BOT_LOCK_HANDLE
    if handle is None:
        return
    try:
        handle.seek(0)
        if os.name == "nt":
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    handle.close()
    _BOT_LOCK_HANDLE = None


async def _run() -> None:
    if not TELEGRAM_TOKEN.strip():
        print("Укажите TELEGRAM_TOKEN в файле .env", file=sys.stderr)
        raise SystemExit(1)
    if BOT_RUN_MODE == "webhook":
        print(
            f"BOT_RUN_MODE=webhook: локальный polling отключён. Бот принимает апдейты через {WEBHOOK_URL or 'webhook endpoint'}.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    knowledge_path = BASE_DIR / "knowledge.txt"
    if not knowledge_path.is_file():
        print("Отсутствует knowledge.txt", file=sys.stderr)
        raise SystemExit(1)
    knowledge = knowledge_path.read_text(encoding="utf-8")
    configure_gemini(GEMINI_API_KEY, knowledge)
    _acquire_bot_lock()
    bot: Bot | None = None

    try:
        await init_db()

        if not ADMIN_ID:
            logging.getLogger(__name__).warning(
                "ADMIN_ID не задан в .env — уведомления о новых заказах администратору не отправляются."
            )

        bot = Bot(
            token=TELEGRAM_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2),
        )
        dp = Dispatcher(storage=MemoryStorage())
        for router in setup_routers():
            dp.include_router(router)

        await bot.delete_webhook(drop_pending_updates=False)
        me = await bot.get_me()
        logging.getLogger(__name__).info(
            "Polling bot started as @%s (%s)",
            me.username or "unknown",
            me.id,
        )
        await dp.start_polling(bot)
    finally:
        if bot is not None:
            await bot.session.close()
        _release_bot_lock()
        await close_db()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(_run())


if __name__ == "__main__":
    main()
