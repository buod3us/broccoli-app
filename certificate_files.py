"""
PDF сертификаты: папка certificates/ в корне проекта.

Кладите сюда файлы *.pdf — при нажатии «Сертификаты» в боте они отправятся в чат.
"""

from pathlib import Path

from config import BASE_DIR

CERTIFICATES_DIR = BASE_DIR / "certificates"


def list_certificate_pdfs() -> list[Path]:
    if not CERTIFICATES_DIR.is_dir():
        return []
    found: list[Path] = []
    for p in CERTIFICATES_DIR.iterdir():
        if p.is_file() and p.suffix.lower() == ".pdf":
            found.append(p)
    return sorted(found, key=lambda x: x.name.lower())


CERTIFICATES_DIR.mkdir(parents=True, exist_ok=True)
