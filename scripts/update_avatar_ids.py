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
    'workout': '96c419d3058444069ab8e28308fdc834',
    'fitness': '291df9103e744984be41715e649ae8e6',
    'professional': '64a1ca313daf488698bebb282aa87dae',
    'business': '331e5ac30c914d5abeb2853be17a8532',
    'motivational': 'd0c9ad8674ef49b79f618dd5303e50df',
    'educational': '55bdbaaa7ded40458bfc0e498ff24ae6',
    'community': '6a7f86c8c60544d497ae63695af00425',
    'relatable': 'b6bb73219ff54f5eb2934b3047bf028f',
    'casual': 'a33ab8bbeff5499a96ae613e5497247c',
    'announcement': 'e4fc74c588ba45ec9eb49020bd95417d',
    'outdoor': '79938b6165b649b9b724d1af99a3b4b5',
    'studio': '4a5842d1f4de4d0ab4d0cb832b71a1d3',
    'lifestyle': '4c621fd3eae84def9dfcc5f25bd83c93',
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
