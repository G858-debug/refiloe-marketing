#!/usr/bin/env python3
"""Utility to set up HeyGen avatar environment variables.

This script helps developers provision the HeyGen avatar IDs required by the
application by:
  * Writing the expected variables to the project-level `.env` file
  * Providing deployment guidance for Railway
  * Ensuring a companion availability test script exists

The script is idempotent - running it multiple times keeps the `.env` file
and helper script up to date without removing other user-defined variables.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.heygen_avatars import AVATAR_ENV_DEFAULTS, build_bulk_payload


TEST_SCRIPT_RELATIVE_PATH = Path("scripts/test_avatar_availability.py")


def ensure_env_file(project_root: Path) -> Path:
    """Create or update the `.env` file with the required avatar IDs."""

    env_path = project_root / ".env"
    env_lines: list[str] = []
    existing_vars: dict[str, str] = {}

    if env_path.exists():
        env_lines = env_path.read_text().splitlines()
        for line in env_lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            existing_vars[key.strip()] = value.strip()

    updated_vars = existing_vars.copy()
    updated_vars.update(AVATAR_ENV_DEFAULTS)

    written_keys: set[str] = set()
    new_lines: list[str] = []

    for line in env_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updated_vars:
            new_lines.append(f"{key}={updated_vars[key]}")
            written_keys.add(key)
        else:
            new_lines.append(line)

    for key, value in AVATAR_ENV_DEFAULTS.items():
        if key not in written_keys:
            new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n")
    return env_path


def ensure_test_script(project_root: Path) -> Path:
    """Create the HeyGen avatar availability test script if it does not exist."""

    test_script_path = project_root / TEST_SCRIPT_RELATIVE_PATH
    test_script_path.parent.mkdir(parents=True, exist_ok=True)

    if not test_script_path.exists():
        test_script_path.write_text(TEST_SCRIPT_TEMPLATE)
    return test_script_path


def print_summary(env_path: Path, test_script_path: Path) -> None:
    """Output next steps and Railway instructions."""

    railway_instructions = dedent(
        """
        HeyGen avatar variables have been written to {env_path}

        To add these variables to Railway:
          1. Open your Railway project dashboard.
          2. Navigate to the "Variables" tab.
          3. For each key in .env starting with HEYGEN_AVATAR_, add the same key
             and value to Railway. You can bulk import them by clicking
             "Bulk Edit" and pasting the following JSON payload:

             {bulk_payload}

          4. Ensure `HEYGEN_API_KEY` is also added (value is your HeyGen API key).
          5. Redeploy the service or restart the container to pick up the new
             variables.

        Next steps:
          - Verify avatar availability locally via `python {test_script_path}`.
          - Confirm the application starts without warnings about missing avatars.
        """
    ).strip()

    bulk_payload = json.dumps(build_bulk_payload(), indent=2)
    print(
        railway_instructions.format(
            env_path=str(env_path),
            bulk_payload=bulk_payload,
            test_script_path=str(test_script_path),
        )
    )


TEST_SCRIPT_TEMPLATE = dedent(
    '''"""Validate access to all configured HeyGen avatars.

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
    '''
)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]

    env_path = ensure_env_file(project_root)
    test_script_path = ensure_test_script(project_root)
    print_summary(env_path, test_script_path)


if __name__ == "__main__":
    main()
