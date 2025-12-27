#!/usr/bin/env python3
"""Script to inspect text card posts in Supabase database."""

import os
import sys
import json

# Try to load from .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from utils.supabase_rest import SupabaseRestClient

def main():
    # Initialize Supabase client - check environment first, then command line args
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_ANON_KEY')

    # Allow passing credentials via command line for testing
    if len(sys.argv) >= 3:
        supabase_url = sys.argv[1]
        supabase_key = sys.argv[2]
        print("Using credentials from command line arguments")

    if not supabase_url or not supabase_key:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY/SUPABASE_ANON_KEY")
        print("\nUsage: python inspect_text_cards.py [SUPABASE_URL] [SUPABASE_KEY]")
        print("   Or set environment variables: SUPABASE_URL and SUPABASE_SERVICE_KEY")
        return

    client = SupabaseRestClient(supabase_url, supabase_key)

    print("=" * 80)
    print("INSPECTING TEXT CARD POSTS IN SUPABASE")
    print("=" * 80)

    # Query 1: Get posts where post_type='text_card'
    print("\n1. Querying for posts where post_type='text_card'...")
    print("-" * 60)

    result1 = client.table('social_posts').select('*').eq('post_type', 'text_card').order('created_at', desc=True).limit(20).execute()

    if result1.data:
        print(f"Found {len(result1.data)} posts with post_type='text_card'")
        for i, post in enumerate(result1.data, 1):
            print(f"\n--- Post {i} ---")
            print(f"  ID: {post.get('id')}")
            print(f"  post_type: {post.get('post_type')}")
            print(f"  status: {post.get('status')}")
            print(f"  platform: {post.get('platform')}")
            print(f"  content_theme: {post.get('content_theme')}")
            print(f"  image_url: {post.get('image_url', 'None')[:80] if post.get('image_url') else 'None'}...")
            print(f"  media_url: {post.get('media_url', 'None')[:80] if post.get('media_url') else 'None'}...")
            print(f"  carousel_image_urls: {post.get('carousel_image_urls')}")
            print(f"  scheduled_time: {post.get('scheduled_time')}")
            print(f"  created_at: {post.get('created_at')}")
            print(f"  content_text preview: {(post.get('content_text') or '')[:100]}...")
    else:
        print("No posts found with post_type='text_card'")

    # Query 2: Check if there's a 'content_type' column (may not exist)
    print("\n\n2. Checking database columns by looking at a sample post...")
    print("-" * 60)

    sample = client.table('social_posts').select('*').limit(1).execute()
    if sample.data:
        print("Available columns in social_posts table:")
        for key in sorted(sample.data[0].keys()):
            print(f"  - {key}")

    # Query 3: Get text cards with status='scheduled_on_facebook'
    print("\n\n3. Querying for text_card posts with status='scheduled_on_facebook'...")
    print("-" * 60)

    result3 = client.table('social_posts').select('*').eq('post_type', 'text_card').eq('status', 'scheduled_on_facebook').order('created_at', desc=True).limit(20).execute()

    if result3.data:
        print(f"Found {len(result3.data)} text_card posts with status='scheduled_on_facebook'")
        for i, post in enumerate(result3.data, 1):
            print(f"\n--- Post {i} ---")
            print(f"  ID: {post.get('id')}")
            print(f"  status: {post.get('status')}")
            print(f"  content_theme: {post.get('content_theme')}")
            print(f"  image_url: {post.get('image_url', 'None')[:80] if post.get('image_url') else 'None'}...")
            print(f"  scheduled_time: {post.get('scheduled_time')}")
            print(f"  facebook_post_id: {post.get('facebook_post_id')}")
    else:
        print("No text_card posts found with status='scheduled_on_facebook'")

    # Query 4: Get all text_card statuses summary
    print("\n\n4. Summary of all text_card post statuses...")
    print("-" * 60)

    all_text_cards = client.table('social_posts').select('id,status,post_type').eq('post_type', 'text_card').execute()

    if all_text_cards.data:
        status_counts = {}
        for post in all_text_cards.data:
            status = post.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

        print(f"Total text_card posts: {len(all_text_cards.data)}")
        print("\nStatus breakdown:")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")
    else:
        print("No text_card posts found")

    # Query 5: Check for any posts that might have text_card in content_theme
    print("\n\n5. Checking for posts with 'text_card' in content_theme...")
    print("-" * 60)

    # This might help find text card content that wasn't typed correctly
    all_posts = client.table('social_posts').select('id,post_type,status,content_theme,image_url').order('created_at', desc=True).limit(100).execute()

    if all_posts.data:
        text_card_themes = [p for p in all_posts.data if 'text' in (p.get('content_theme') or '').lower()]
        if text_card_themes:
            print(f"Found {len(text_card_themes)} posts with 'text' in content_theme:")
            for p in text_card_themes[:10]:
                print(f"  ID: {p.get('id')[:8]}... | post_type: {p.get('post_type')} | status: {p.get('status')} | theme: {p.get('content_theme')}")
        else:
            print("No posts found with 'text' in content_theme")

    print("\n" + "=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
