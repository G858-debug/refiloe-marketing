"""Shared helpers for managing HeyGen avatar configuration."""

from __future__ import annotations

import os
from typing import Dict, Iterable, Tuple

import requests

AVATAR_ENV_DEFAULTS: Dict[str, str] = {
    "HEYGEN_AVATAR_PROFESSIONAL_CLOSEUP": "110f75a397604454ba6f822c68f29949",
    "HEYGEN_AVATAR_CASUAL_CLOSEUP": "e39d22ad46c34b5599dc939c63ba1d89",
    "HEYGEN_AVATAR_FITNESS_FULLBODY": "3fa139effeb348a99b959065a2425363",
    "HEYGEN_AVATAR_CONFIDENT_SWIMWEAR_FULLBODY": "5d511d22069d4a7d9d75ffd78d1a0bda",
    "HEYGEN_AVATAR_SERIOUS_CLOSEUP": "efe8efb12f0a4bc8b961e22220fc974d",
    "HEYGEN_AVATAR_WARMSMILE_CLOSEUP": "9648b4e9da9c444c877214312c5ad27c",
    "HEYGEN_AVATAR_LAUGHING_CLOSEUP": "89c3da65880249e78e26070732b52f53",
    "HEYGEN_AVATAR_THREEQUARTERS_CLOSEUP": "5637676d31d54946b7585b012a3ce182",
    "HEYGEN_AVATAR_SUMMERCASUAL_THREEQUARTERBODY": "12e5e8c825e547a0a67ad0057288a4da",
    "HEYGEN_AVATAR_GROUP": "89c3da65880249e78e26070732b52f53",
    "HEYGEN_AVATAR_DEFAULT": "5637676d31d54946b7585b012a3ce182",
}

HEYGEN_API_BASE_URL = "https://api.heygen.com/v2/avatars"


class AvatarAvailabilityError(RuntimeError):
    """Raised when avatar availability cannot be confirmed."""


def collect_avatar_env_values(keys: Iterable[str] | None = None) -> Tuple[Dict[str, str], list[str]]:
    """Read avatar IDs from the environment.

    Returns a tuple of (configured_values, missing_keys).
    """

    keys = list(keys) if keys is not None else list(AVATAR_ENV_DEFAULTS.keys())
    values: Dict[str, str] = {}
    missing: list[str] = []

    for key in keys:
        value = os.getenv(key)
        if value:
            values[key] = value
        else:
            missing.append(key)

    return values, missing


def check_avatar_availability(
    api_key: str,
    avatar_ids: Dict[str, str],
    timeout: float = 15.0,
) -> Dict[str, Dict[str, str | bool]]:
    """Call the HeyGen API for each avatar and return status details."""

    session = requests.Session()
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    results: Dict[str, Dict[str, str | bool]] = {}

    list_url = "https://api.heygen.com/v2/avatars"
    try:
        list_response = session.get(list_url, headers=headers, timeout=timeout)
        if list_response.status_code == 200:
            available_avatars = list_response.json().get("data", {}).get("avatars", [])
            available_ids = {
                a.get("avatar_id") for a in available_avatars if a.get("avatar_id")
            }
        else:
            available_ids = set()
    except Exception:  # pragma: no cover - network issues or unexpected errors
        available_ids = set()

    for env_key, avatar_id in avatar_ids.items():
        status: Dict[str, str | bool] = {
            "avatar_id": avatar_id,
            "ok": False,
            "detail": "",
        }

        if available_ids and avatar_id in available_ids:
            status["ok"] = True
            status["detail"] = "OK"
        else:
            url = f"https://api.heygen.com/v2/avatar/{avatar_id}"
            try:
                response = session.get(url, headers=headers, timeout=timeout)
                if response.status_code == 200:
                    status["ok"] = True
                    status["detail"] = "OK"
                else:
                    try:
                        payload = response.json()
                        status["detail"] = payload.get(
                            "message", f"Status {response.status_code}"
                        )
                    except ValueError:
                        status["detail"] = f"HTTP {response.status_code}"
            except requests.RequestException as exc:  # pragma: no cover - network issues
                status["detail"] = str(exc)
        results[env_key] = status

    return results


def build_bulk_payload() -> Dict[str, str]:
    """Return a JSON-serialisable payload of the default avatar mappings."""

    return dict(AVATAR_ENV_DEFAULTS)
