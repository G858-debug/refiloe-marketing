"""
Single source of truth for HeyGen Photo Avatar IDs.

This file contains all avatar ID mappings. Import from here in all other files.
Do NOT duplicate these IDs elsewhere in the codebase.

To update avatar IDs:
1. Update this file
2. Run the SQL in scripts/sql/update_avatar_ids.sql (generated from this file)
3. Deploy
"""

from typing import Dict

# =============================================================================
# AVATAR ID REGISTRY - Single Source of Truth
# =============================================================================

AVATAR_IDS: Dict[str, str] = {
    "workout": "c27a07fecf6d4fd0916e5da74ba9a247",
    "fitness": "546e123c403646abb8a1b5c806000d2d",
    "professional": "921680e6ba184811aea1e72102920ff8",
    "business": "e449aa5ff5bc4c9b970e40b4420dacbd",
    "motivational": "9150e25a09ab417fa9b3aff5482d4268",
    "educational": "f7b5354d99454a259a405694aff6041f",
    "community": "34f4326cfa394ce0808c37179eff8dd4",
    "relatable": "8a5e863b6d4049ad80d4fc5c56d84721",
    "casual": "e3e6f1c06c7342ae8804770543707c23",
    "announcement": "9fa2794180864cb39e1ed2e5af4d80dc",
    "outdoor": "c056dfb7ca4c4c63abfe8b915f2d2c6a",
    "studio": "6b1ce97e7cb0492ca43632383b3c37de",
    "lifestyle": "b36238122e054eea822e409f1a469978",
}

# Default avatar (casual look)
DEFAULT_AVATAR_ID: str = AVATAR_IDS["casual"]

# For backward compatibility
PHOTO_AVATAR_REGISTRY = AVATAR_IDS
DEFAULT_PHOTO_AVATAR_ID = DEFAULT_AVATAR_ID


def get_avatar_id(content_type: str) -> str:
    """Get avatar ID for a content type, with fallback to default."""
    return AVATAR_IDS.get(content_type, DEFAULT_AVATAR_ID)


def generate_sql_update() -> str:
    """Generate SQL to update the database with current avatar IDs."""
    lines = [
        "-- Auto-generated from social_media/config/avatar_ids.py",
        "-- Run this in Supabase SQL Editor after updating avatar_ids.py",
        ""
    ]
    for content_type, avatar_id in AVATAR_IDS.items():
        lines.append(f"UPDATE photo_avatar_looks SET photo_avatar_id = '{avatar_id}', updated_at = NOW() WHERE content_type = '{content_type}';")
    return "\n".join(lines)


if __name__ == "__main__":
    # When run directly, print the SQL update statements
    print(generate_sql_update())
