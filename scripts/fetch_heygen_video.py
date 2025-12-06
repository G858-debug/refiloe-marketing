#!/usr/bin/env python3
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from supabase import create_client

load_dotenv()

def fetch_and_save_video(video_id, post_id):
    """Fetch video from HeyGen and update database"""

    # HeyGen API
    api_key = os.getenv('HEYGEN_API_KEY')
    url = f"https://api.heygen.com/v2/video/{video_id}"

    headers = {
        'X-Api-Key': api_key,
        'Content-Type': 'application/json'
    }

    print(f"🎬 Fetching video {video_id}...")
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        video_url = data.get('data', {}).get('video_url')

        if video_url:
            print(f"✅ Video URL: {video_url}")

            # Update database
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
            supabase = create_client(supabase_url, supabase_key)

            from datetime import datetime
            import pytz
            sa_tz = pytz.timezone('Africa/Johannesburg')

            supabase.table('social_posts').update({
                'status': 'pending_media_approval',
                'video_url': video_url,
                'updated_at': datetime.now(sa_tz).isoformat()
            }).eq('id', post_id).execute()

            print(f"✅ Database updated for post {post_id}")
            print(f"📺 Video URL: {video_url}")
            return video_url
        else:
            print("❌ Video URL not found in response")
            print(data)
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)

    return None

if __name__ == "__main__":
    video_id = "3d6c119571954a1a87157db97021327b"
    post_id = "3bf85476-9c19-484b-af7e-80f77117ccb4"

    fetch_and_save_video(video_id, post_id)
