"""Экранирование текста для Telegram MarkdownV2."""

_MD2_SPECIAL = r"_*[]()~`>#+-=|{}.!"


def escape_md2(text: str) -> str:
    if not text:
        return ""
    return "".join(f"\\{c}" if c in _MD2_SPECIAL else c for c in str(text))
