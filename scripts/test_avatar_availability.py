"""Validate access to all configured HeyGen avatars.

This script checks that each avatar ID responds successfully from the HeyGen API.
Requirements:
  - Environment variable HEYGEN_API_KEY must be set.
  - `requests` and `python-dotenv` must be installed (see requirements.txt).

Usage:
    python scripts/test_avatar_availability.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.heygen_avatars import (
    AVATAR_ENV_DEFAULTS,
    check_avatar_availability,
    collect_avatar_env_values,
)

API_KEY_ENV = "HEYGEN_API_KEY"


def ensure_env_loaded() -> None:
    dotenv_path = PROJECT_ROOT / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
    else:
        load_dotenv()


def require_api_key() -> str:
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        sys.exit(f"{API_KEY_ENV} is not set. Please add it to your environment before running this check.")
    return api_key


def load_avatar_ids() -> dict[str, str]:
    avatar_ids, missing = collect_avatar_env_values()
    if missing:
        print("Environment variables missing for: " + ", ".join(sorted(missing)))
        print("Using default avatar IDs for missing entries.")
        for env_key in missing:
            default_value = AVATAR_ENV_DEFAULTS.get(env_key)
            if default_value:
                avatar_ids[env_key] = default_value
    return avatar_ids


def main() -> int:
    ensure_env_loaded()
    api_key = require_api_key()

    avatar_ids = load_avatar_ids()
    if not avatar_ids:
        print("No HeyGen avatar IDs available to validate.")
        return 1

    results = check_avatar_availability(api_key, avatar_ids)

    all_passed = True
    for env_key, status in results.items():
        ok = status.get("ok", False)
        detail = status.get("detail", "")
        avatar_id = status.get("avatar_id", "")
        tag = "PASS" if ok else "FAIL"
        print(f"[{tag}] {env_key} -> {avatar_id} :: {detail}")
        all_passed &= bool(ok)

    if not all_passed:
        print("One or more avatars failed availability checks.")
        return 1

    print("All HeyGen avatars are reachable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
