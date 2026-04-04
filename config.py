import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        return []
    return [part.strip().rstrip("/") for part in raw.split(",") if part.strip()]


def _url_origin(url: str) -> str:
    s = str(url or "").strip()
    if not s:
        return ""
    parsed = urlsplit(s)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()
BOT_RUN_MODE = (os.getenv("BOT_RUN_MODE") or "polling").strip().lower()
if BOT_RUN_MODE not in {"polling", "webhook"}:
    BOT_RUN_MODE = "polling"
# API Key Gemini (пакет google-genai); при отсутствии подставляется GOOGLE_API_KEY (старое имя).
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")).strip()
# Стабильное имя из документации Gemini API (1.5-* в v1beta часто даёт 404).
GEMINI_MODEL = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ADMIN_ID_RAW = (os.getenv("ADMIN_ID") or "0").strip()

try:
    ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW else 0
except ValueError:
    ADMIN_ID = 0

# Стабильные прямые ссылки (Wikimedia); в .env можно задать свои CDN.
DEFAULT_WELCOME_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/6/6d/"
    "Good_Food_Display_-_NCI_Visuals_Online.jpg"
)
WELCOME_IMAGE_URL = os.getenv("WELCOME_IMAGE_URL", DEFAULT_WELCOME_URL)

# URL Mini App (HTTPS). Приложение в подпапке web/ на GitHub Pages.
MINI_APP_URL = os.getenv(
    "MINI_APP_URL",
    "https://buod3us.github.io/broccoli-app/web/",
)

# Базовые настройки API: это отдельный HTTPS-сервис для Mini App.
API_HOST = (os.getenv("API_HOST") or "127.0.0.1").strip() or "127.0.0.1"
API_PORT = _int_env("API_PORT", 8000)
API_BASE_URL = (
    os.getenv("API_BASE_URL") or f"http://127.0.0.1:{API_PORT}"
).strip().rstrip("/")
WEBHOOK_PATH = (os.getenv("WEBHOOK_PATH") or "/telegram/webhook").strip() or "/telegram/webhook"
if not WEBHOOK_PATH.startswith("/"):
    WEBHOOK_PATH = f"/{WEBHOOK_PATH}"
WEBHOOK_PATH = WEBHOOK_PATH.rstrip("/") or "/telegram/webhook"
WEBHOOK_BASE_URL = (os.getenv("WEBHOOK_BASE_URL") or API_BASE_URL).strip().rstrip("/")
WEBHOOK_URL = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}" if WEBHOOK_BASE_URL else ""
WEBHOOK_SECRET_TOKEN = (os.getenv("WEBHOOK_SECRET_TOKEN") or "").strip()

_default_api_cors_origins: list[str] = []
_mini_app_origin = _url_origin(MINI_APP_URL)
if _mini_app_origin:
    _default_api_cors_origins.append(_mini_app_origin)
API_CORS_ORIGINS = _csv_env("API_CORS_ORIGINS") or _default_api_cors_origins
