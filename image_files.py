"""
Картинки из папки images/ (корень проекта).

Имя файла = ключ + расширение. Поддерживаются: .jpg .jpeg .png .webp
Примеры:
  images/welcome.jpg       — старт, главное меню, доставка, ИИ
  images/certificates.jpg  — «Сертификаты»; PDF — в certificates/
  images/reviews.jpg       — «Отзывы»
"""

from pathlib import Path

from config import BASE_DIR

IMAGES_DIR = BASE_DIR / "images"

_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def image_path(stem: str) -> Path | None:
    """Путь к images/<stem>.<ext> или None, если файла нет."""
    for ext in _EXTENSIONS:
        p = IMAGES_DIR / f"{stem}{ext}"
        if p.is_file():
            return p
    return None


IMAGES_DIR.mkdir(parents=True, exist_ok=True)
