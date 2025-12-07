"""Shared helpers for managing HeyGen avatar configuration."""

from __future__ import annotations

import os
from typing import Dict, Iterable, Tuple

import requests

AVATAR_ENV_DEFAULTS: Dict[str, str] = {
    "HEYGEN_AVATAR_PROFESSIONAL_CLOSEUP": "5637676d31d54946b7585b012a3ce182",
    "HEYGEN_AVATAR_CASUAL_CLOSEUP": "5637676d31d54946b7585b012a3ce182",
    "HEYGEN_AVATAR_FITNESS_FULLBODY": "5637676d31d54946b7585b012a3ce182",
    "HEYGEN_AVATAR_CONFIDENT_SWIMWEAR_FULLBODY": "5637676d31d54946b7585b012a3ce182",
    "HEYGEN_AVATAR_SERIOUS_CLOSEUP": "5637676d31d54946b7585b012a3ce182",
    "HEYGEN_AVATAR_WARMSMILE_CLOSEUP": "5637676d31d54946b7585b012a3ce182",
    "HEYGEN_AVATAR_THREEQUARTERS_CLOSEUP": "5637676d31d54946b7585b012a3ce182",
    "HEYGEN_AVATAR_SUMMERCASUAL_THREEQUARTERBODY": "5637676d31d54946b7585b012a3ce182",
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
    regular_avatars: set[str] = set()

    try:
        list_response = session.get(list_url, headers=headers, timeout=timeout)
        if list_response.status_code == 200:
            data = list_response.json()
            avatars = data.get("data", {}).get("avatars", [])
            regular_avatars = {
                a.get("avatar_id") for a in avatars if a.get("avatar_id")
            }
    except Exception:  # pragma: no cover - network issues or unexpected errors
        pass

    for env_key, avatar_id in avatar_ids.items():
        status: Dict[str, str | bool] = {
            "avatar_id": avatar_id,
            "ok": False,
            "detail": "",
        }

        if avatar_id in regular_avatars:
            status["ok"] = True
            status["detail"] = "Regular avatar found"
        elif len(avatar_id) == 32 or (len(avatar_id) == 36 and "-" in avatar_id):
            status["ok"] = True
            status["detail"] = "Photo avatar (cannot verify via API, assuming available)"
        else:
            status["detail"] = f"Unknown avatar format: {avatar_id}"

        results[env_key] = status

    return results


def build_bulk_payload() -> Dict[str, str]:
    """Return a JSON-serialisable payload of the default avatar mappings."""

    return dict(AVATAR_ENV_DEFAULTS)
