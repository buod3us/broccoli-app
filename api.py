from contextlib import asynccontextmanager

from aiogram import Bot
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import database as db
from catalog import MINI_APP_CATEGORIES, MINI_APP_PRODUCT_CATALOG
from config import API_CORS_ORIGINS, API_HOST, API_PORT, BASE_DIR, TELEGRAM_TOKEN
from order_service import OrderProcessingError, process_order_payload
from telegram_webapp import TelegramInitDataError, validate_telegram_init_data

WEB_DIR = BASE_DIR / "web"


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN.strip() else None
    app.state.bot = bot
    try:
        yield
    finally:
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
    }


@app.get("/healthz")
async def healthz() -> dict[str, object]:
    ok = await db.ping_db()
    if not ok:
        raise HTTPException(status_code=503, detail="Database ping failed.")
    return {"ok": True, "db": db.backend_name()}


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
async def api_create_order(payload: CreateOrderPayload) -> dict[str, object]:
    if not TELEGRAM_TOKEN.strip():
        raise HTTPException(status_code=503, detail="На сервере не задан TELEGRAM_TOKEN.")

    try:
        init_data = validate_telegram_init_data(payload.init_data, TELEGRAM_TOKEN)
    except TelegramInitDataError as e:
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
        raise HTTPException(status_code=400, detail=e.public_message) from e

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
