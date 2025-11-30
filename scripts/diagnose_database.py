#!/usr/bin/env python3
"""
Database Schema Diagnostic Script
Checks all social media tables and reports missing columns
"""

import os
import sys
from supabase import create_client

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def check_table_exists(supabase, table_name):
    """Check if a table exists"""
    try:
        result = supabase.table(table_name).select('*').limit(1).execute()
        return True
    except Exception as e:
        if '404' in str(e) or 'not found' in str(e).lower():
            return False
        print(f"Error checking {table_name}: {e}")
        return False

def get_table_columns(supabase, table_name):
    """Get columns of a table by fetching one row"""
    try:
        result = supabase.table(table_name).select('*').limit(1).execute()
        if result.data and len(result.data) > 0:
            return list(result.data[0].keys())
        return []
    except Exception as e:
        print(f"Error getting columns for {table_name}: {e}")
        return []

def main():
    # Connect to Supabase
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')

    if not supabase_url or not supabase_key:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
        sys.exit(1)

    supabase = create_client(supabase_url, supabase_key)

    print("=" * 80)
    print("DATABASE SCHEMA DIAGNOSTIC REPORT")
    print("=" * 80)
    print()

    # Tables we need
    tables = {
        'social_posts': [
            'id', 'post_type', 'platform', 'caption_text', 'title',
            'content_theme', 'scheduled_time', 'published_time', 'status',
            'video_url', 'thumbnail_url', 'video_duration', 'video_type',
            'video_style', 'has_captions', 'completion_rate', 'avg_watch_time',
            'image_ids', 'created_at', 'updated_at'
        ],
        'avatar_looks': [
            'id', 'look_id', 'photo_avatar_id', 'status', 'look_type',
            'prompt', 'group_id', 'preview_url', 'image_urls', 'image_keys',
            'created_at', 'updated_at', 'look_config', 'has_motion',
            'motion_id', 'motion_prompt', 'motion_type'
        ],
        'social_images': [
            'id', 'post_id', 'image_url', 'image_type', 'created_at'
        ]
    }

    issues_found = []

    for table_name, expected_columns in tables.items():
        print(f"\nChecking table: {table_name}")
        print("-" * 80)

        # Check if table exists
        exists = check_table_exists(supabase, table_name)

        if not exists:
            print(f"  ❌ TABLE DOES NOT EXIST")
            issues_found.append(f"Table '{table_name}' does not exist")
            print(f"  → Need to create table with columns: {expected_columns}")
        else:
            print(f"  ✅ Table exists")

            # Get actual columns
            actual_columns = get_table_columns(supabase, table_name)

            if actual_columns:
                print(f"  📋 Actual columns ({len(actual_columns)}): {actual_columns}")

                # Check for missing columns
                missing = set(expected_columns) - set(actual_columns)
                extra = set(actual_columns) - set(expected_columns)

                if missing:
                    print(f"  ⚠️  Missing columns: {list(missing)}")
                    issues_found.append(f"Table '{table_name}' missing columns: {list(missing)}")

                if extra:
                    print(f"  ℹ️  Extra columns: {list(extra)}")
            else:
                print(f"  ⚠️  Table is empty, cannot detect columns")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if issues_found:
        print(f"\n❌ Found {len(issues_found)} issues:\n")
        for i, issue in enumerate(issues_found, 1):
            print(f"{i}. {issue}")
        print("\n→ Run the migration SQL to fix these issues")
        sys.exit(1)
    else:
        print("\n✅ All tables and columns are correctly configured!")
        sys.exit(0)

if __name__ == '__main__':
    main()
