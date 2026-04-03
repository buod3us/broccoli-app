import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
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
