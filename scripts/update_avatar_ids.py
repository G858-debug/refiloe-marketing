#!/usr/bin/env python3
"""
Script to update photo_avatar_id values in the photo_avatar_looks table.

This script:
1. Connects to Supabase using environment variables
2. Updates each content_type with its corresponding photo_avatar_id
3. Logs each successful update
4. Handles errors gracefully

Usage:
    python scripts/update_avatar_ids.py

Environment variables required:
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.supabase_rest import SupabaseRestClient

# Try to import dotenv
try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False
    def load_dotenv(*args, **kwargs):
        pass

# Get project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Avatar ID mappings
AVATAR_MAPPINGS = {
    'workout': 'c27a07fecf6d4fd0916e5da74ba9a247',
    'fitness': '546e123c403646abb8a1b5c806000d2d',
    'professional': '921680e6ba184811aea1e72102920ff8',
    'business': 'e449aa5ff5bc4c9b970e40b4420dacbd',
    'motivational': '9150e25a09ab417fa9b3aff5482d4268',
    'educational': 'f7b5354d99454a259a405694aff6041f',
    'community': '34f4326cfa394ce0808c37179eff8dd4',
    'relatable': '8a5e863b6d4049ad80d4fc5c56d84721',
    'casual': 'e3e6f1c06c7342ae8804770543707c23',
    'announcement': '9fa2794180864cb39e1ed2e5af4d80dc',
    'outdoor': 'c056dfb7ca4c4c63abfe8b915f2d2c6a',
    'studio': '6b1ce97e7cb0492ca43632383b3c37de',
    'lifestyle': 'b36238122e054eea822e409f1a469978',
}


def ensure_env_loaded() -> None:
    """Load environment variables from .env file."""
    dotenv_path = PROJECT_ROOT / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path=dotenv_path)
        logger.info(f"Loaded environment variables from {dotenv_path}")
    else:
        load_dotenv()


def get_supabase_client() -> SupabaseRestClient:
    """Initialize Supabase client using environment variables."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        logger.error("Missing required environment variables")
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required")

    logger.info(f"Connecting to Supabase at {url}")
    return SupabaseRestClient(url, key)


def print_separator(char="=", length=80):
    """Print a separator line."""
    print(char * length)


def update_avatar_ids():
    """Update photo_avatar_id values in photo_avatar_looks table."""
    ensure_env_loaded()

    print_separator()
    print("UPDATE AVATAR IDS SCRIPT")
    print_separator()
    print(f"Run at: {datetime.now().isoformat()}")
    print_separator()

    try:
        # Connect to Supabase
        logger.info("Connecting to Supabase...")
        client = get_supabase_client()
        logger.info("Successfully connected to Supabase")
        print("\n✅ Database connection successful")

    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\nPlease ensure the following environment variables are set:")
        print("  - SUPABASE_URL")
        print("  - SUPABASE_SERVICE_KEY")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Connection Error: {e}")
        print("\nFailed to connect to Supabase. Please check your credentials.")
        sys.exit(1)

    # Track update statistics
    successful_updates = 0
    failed_updates = 0
    not_found = []
    errors = []

    print_separator()
    print(f"UPDATING {len(AVATAR_MAPPINGS)} AVATAR IDS")
    print_separator()

    # Update each content_type
    for content_type, avatar_id in AVATAR_MAPPINGS.items():
        try:
            logger.info(f"Updating {content_type} -> {avatar_id}")

            # Get current timestamp
            now = datetime.utcnow().isoformat()

            # Update the record
            result = client.table("photo_avatar_looks").update({
                "photo_avatar_id": avatar_id,
                "updated_at": now
            }).eq("content_type", content_type).execute()

            # Check if any records were updated
            if result.data and len(result.data) > 0:
                successful_updates += 1
                print(f"✅ Updated {content_type}: {avatar_id}")
                logger.info(f"Successfully updated {content_type}")
            else:
                # No records found for this content_type
                not_found.append(content_type)
                logger.warning(f"No records found for content_type: {content_type}")
                print(f"⚠️  Warning: No records found for content_type '{content_type}'")

        except Exception as e:
            failed_updates += 1
            error_msg = f"{content_type}: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Failed to update {content_type}: {e}")
            print(f"❌ Error updating {content_type}: {e}")

    # Print summary
    print_separator()
    print("UPDATE SUMMARY")
    print_separator()
    print(f"Total mappings to update: {len(AVATAR_MAPPINGS)}")
    print(f"✅ Successful updates: {successful_updates}")

    if not_found:
        print(f"⚠️  Not found (no matching records): {len(not_found)}")
        for ct in not_found:
            print(f"   - {ct}")

    if failed_updates > 0:
        print(f"❌ Failed updates: {failed_updates}")
        for error in errors:
            print(f"   - {error}")

    print_separator()

    if successful_updates == len(AVATAR_MAPPINGS):
        print("✅ ALL UPDATES COMPLETED SUCCESSFULLY!")
    elif successful_updates > 0:
        print(f"⚠️  PARTIAL SUCCESS: {successful_updates}/{len(AVATAR_MAPPINGS)} updated")
    else:
        print("❌ NO UPDATES WERE SUCCESSFUL")
        sys.exit(1)

    print_separator()


if __name__ == "__main__":
    update_avatar_ids()
