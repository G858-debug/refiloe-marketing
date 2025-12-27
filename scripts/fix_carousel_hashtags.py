#!/usr/bin/env python3
"""
One-time script to add hashtags to existing carousel posts that don't have them.
Specifically targets post 77b5b9a2-1dab-499e-9ce6-07948d062c68.

Run with: python scripts/fix_carousel_hashtags.py
"""

import os
import sys
import json
import random
import urllib.request
import urllib.error
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment from .env file manually
env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")

# Target post ID
TARGET_POST_ID = '77b5b9a2-1dab-499e-9ce6-07948d062c68'


def generate_trainer_hashtags(content_type: str = 'educational') -> list:
    """Generate relevant hashtags for personal trainer content."""

    # Core hashtags (always include 3 of these)
    core_hashtags = [
        '#PersonalTrainer', '#FitnessCoach', '#PTLife', '#FitnessBusiness',
        '#PersonalTraining', '#FitnessIndustry', '#TrainerLife'
    ]

    # Content-type specific hashtags
    type_hashtags = {
        'educational': ['#FitnessTips', '#TrainerTips', '#FitnessEducation', '#LearnFitness'],
        'motivational': ['#FitnessMotivation', '#GymMotivation', '#FitInspiration', '#MondayMotivation'],
        'admin_hacks': ['#BusinessTips', '#ProductivityHacks', '#TimeManagement', '#WorkSmarter'],
        'relatable': ['#TrainerProblems', '#GymLife', '#FitnessHumor', '#PTProblems'],
        'business': ['#FitnessBusiness', '#EntrepreneurLife', '#BusinessGrowth', '#SideHustle']
    }

    # South African hashtags (include 1)
    sa_hashtags = ['#SouthAfrica', '#SAFitness', '#MzansiFitness', '#FitnessSA']

    hashtags = []
    hashtags.extend(random.sample(core_hashtags, 3))
    hashtags.extend(random.sample(type_hashtags.get(content_type, type_hashtags['educational']), 2))
    hashtags.extend(random.sample(sa_hashtags, 1))
    hashtags.append('#Refiloe')  # Brand hashtag

    return hashtags


def supabase_request(url, method='GET', data=None, supabase_key=None):
    """Make a request to Supabase REST API."""
    headers = {
        'apikey': supabase_key,
        'Authorization': f'Bearer {supabase_key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }

    req = urllib.request.Request(url, headers=headers, method=method)

    if data:
        req.data = json.dumps(data).encode('utf-8')

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"HTTP Error {e.code}: {error_body}")
        raise


def main():
    print("=" * 50)
    print("Carousel Hashtags Fix Script")
    print("=" * 50)

    # Initialize Supabase connection
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')

    if not supabase_url or not supabase_key:
        print("ERROR: SUPABASE_URL and SUPABASE_KEY environment variables required")
        sys.exit(1)

    # Clean up URL
    supabase_url = supabase_url.rstrip('/')
    api_url = f"{supabase_url}/rest/v1"

    print(f"Connecting to Supabase: {supabase_url[:40]}...")

    # Get the target post
    print(f"\nFetching post: {TARGET_POST_ID}")
    get_url = f"{api_url}/social_posts?id=eq.{TARGET_POST_ID}&select=*"

    result = supabase_request(get_url, supabase_key=supabase_key)

    if not result:
        print(f"ERROR: Post {TARGET_POST_ID} not found!")
        sys.exit(1)

    post = result[0]
    print(f"Found post: {post.get('title', 'Untitled')}")
    print(f"  Post type: {post.get('post_type')}")
    print(f"  Media type: {post.get('media_type')}")
    print(f"  Current hashtags: {post.get('hashtags')}")

    # Get content_type from metadata
    content_type = 'educational'  # Default
    if post.get('generation_prompt'):
        try:
            metadata = json.loads(post['generation_prompt'])
            content_type = metadata.get('content_type', 'educational')
            print(f"  Content type from metadata: {content_type}")
        except Exception as e:
            print(f"  Could not parse metadata: {e}")

    # Generate hashtags
    hashtags = generate_trainer_hashtags(content_type)
    print(f"\nGenerated {len(hashtags)} hashtags:")
    for tag in hashtags:
        print(f"  {tag}")

    # Update the post
    print(f"\nUpdating post with hashtags...")
    update_url = f"{api_url}/social_posts?id=eq.{TARGET_POST_ID}"
    update_data = {
        'hashtags': hashtags,
        'updated_at': datetime.utcnow().isoformat()
    }

    update_result = supabase_request(update_url, method='PATCH', data=update_data, supabase_key=supabase_key)

    if update_result:
        print(f"SUCCESS! Post {TARGET_POST_ID} updated with {len(hashtags)} hashtags")
        print("\nNew hashtags on post:")
        for tag in hashtags:
            print(f"  {tag}")
    else:
        print("WARNING: Update returned empty response (may still have succeeded)")

    print("\n" + "=" * 50)
    print("Done!")


if __name__ == '__main__':
    main()
