"""
Migration script to create the leonardo_reference_images table in Supabase.
This table stores reference images for Leonardo AI character consistency.

Before running this Python script, execute the SQL in Supabase Dashboard:
1. Go to Supabase Dashboard > SQL Editor
2. Paste and run the contents of scripts/migrations/sql/leonardo_reference_images.sql
3. Then optionally run: python scripts/migrations/create_leonardo_reference_images_table.py
"""

import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from supabase import create_client, Client
from utils.logger import log_info, log_error, log_warning


def get_supabase_client() -> Client:
    """Initialize Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required")
    return create_client(url, key)


def check_table_exists(client: Client) -> bool:
    """Check if the leonardo_reference_images table exists."""
    try:
        result = client.table("leonardo_reference_images").select("id").limit(1).execute()
        return True
    except Exception as e:
        if "relation" in str(e).lower() and "does not exist" in str(e).lower():
            return False
        # Re-raise if it's a different error
        raise


def run_migration():
    """Create the leonardo_reference_images table and verify setup."""
    log_info("Starting leonardo_reference_images table migration check...")

    client = get_supabase_client()

    # Check if table exists
    if check_table_exists(client):
        log_info("✅ leonardo_reference_images table already exists")

        # Get count of existing records
        try:
            result = client.table("leonardo_reference_images").select("id", count="exact").execute()
            count = result.count if hasattr(result, 'count') else len(result.data or [])
            log_info(f"📊 Table contains {count} reference image(s)")
        except Exception as e:
            log_warning(f"Could not count records: {e}")

        return True
    else:
        log_warning("⚠️  Table does not exist!")
        log_info("")
        log_info("Please create the table by running this SQL in Supabase Dashboard:")
        log_info("-" * 60)

        sql_path = os.path.join(
            os.path.dirname(__file__),
            "sql",
            "leonardo_reference_images.sql"
        )

        if os.path.exists(sql_path):
            with open(sql_path, 'r') as f:
                print(f.read())
        else:
            print("""
CREATE TABLE IF NOT EXISTS leonardo_reference_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    supabase_storage_url TEXT NOT NULL,
    leonardo_image_id VARCHAR(100),
    leonardo_upload_status VARCHAR(20) DEFAULT 'pending',
    last_leonardo_upload TIMESTAMPTZ,
    last_used TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
""")

        log_info("-" * 60)
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
