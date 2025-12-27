#!/usr/bin/env python3
"""
Debug script to query and inspect carousel post data.
Run with: python scripts/debug_carousel_post.py
"""
import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Use environment variables directly (no .env file needed)
# from dotenv import load_dotenv
# load_dotenv()

from utils.supabase_rest import SupabaseRestClient

def safe_json_parse(val):
    """Safely parse a value that might be JSON."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val

def print_separator(title=""):
    """Print a nice separator."""
    print("\n" + "=" * 80)
    if title:
        print(f" {title}")
        print("=" * 80)

def debug_carousel_post(post_id: str):
    """Debug a specific carousel post by querying all relevant fields."""

    # Initialize Supabase
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')

    if not url or not key:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
        return None

    client = SupabaseRestClient(url, key)

    print(f"\n🔍 Querying post: {post_id}")
    print("-" * 60)

    # Query the post
    result = client.table('social_posts').select('*').eq('id', post_id).execute()

    if not result.data:
        print(f"❌ Post not found with ID: {post_id}")
        return None

    post = result.data[0]

    # Print basic info
    print_separator("BASIC POST INFO")
    print(f"ID: {post.get('id')}")
    print(f"Title: {post.get('title')}")
    print(f"Post Type: {post.get('post_type')}")
    print(f"Status: {post.get('status')}")
    print(f"Platform: {post.get('platform')}")
    print(f"Created: {post.get('created_at')}")

    # Print carousel_data
    print_separator("CAROUSEL_DATA FIELD")
    carousel_data_raw = post.get('carousel_data')
    if carousel_data_raw:
        print(f"Type: {type(carousel_data_raw)}")
        carousel_data = safe_json_parse(carousel_data_raw)
        print(f"Parsed type: {type(carousel_data)}")
        print("\nFull carousel_data content:")
        print(json.dumps(carousel_data, indent=2, default=str))
    else:
        print("❌ carousel_data is NULL/empty")

    # Print generation_prompt
    print_separator("GENERATION_PROMPT FIELD")
    generation_prompt_raw = post.get('generation_prompt')
    if generation_prompt_raw:
        print(f"Type: {type(generation_prompt_raw)}")
        generation_prompt = safe_json_parse(generation_prompt_raw)
        print(f"Parsed type: {type(generation_prompt)}")
        print("\nFull generation_prompt content:")
        print(json.dumps(generation_prompt, indent=2, default=str))

        # Check for carousel data inside generation_prompt
        if isinstance(generation_prompt, dict):
            inner_carousel = generation_prompt.get('carousel_data') or generation_prompt.get('carousel_slides')
            if inner_carousel:
                print("\n--- Extracted carousel_data from generation_prompt ---")
                inner_parsed = safe_json_parse(inner_carousel)
                print(json.dumps(inner_parsed, indent=2, default=str))
    else:
        print("❌ generation_prompt is NULL/empty")

    # Print content_text/content
    print_separator("CONTENT/CAPTION FIELDS")
    content_text = post.get('content_text')
    content = post.get('content')
    caption = post.get('caption')

    print(f"content_text (first 500 chars):")
    if content_text:
        print(content_text[:500])
    else:
        print("❌ content_text is NULL/empty")

    print(f"\ncontent (first 500 chars):")
    if content:
        print(str(content)[:500])
    else:
        print("❌ content is NULL/empty")

    print(f"\ncaption (first 500 chars):")
    if caption:
        print(str(caption)[:500])
    else:
        print("❌ caption is NULL/empty")

    # Print media_url
    print_separator("MEDIA_URL FIELD")
    media_url_raw = post.get('media_url')
    if media_url_raw:
        print(f"Type: {type(media_url_raw)}")
        media_urls = safe_json_parse(media_url_raw)
        if isinstance(media_urls, list):
            print(f"Number of carousel slides: {len(media_urls)}")
            for i, url in enumerate(media_urls):
                print(f"  Slide {i+1}: {url[:80]}...")
        else:
            print(f"Single URL: {media_url_raw[:80]}...")
    else:
        print("❌ media_url is NULL/empty")

    # Analysis
    print_separator("ANALYSIS & DIAGNOSIS")

    # Determine where carousel content should come from
    carousel_data = safe_json_parse(post.get('carousel_data'))
    generation_prompt = safe_json_parse(post.get('generation_prompt'))

    carousel_source = None
    slides = None

    if carousel_data:
        if isinstance(carousel_data, dict) and carousel_data.get('slides'):
            carousel_source = "carousel_data field (dict with slides)"
            slides = carousel_data.get('slides')
        elif isinstance(carousel_data, list):
            carousel_source = "carousel_data field (raw list)"
            slides = carousel_data

    if not slides and generation_prompt:
        if isinstance(generation_prompt, dict):
            inner = generation_prompt.get('carousel_data') or generation_prompt.get('carousel_slides')
            if inner:
                inner = safe_json_parse(inner)
                if isinstance(inner, dict) and inner.get('slides'):
                    carousel_source = "generation_prompt.carousel_data (dict with slides)"
                    slides = inner.get('slides')
                elif isinstance(inner, list):
                    carousel_source = "generation_prompt.carousel_slides (raw list)"
                    slides = inner

    if slides:
        print(f"✅ Found carousel slides from: {carousel_source}")
        print(f"   Number of slides: {len(slides)}")
        print("\n   Slide structure analysis:")
        for i, slide in enumerate(slides):
            if isinstance(slide, dict):
                print(f"\n   Slide {i+1}:")
                print(f"      Keys: {list(slide.keys())}")
                for key, val in slide.items():
                    val_preview = str(val)[:100] if val else "NULL"
                    print(f"      {key}: {val_preview}")
            else:
                print(f"   Slide {i+1}: Not a dict - {type(slide)}: {str(slide)[:100]}")
    else:
        print("❌ NO CAROUSEL SLIDES FOUND!")
        print("   The system will fall back to parsing content_text as a caption.")

        # Check if content_text can be parsed
        content_text = post.get('content_text', '')
        if content_text:
            lines = [l.strip() for l in content_text.split('\n') if l.strip()]
            print(f"\n   Content text has {len(lines)} non-empty lines:")
            for i, line in enumerate(lines[:5]):
                print(f"      Line {i+1}: {line[:80]}...")

    # Check for common issues
    print("\n   Common issues check:")

    if slides:
        for i, slide in enumerate(slides):
            if isinstance(slide, dict):
                # Check for description content
                text = slide.get('text', '')
                desc = slide.get('description', '')
                bullets = slide.get('bullets', [])
                step_title = slide.get('step_title', '')

                if i > 0:  # Content slides (not cover)
                    if not desc and not bullets:
                        print(f"   ⚠️  Slide {i+1} has NO description/bullets - will show only title!")
                    elif desc:
                        print(f"   ✅ Slide {i+1} has description ({len(desc)} chars)")
                    elif bullets:
                        print(f"   ✅ Slide {i+1} has {len(bullets)} bullets")

    return {
        'post_id': post_id,
        'carousel_data': safe_json_parse(post.get('carousel_data')),
        'generation_prompt': safe_json_parse(post.get('generation_prompt')),
        'content_text': post.get('content_text'),
        'caption': post.get('caption', ''),
        'title': post.get('title'),
        'media_url': safe_json_parse(post.get('media_url')),
    }


if __name__ == '__main__':
    # The specific post ID to debug
    POST_ID = "77b5b9a2-1dab-499e-9ce6-07948d062c68"

    print("=" * 80)
    print(" CAROUSEL POST DEBUGGER")
    print("=" * 80)

    result = debug_carousel_post(POST_ID)

    if result:
        print_separator("RAW JSON OUTPUT")
        print(json.dumps(result, indent=2, default=str))
