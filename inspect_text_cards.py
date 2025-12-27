#!/usr/bin/env python3
"""
Text Card Inspection Script

Usage: python inspect_text_cards.py "SUPABASE_URL" "SUPABASE_SERVICE_KEY"
"""
import sys
import json
import requests
from datetime import datetime, timezone

def main():
    if len(sys.argv) != 3:
        print("Usage: python inspect_text_cards.py SUPABASE_URL SUPABASE_SERVICE_KEY")
        sys.exit(1)

    supabase_url = sys.argv[1]
    supabase_key = sys.argv[2]

    print("=" * 70)
    print("TEXT CARD INSPECTION REPORT")
    print("=" * 70)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Query Supabase REST API directly
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }

    # Fetch all text_card posts
    url = f"{supabase_url}/rest/v1/social_posts?post_type=eq.text_card&order=scheduled_time.desc"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code} - {response.text}")
        sys.exit(1)

    text_cards = response.json()
    total_count = len(text_cards)

    print(f"📊 TOTAL TEXT CARDS: {total_count}")
    print("-" * 70)

    # Status breakdown
    status_counts = {}
    has_image_url = 0
    has_facebook_post_id = 0

    for card in text_cards:
        status = card.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
        if card.get('image_url'):
            has_image_url += 1
        if card.get('facebook_post_id'):
            has_facebook_post_id += 1

    print("\n📈 STATUS BREAKDOWN:")
    for status, count in sorted(status_counts.items()):
        pct = (count / total_count * 100) if total_count > 0 else 0
        print(f"   {status}: {count} ({pct:.1f}%)")

    print(f"\n🖼️  IMAGE URL ANALYSIS:")
    print(f"   With image_url: {has_image_url} ({(has_image_url/total_count*100) if total_count else 0:.1f}%)")
    print(f"   Without image_url: {total_count - has_image_url}")

    print(f"\n📘 FACEBOOK POST ID ANALYSIS:")
    print(f"   With facebook_post_id: {has_facebook_post_id}")
    print(f"   Without facebook_post_id: {total_count - has_facebook_post_id}")

    # Recent examples
    print("\n" + "=" * 70)
    print("📋 RECENT TEXT CARDS (Last 15)")
    print("=" * 70)

    for card in text_cards[:15]:
        post_id = card.get('id', 'N/A')
        status = card.get('status', 'N/A')
        scheduled_time = card.get('scheduled_time', 'N/A')
        image_url = card.get('image_url', None)
        fb_post_id = card.get('facebook_post_id', None)
        caption = card.get('caption', '')[:50] + '...' if card.get('caption') and len(card.get('caption', '')) > 50 else card.get('caption', 'N/A')

        # Parse metadata
        metadata = card.get('generation_prompt', {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}

        text_card_type = metadata.get('text_card_type', 'N/A')

        print(f"\n🔹 ID: {post_id}")
        print(f"   Status: {status}")
        print(f"   Scheduled: {scheduled_time}")
        print(f"   Type: {text_card_type}")
        print(f"   Image URL: {'✅ Yes' if image_url else '❌ No'}{' ('+image_url[:60]+'...)' if image_url and len(image_url) > 60 else (' ('+image_url+')' if image_url else '')}")
        print(f"   FB Post ID: {fb_post_id or 'None'}")
        print(f"   Caption: {caption}")

    # Cards missing image_url
    missing_image = [c for c in text_cards if not c.get('image_url')]
    if missing_image:
        print("\n" + "=" * 70)
        print(f"⚠️  TEXT CARDS WITHOUT IMAGE_URL ({len(missing_image)} total)")
        print("=" * 70)
        for card in missing_image[:10]:
            print(f"\n   ID: {card.get('id')}")
            print(f"   Status: {card.get('status')}")
            print(f"   Scheduled: {card.get('scheduled_time')}")

    # Upcoming scheduled cards
    now = datetime.now(timezone.utc)
    upcoming = [c for c in text_cards if c.get('status') in ('scheduled', 'scheduled_on_facebook') and c.get('scheduled_time')]
    upcoming_valid = []
    for c in upcoming:
        try:
            sched_str = c.get('scheduled_time', '')
            # Handle various datetime formats
            if 'T' in sched_str:
                if '+' in sched_str:
                    sched_time = datetime.fromisoformat(sched_str.replace('Z', '+00:00'))
                else:
                    sched_time = datetime.fromisoformat(sched_str + '+00:00')
                if sched_time > now:
                    upcoming_valid.append((sched_time, c))
        except:
            pass

    upcoming_valid.sort(key=lambda x: x[0])

    if upcoming_valid:
        print("\n" + "=" * 70)
        print(f"📅 UPCOMING SCHEDULED TEXT CARDS ({len(upcoming_valid)} pending)")
        print("=" * 70)
        for sched_time, card in upcoming_valid[:10]:
            print(f"\n   ID: {card.get('id')}")
            print(f"   Status: {card.get('status')}")
            print(f"   Scheduled: {sched_time.strftime('%Y-%m-%d %H:%M')} UTC")
            print(f"   Has Image: {'✅' if card.get('image_url') else '❌'}")
            print(f"   FB Post ID: {card.get('facebook_post_id') or 'None'}")

if __name__ == "__main__":
    main()
