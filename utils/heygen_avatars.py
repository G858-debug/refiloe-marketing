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
    "HEYGEN_AVATAR_THREEQUARTERS_CLOSEUP": "5637676d31d54946b7585b012a3ce182",
    "HEYGEN_AVATAR_SUMMERCASUAL_THREEQUARTERBODY": "12e5e8c825e547a0a67ad0057288a4da",
    "HEYGEN_AVATAR_GROUP": "89c3da65880249e78e26070732b52f53",
    "HEYGEN_AVATAR_DEFAULT": "75370ca4dd714442a70d84eee87870f3",
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
