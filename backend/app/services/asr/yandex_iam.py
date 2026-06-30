"""IAM-токен Yandex Cloud из авторизованного ключа сервисного аккаунта."""

from __future__ import annotations

import json
import logging
import time

import httpx
import jwt

from app.config import settings

logger = logging.getLogger(__name__)

IAM_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"

_cached_token: str | None = None
_cached_until: float = 0.0


def _load_authorized_key() -> dict:
    raw = settings.yandex_sa_authorized_key.strip()
    if not raw:
        raise RuntimeError("YANDEX_SA_AUTHORIZED_KEY не задан")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "YANDEX_SA_AUTHORIZED_KEY должен быть JSON авторизованного ключа Yandex "
            "(Сервисные аккаунты → speechkit-railway → Создать авторизованный ключ)."
        ) from exc


def get_iam_token() -> str:
    global _cached_token, _cached_until
    now = time.time()
    if _cached_token and now < _cached_until - 120:
        return _cached_token

    key = _load_authorized_key()
    sa_id = key.get("service_account_id")
    key_id = key.get("id")
    private_key = key.get("private_key")
    if not all([sa_id, key_id, private_key]):
        raise RuntimeError("JSON авторизованного ключа должен содержать id, service_account_id, private_key")

    payload = {
        "aud": IAM_URL,
        "iss": sa_id,
        "iat": int(now),
        "exp": int(now) + 3600,
    }
    encoded = jwt.encode(
        payload,
        private_key,
        algorithm="PS256",
        headers={"kid": key_id},
    )

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(IAM_URL, json={"jwt": encoded})
        resp.raise_for_status()
        data = resp.json()

    token = data.get("iamToken")
    if not token:
        raise RuntimeError("Yandex IAM не вернул iamToken")

    _cached_token = token
    _cached_until = now + 3600
    logger.info("Yandex IAM token refreshed")
    return token
