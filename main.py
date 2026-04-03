import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import ADMIN_ID, BASE_DIR, GEMINI_API_KEY, TELEGRAM_TOKEN
from database import init_db
from handlers import setup_routers
from handlers.ai import configure_gemini


async def _run() -> None:
    if not TELEGRAM_TOKEN.strip():
        print("Укажите TELEGRAM_TOKEN в файле .env", file=sys.stderr)
        raise SystemExit(1)

    knowledge_path = BASE_DIR / "knowledge.txt"
    if not knowledge_path.is_file():
        print("Отсутствует knowledge.txt", file=sys.stderr)
        raise SystemExit(1)
    knowledge = knowledge_path.read_text(encoding="utf-8")
    configure_gemini(GEMINI_API_KEY, knowledge)

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

    await dp.start_polling(bot)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(_run())


if __name__ == "__main__":
    main()
