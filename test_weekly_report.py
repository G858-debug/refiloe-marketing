#!/usr/bin/env python3
"""
Test script for the weekly report generator.

This script tests the weekly report generation functionality without
requiring scheduled execution.
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from utils.supabase_rest import SupabaseRestClient
from social_media.weekly_report import generate_weekly_report


def main():
    """Test the weekly report generator."""
    print("=" * 80)
    print("WEEKLY REPORT GENERATOR TEST")
    print("=" * 80)
    print()

    # Check environment variables
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')

    if not supabase_url or not supabase_key:
        print("❌ ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY/SUPABASE_ANON_KEY")
        print("Please set these environment variables before running the test.")
        sys.exit(1)

    print("✅ Environment variables found")
    print(f"   Supabase URL: {supabase_url}")
    print()

    # Create Supabase client
    try:
        supabase_client = SupabaseRestClient(supabase_url, supabase_key)
        print("✅ Supabase client created successfully")
        print()
    except Exception as e:
        print(f"❌ Failed to create Supabase client: {e}")
        sys.exit(1)

    # Test text format
    print("-" * 80)
    print("TEST 1: Generating report in TEXT format")
    print("-" * 80)
    try:
        result = generate_weekly_report(
            supabase_client,
            output_format="text"
        )

        if result.get("success"):
            print("✅ Text report generated successfully")
            print()
            print(result.get("report", ""))
            print()
        else:
            print(f"❌ Text report generation failed: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Exception during text report generation: {e}")
        import traceback
        traceback.print_exc()

    # Test JSON format
    print()
    print("-" * 80)
    print("TEST 2: Generating report in JSON format")
    print("-" * 80)
    try:
        result = generate_weekly_report(
            supabase_client,
            output_format="json"
        )

        if result.get("success"):
            print("✅ JSON report generated successfully")
            print()
            print("JSON Report (first 500 characters):")
            print(result.get("report", "")[:500])
            print("...")
            print()
        else:
            print(f"❌ JSON report generation failed: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Exception during JSON report generation: {e}")
        import traceback
        traceback.print_exc()

    # Test HTML format
    print()
    print("-" * 80)
    print("TEST 3: Generating report in HTML format")
    print("-" * 80)
    try:
        result = generate_weekly_report(
            supabase_client,
            output_format="html"
        )

        if result.get("success"):
            print("✅ HTML report generated successfully")
            print()
            print("HTML Report (first 500 characters):")
            print(result.get("report", "")[:500])
            print("...")
            print()

            # Optionally save HTML to file for preview
            html_file = "/tmp/weekly_report_test.html"
            with open(html_file, "w") as f:
                f.write(result.get("report", ""))
            print(f"📄 HTML report saved to: {html_file}")
            print()
        else:
            print(f"❌ HTML report generation failed: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Exception during HTML report generation: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()
