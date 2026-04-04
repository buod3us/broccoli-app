import asyncio
import logging
import re
from contextlib import asynccontextmanager, suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db
from catalog import MINI_APP_CATEGORIES, MINI_APP_PRODUCT_CATALOG
from config import (
    API_CORS_ORIGINS,
    API_HOST,
    API_PORT,
    BASE_DIR,
    BOT_RUN_MODE,
    GEMINI_API_KEY,
    TELEGRAM_TOKEN,
    WEBHOOK_PATH,
    WEBHOOK_SECRET_TOKEN,
    WEBHOOK_URL,
)
from handlers import setup_routers
from handlers.ai import configure_gemini
from order_service import OrderProcessingError, process_order_payload
from telegram_webapp import TelegramInitDataError, validate_telegram_init_data

WEB_DIR = BASE_DIR / "web"
log = logging.getLogger(__name__)
_VALID_WEBHOOK_SECRET_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


def _resolve_webhook_secret_token() -> str | None:
    token = WEBHOOK_SECRET_TOKEN.strip()
    if not token:
        return None
    if not _VALID_WEBHOOK_SECRET_RE.fullmatch(token):
        log.warning(
            "WEBHOOK_SECRET_TOKEN contains unsupported Telegram characters; webhook secret disabled."
        )
        return None
    return token


_WEBHOOK_SECRET_TOKEN = _resolve_webhook_secret_token()


class OrderItemPayload(BaseModel):
    id: str
    qty: int
    title: str | None = None
    price: int | float | None = None


class CreateOrderPayload(BaseModel):
    init_data: str
    items: list[OrderItemPayload]
    deliveryType: str = ""
    city: str = ""
    address: str = ""
    phone: str = ""
    comment: str = ""
    payment: str = ""
    total_price: int | float | str | None = None
    applied_promo: str = ""
    discount_percent: int | float | str | None = None
    final_price: int | float | str | None = None


def _public_catalog_payload() -> dict[str, list[dict]]:
    return {
        "categories": [dict(item) for item in MINI_APP_CATEGORIES],
        "items": [dict(item) for item in MINI_APP_PRODUCT_CATALOG],
    }


def _public_promos_payload(rows: list[dict]) -> dict[str, int]:
    payload: dict[str, int] = {}
    for row in rows:
        code = str(row.get("code") or "").strip().upper()
        discount = int(row.get("discount_percent") or 0)
        if code and 0 < discount <= 100:
            payload[code] = discount
    return payload


def _build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    for router in setup_routers():
        dp.include_router(router)
    return dp


async def _configure_webhook(bot: Bot, allowed_updates: list[str]) -> None:
    retry_delays = (0, 3, 10, 30)
    attempts = len(retry_delays)
    for attempt, delay in enumerate(retry_delays, start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            await bot.set_webhook(
                WEBHOOK_URL,
                secret_token=_WEBHOOK_SECRET_TOKEN,
                allowed_updates=allowed_updates,
                drop_pending_updates=False,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            if attempt == attempts:
                log.exception(
                    "Telegram webhook setup failed after %s attempts for %s",
                    attempts,
                    WEBHOOK_URL,
                )
                return
            log.warning(
                "Telegram webhook setup failed on attempt %s/%s for %s; retrying in %ss",
                attempt,
                attempts,
                WEBHOOK_URL,
                retry_delays[attempt],
                exc_info=True,
            )
        else:
            log.info("Telegram webhook configured: %s", WEBHOOK_URL)
            return


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bot = None
    app.state.bot_id = 0
    app.state.bot_username = ""
    app.state.bot_mode = BOT_RUN_MODE
    app.state.dp = None
    app.state.webhook_task = None
    bot = None
    try:
        await db.init_db()
        if BOT_RUN_MODE == "webhook" and not TELEGRAM_TOKEN.strip():
            raise RuntimeError("BOT_RUN_MODE=webhook требует TELEGRAM_TOKEN.")
        if BOT_RUN_MODE == "webhook" and (not WEBHOOK_URL or not WEBHOOK_URL.startswith("https://")):
            raise RuntimeError("BOT_RUN_MODE=webhook требует корректный HTTPS WEBHOOK_URL/WEBHOOK_BASE_URL.")

        if TELEGRAM_TOKEN.strip():
            bot = Bot(
                token=TELEGRAM_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2),
            )
        if bot is not None:
            try:
                me = await bot.get_me()
            except Exception as e:
                log.warning("API bot self-check failed: %s", e)
            else:
                app.state.bot_id = int(me.id)
                app.state.bot_username = str(me.username or "").strip()
                log.info(
                    "API bot configured as @%s (%s)",
                    app.state.bot_username or "unknown",
                    app.state.bot_id,
                )
            if BOT_RUN_MODE == "webhook":
                knowledge_path = BASE_DIR / "knowledge.txt"
                if not knowledge_path.is_file():
                    raise RuntimeError("Для webhook-режима отсутствует knowledge.txt.")
                configure_gemini(GEMINI_API_KEY, knowledge_path.read_text(encoding="utf-8"))
                dp = _build_dispatcher()
                app.state.dp = dp
                app.state.webhook_task = asyncio.create_task(
                    _configure_webhook(
                        bot,
                        dp.resolve_used_update_types(),
                    )
                )
        else:
            log.warning("API started without TELEGRAM_TOKEN — order creation will be unavailable.")
        app.state.bot = bot
        yield
    finally:
        webhook_task = getattr(app.state, "webhook_task", None)
        if webhook_task is not None:
            webhook_task.cancel()
            with suppress(asyncio.CancelledError):
                await webhook_task
        if bot is not None:
            await bot.session.close()
        await db.close_db()


app = FastAPI(
    title="Halalstore API",
    version="0.2.0",
    lifespan=lifespan,
)

if API_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=API_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/")
async def root() -> dict[str, object]:
    return {
        "service": "halalstore-api",
        "ok": True,
        "cors_origins": API_CORS_ORIGINS,
        "mini_app_path": "/app/",
        "bot_mode": BOT_RUN_MODE,
        "webhook_path": WEBHOOK_PATH if BOT_RUN_MODE == "webhook" else "",
    }


@app.get("/healthz")
async def healthz() -> dict[str, object]:
    ok = await db.ping_db()
    if not ok:
        raise HTTPException(status_code=503, detail="Database ping failed.")
    return {
        "ok": True,
        "db": db.backend_name(),
        "bot_username": getattr(app.state, "bot_username", ""),
        "bot_id": getattr(app.state, "bot_id", 0),
        "bot_mode": getattr(app.state, "bot_mode", "polling"),
        "webhook_url": WEBHOOK_URL if BOT_RUN_MODE == "webhook" else "",
    }


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request) -> Response:
    if BOT_RUN_MODE != "webhook":
        raise HTTPException(status_code=503, detail="Webhook mode is disabled.")

    bot = getattr(app.state, "bot", None)
    dp = getattr(app.state, "dp", None)
    if bot is None or dp is None:
        raise HTTPException(status_code=503, detail="Webhook bot runtime is not ready.")

    if _WEBHOOK_SECRET_TOKEN is not None:
        provided_secret = (request.headers.get("X-Telegram-Bot-Api-Secret-Token") or "").strip()
        if provided_secret != _WEBHOOK_SECRET_TOKEN:
            raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret.")

    update = await request.json()
    result = await dp.feed_webhook_update(bot, update)
    if result is not None:
        await dp.silent_call_request(bot=bot, result=result)
    return Response(status_code=200)


@app.get("/api/catalog")
async def api_catalog() -> dict[str, list[dict]]:
    return _public_catalog_payload()


@app.get("/api/stock")
async def api_stock() -> dict[str, bool]:
    return await db.get_product_stock_map()


@app.get("/api/promos")
async def api_promos() -> dict[str, int]:
    return _public_promos_payload(await db.list_promos())


@app.post("/api/orders")
async def api_create_order(payload: CreateOrderPayload, request: Request) -> dict[str, object]:
    if not TELEGRAM_TOKEN.strip():
        raise HTTPException(status_code=503, detail="На сервере не задан TELEGRAM_TOKEN.")

    try:
        init_data = validate_telegram_init_data(payload.init_data, TELEGRAM_TOKEN)
    except TelegramInitDataError as e:
        log.warning(
            "Order initData rejected: %s origin=%s referer=%s",
            e,
            request.headers.get("origin", "") or "-",
            request.headers.get("referer", "") or "-",
        )
        raise HTTPException(status_code=401, detail=str(e)) from e

    body = payload.model_dump(mode="python")
    body.pop("init_data", None)
    try:
        result = await process_order_payload(
            body,
            user_id=init_data.user_id,
            username=init_data.username,
            bot=app.state.bot,
            notify_user=True,
        )
    except OrderProcessingError as e:
        log.warning(
            "Order rejected user_id=%s username=%s: %s",
            init_data.user_id,
            init_data.username or "-",
            e,
        )
        raise HTTPException(status_code=400, detail=e.public_message) from e

    if not result.admin_notified:
        log.warning(
            "Order accepted but admin notification failed order_id=%s user_id=%s",
            result.order_id,
            init_data.user_id,
        )

    return {
        "ok": True,
        "order_id": result.order_id,
        "message": result.user_message,
        "admin_notified": result.admin_notified,
    }


if WEB_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=str(WEB_DIR), html=True), name="mini_app")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host=API_HOST, port=API_PORT, reload=False)
