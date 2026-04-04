import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


@dataclass(slots=True)
class TelegramInitData:
    raw: str
    auth_date: int
    query_id: str
    user_id: int
    username: str | None
    user: dict


class TelegramInitDataError(ValueError):
    pass


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 86400,
) -> TelegramInitData:
    raw = str(init_data or "").strip()
    if not raw:
        raise TelegramInitDataError("Пустой Telegram initData.")
    if not str(bot_token or "").strip():
        raise TelegramInitDataError("На сервере не задан TELEGRAM_TOKEN.")

    pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=False)
    if not pairs:
        raise TelegramInitDataError("Не удалось разобрать Telegram initData.")

    data = dict(pairs)
    provided_hash = str(data.pop("hash", "")).strip().lower()
    if not provided_hash:
        raise TelegramInitDataError("В Telegram initData отсутствует hash.")

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(data.items(), key=lambda item: item[0])
    )
    expected_hash = hmac.new(
        _secret_key(bot_token),
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, provided_hash):
        raise TelegramInitDataError("Подпись Telegram initData не прошла проверку.")

    try:
        auth_date = int(str(data.get("auth_date") or "0"))
    except ValueError as e:
        raise TelegramInitDataError("В Telegram initData отсутствует корректный auth_date.") from e

    now = int(time.time())
    if auth_date <= 0 or abs(now - auth_date) > max_age_seconds:
        raise TelegramInitDataError("Сессия Mini App устарела. Откройте магазин заново из бота.")

    user_raw = str(data.get("user") or "").strip()
    if not user_raw:
        raise TelegramInitDataError("В Telegram initData отсутствуют данные пользователя.")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as e:
        raise TelegramInitDataError("Не удалось прочитать пользователя из Telegram initData.") from e
    if not isinstance(user, dict):
        raise TelegramInitDataError("Поле user в Telegram initData имеет неверный формат.")

    try:
        user_id = int(user.get("id") or 0)
    except (TypeError, ValueError) as e:
        raise TelegramInitDataError("В Telegram initData отсутствует корректный user id.") from e
    if user_id <= 0:
        raise TelegramInitDataError("В Telegram initData отсутствует корректный user id.")

    username_raw = user.get("username")
    username = str(username_raw).strip() if username_raw is not None else None
    if username == "":
        username = None

    return TelegramInitData(
        raw=raw,
        auth_date=auth_date,
        query_id=str(data.get("query_id") or "").strip(),
        user_id=user_id,
        username=username,
        user=user,
    )
