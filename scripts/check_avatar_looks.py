#!/usr/bin/env python3
"""
Diagnostic script to check what's in the photo_avatar_looks table.

This script:
1. Connects to Supabase using the same credentials as the main app
2. Query the photo_avatar_looks table and print all records
3. Show count of total records
4. Show count by content_type
5. Show which one is marked as default
6. Print the full details of each record in a readable format

Usage:
    python scripts/check_avatar_looks.py

Environment variables required:
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client, Client

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    """Initialize Supabase client using environment variables."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        logger.error("Missing required environment variables")
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required")

    logger.info(f"Connecting to Supabase at {url}")
    return create_client(url, key)


def print_separator(char="=", length=80):
    """Print a separator line."""
    print(char * length)


def print_record(record: dict, index: int):
    """Print a single record in a readable format."""
    print(f"\n[{index}] Content Type: {record.get('content_type', 'N/A')}")
    print(f"    Label: {record.get('label', 'N/A')}")
    print(f"    Photo Avatar ID: {record.get('photo_avatar_id', 'N/A')}")
    print(f"    Is Active: {record.get('is_active', 'N/A')}")
    print(f"    Is Default: {record.get('is_default', 'N/A')} {'⭐ DEFAULT' if record.get('is_default') else ''}")
    print(f"    Outfit: {record.get('outfit_description', 'N/A')[:80]}...")
    print(f"    Environment: {record.get('environment_description', 'N/A')[:80]}...")
    print(f"    Created At: {record.get('created_at', 'N/A')}")
    print(f"    Updated At: {record.get('updated_at', 'N/A')}")


def check_avatar_looks():
    """Check and display contents of photo_avatar_looks table."""
    print_separator()
    print("PHOTO AVATAR LOOKS DIAGNOSTIC SCRIPT")
    print_separator()
    print(f"Run at: {datetime.now().isoformat()}")
    print_separator()

    try:
        # Connect to Supabase
        logger.info("Connecting to Supabase...")
        client = get_supabase_client()
        logger.info("Successfully connected to Supabase")

        # Test connection
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

    try:
        # Query the table
        logger.info("Querying photo_avatar_looks table...")
        result = client.table("photo_avatar_looks").select("*").execute()

        # Check if table exists and has data
        if not hasattr(result, 'data'):
            print("\n❌ Error: Unexpected response format from database")
            sys.exit(1)

        records = result.data

        if not records or len(records) == 0:
            print("\n⚠️  No records found in photo_avatar_looks table")
            print("\nThe table exists but is empty. You may need to run the seed script:")
            print("  python scripts/seed_avatar_looks.py")
            sys.exit(0)

        # Print summary statistics
        print_separator()
        print("SUMMARY STATISTICS")
        print_separator()
        print(f"Total Records: {len(records)}")

        # Count by content_type
        content_types = {}
        default_record = None
        active_count = 0
        inactive_count = 0

        for record in records:
            content_type = record.get('content_type', 'unknown')
            content_types[content_type] = content_types.get(content_type, 0) + 1

            if record.get('is_default'):
                default_record = record

            if record.get('is_active'):
                active_count += 1
            else:
                inactive_count += 1

        print(f"\nActive Records: {active_count}")
        print(f"Inactive Records: {inactive_count}")

        print("\nContent Types:")
        for content_type, count in sorted(content_types.items()):
            print(f"  - {content_type}: {count}")

        # Print default record info
        print_separator()
        print("DEFAULT AVATAR LOOK")
        print_separator()
        if default_record:
            print(f"✅ Default: {default_record.get('content_type')} ({default_record.get('label')})")
            print(f"   Photo Avatar ID: {default_record.get('photo_avatar_id')}")
        else:
            print("⚠️  No default avatar look set!")
            print("   This may cause issues with content generation.")

        # Print all records
        print_separator()
        print("ALL RECORDS")
        print_separator()

        # Sort records by content_type
        sorted_records = sorted(records, key=lambda x: x.get('content_type', ''))

        for index, record in enumerate(sorted_records, 1):
            print_record(record, index)

        # Final summary
        print_separator()
        print("DIAGNOSTIC COMPLETE")
        print_separator()
        print(f"✅ Successfully retrieved {len(records)} records")
        print(f"✅ Default avatar look: {default_record.get('content_type') if default_record else 'NOT SET'}")
        print(f"✅ Active avatars: {active_count}/{len(records)}")

        if not default_record:
            print("\n⚠️  WARNING: No default avatar look is set!")

        if inactive_count > 0:
            print(f"\n⚠️  Note: {inactive_count} avatar(s) are inactive")

        print_separator()

    except Exception as e:
        error_message = str(e).lower()

        if 'relation' in error_message and 'does not exist' in error_message:
            print("\n❌ Table Error: photo_avatar_looks table does not exist")
            print("\nThe table needs to be created. Please run:")
            print("  1. Execute SQL: scripts/migrations/sql/photo_avatar_looks.sql")
            print("  2. Run migration: python scripts/migrations/create_photo_avatar_looks_table.py")
            sys.exit(1)
        elif 'permission denied' in error_message or 'insufficient privileges' in error_message:
            print("\n❌ Permission Error: Insufficient database permissions")
            print("\nPlease ensure you're using SUPABASE_SERVICE_KEY (not SUPABASE_ANON_KEY)")
            sys.exit(1)
        else:
            print(f"\n❌ Query Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    check_avatar_looks()
