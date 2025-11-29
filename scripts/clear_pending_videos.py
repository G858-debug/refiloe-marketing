#!/usr/bin/env python3
"""
Script to clear pending videos from the social_posts table.

This script:
1. Connects to Supabase using environment variables
2. Queries for video posts with pending/scheduled status
3. Updates their status to 'cancelled'
4. Provides detailed logging of the operation
"""

import os
import sys
from typing import List, Dict, Any

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.supabase_rest import SupabaseRestClient
from utils.logger import log_info, log_error, log_warning


def get_supabase_client() -> SupabaseRestClient:
    """
    Initialize and return a Supabase client using environment variables.

    Returns:
        SupabaseRestClient: Initialized Supabase client

    Raises:
        ValueError: If required environment variables are missing
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url:
        raise ValueError("SUPABASE_URL environment variable is not set")
    if not key:
        raise ValueError("SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY environment variable is not set")

    log_info(f"Connecting to Supabase at {url}")
    return SupabaseRestClient(url, key)


def get_pending_videos(client: SupabaseRestClient) -> List[Dict[str, Any]]:
    """
    Query the social_posts table for video posts with pending/scheduled status.

    Args:
        client: Initialized Supabase client

    Returns:
        List of video posts matching the criteria
    """
    statuses_to_query = ['pending', 'pending_approval', 'scheduled']
    all_posts = []

    log_info("Querying for pending/scheduled video posts...")

    # Query for each status separately since we don't have an .in_() method
    for status in statuses_to_query:
        try:
            log_info(f"  Checking posts with status: {status}")
            result = (
                client
                .table('social_posts')
                .select('*')
                .eq('status', status)
                .execute()
            )

            if result.data:
                # Filter for video posts (post_type contains 'video')
                video_posts = [
                    post for post in result.data
                    if post.get('post_type') and 'video' in post.get('post_type', '').lower()
                ]

                if video_posts:
                    log_info(f"    Found {len(video_posts)} video post(s) with status '{status}'")
                    all_posts.extend(video_posts)

        except Exception as e:
            log_error(f"Error querying posts with status '{status}': {str(e)}")
            raise

    return all_posts


def cancel_videos(client: SupabaseRestClient, posts: List[Dict[str, Any]]) -> int:
    """
    Update the status of video posts to 'cancelled'.

    Args:
        client: Initialized Supabase client
        posts: List of posts to cancel

    Returns:
        Number of successfully cancelled posts
    """
    cancelled_count = 0

    log_info(f"\nUpdating {len(posts)} video post(s) to 'cancelled' status...")

    for post in posts:
        post_id = post.get('id')
        post_type = post.get('post_type', 'unknown')
        current_status = post.get('status', 'unknown')

        try:
            result = (
                client
                .table('social_posts')
                .update({'status': 'cancelled'})
                .eq('id', post_id)
                .execute()
            )

            if result.data:
                log_info(f"  ✓ Cancelled post ID: {post_id} (type: {post_type}, was: {current_status})")
                cancelled_count += 1
            else:
                log_warning(f"  ⚠ Failed to cancel post ID: {post_id} - No data returned")

        except Exception as e:
            log_error(f"  ✗ Error cancelling post ID {post_id}: {str(e)}")
            # Continue with other posts even if one fails
            continue

    return cancelled_count


def main():
    """Main execution function."""
    try:
        log_info("=" * 60)
        log_info("Starting Clear Pending Videos Script")
        log_info("=" * 60)

        # Initialize Supabase client
        client = get_supabase_client()
        log_info("✓ Supabase client initialized successfully\n")

        # Get pending video posts
        pending_videos = get_pending_videos(client)

        # Print summary
        log_info("\n" + "=" * 60)
        log_info(f"FOUND: {len(pending_videos)} video post(s) to cancel")
        log_info("=" * 60)

        if not pending_videos:
            log_info("\nNo pending videos found. Nothing to do.")
            return 0

        # Show details of posts that will be cancelled
        log_info("\nPosts to be cancelled:")
        for post in pending_videos:
            post_id = post.get('id', 'unknown')
            post_type = post.get('post_type', 'unknown')
            status = post.get('status', 'unknown')
            created_at = post.get('created_at', 'unknown')
            log_info(f"  - ID: {post_id}, Type: {post_type}, Status: {status}, Created: {created_at}")

        # Cancel the videos
        cancelled_count = cancel_videos(client, pending_videos)

        # Final summary
        log_info("\n" + "=" * 60)
        log_info(f"COMPLETED: Successfully cancelled {cancelled_count}/{len(pending_videos)} video post(s)")
        log_info("=" * 60)

        if cancelled_count < len(pending_videos):
            log_warning(f"\nWarning: {len(pending_videos) - cancelled_count} post(s) failed to cancel")
            return 1

        return 0

    except ValueError as e:
        log_error(f"\nConfiguration Error: {str(e)}")
        log_error("Please ensure SUPABASE_URL and SUPABASE_SERVICE_KEY are set in your environment")
        return 1

    except Exception as e:
        log_error(f"\nUnexpected Error: {str(e)}")
        import traceback
        log_error(f"Traceback:\n{traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
