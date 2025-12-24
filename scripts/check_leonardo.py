#!/usr/bin/env python3
"""
Check Leonardo AI configuration - models and reference images.

USAGE:
------
1. LOCAL (from project root):
   export LEONARDO_API_KEY='your-key-here'
   python scripts/check_leonardo.py

2. RAILWAY SHELL (from web dashboard):
   - Go to Railway dashboard > Your service > Settings > Deploy > Railway Shell
   - Or use: railway run python scripts/check_leonardo.py
   - The LEONARDO_API_KEY should already be set in Railway environment variables

3. DOCKER:
   docker exec -it <container> python scripts/check_leonardo.py
"""

import os
import sys
import requests

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")

if not LEONARDO_API_KEY:
    print("❌ LEONARDO_API_KEY not set!")
    print("Run: export LEONARDO_API_KEY='your-key-here'")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {LEONARDO_API_KEY}",
    "Content-Type": "application/json",
}

def list_models():
    """List available Leonardo AI models."""
    print("=" * 60)
    print("AVAILABLE LEONARDO AI MODELS")
    print("=" * 60)

    url = "https://cloud.leonardo.ai/api/rest/v1/platformModels"

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        models = data.get("custom_models", [])

        # Look for relevant models
        print(f"\nFound {len(models)} models:\n")

        for model in models:
            name = model.get("name", "Unknown")
            model_id = model.get("id", "Unknown")
            description = model.get("description", "")[:80]

            # Highlight likely candidates
            highlight = ""
            name_lower = name.lower()
            if "nano" in name_lower or "banana" in name_lower or "phoenix" in name_lower:
                highlight = " ⭐ RECOMMENDED"

            print(f"  {name}{highlight}")
            print(f"    ID: {model_id}")
            if description:
                print(f"    Desc: {description}...")
            print()

    except Exception as e:
        print(f"❌ Error listing models: {e}")


def check_reference_images():
    """Check if reference images are still valid."""
    print("=" * 60)
    print("CHECKING REFERENCE IMAGES")
    print("=" * 60)

    # These are the IDs from the codebase
    reference_ids = [
        "e206d838-b02e-4ad9-bd23-f32b12c66a26",
        "df794cc1-0492-4bf6-b1b2-fbf64b130623",
        "4cad6505-49cd-4d85-9273-93fd09f7d694",
        "b7e2b346-266d-41b3-a0a9-1f7913f653de",
    ]

    print(f"\nChecking {len(reference_ids)} reference images...\n")

    # List user's uploaded images
    url = "https://cloud.leonardo.ai/api/rest/v1/init-image"

    try:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()
            uploaded_images = data.get("init_images", [])
            uploaded_ids = {img.get("id") for img in uploaded_images}

            print(f"Found {len(uploaded_images)} uploaded images in your account.\n")

            for ref_id in reference_ids:
                if ref_id in uploaded_ids:
                    print(f"  ✅ {ref_id} - VALID")
                else:
                    print(f"  ❌ {ref_id} - NOT FOUND")

            print()

            # Show all uploaded images
            print("All uploaded images in your account:")
            for img in uploaded_images[:20]:  # Limit to 20
                print(f"  - {img.get('id')}: {img.get('url', 'no url')[:60]}...")
        else:
            print(f"❌ Could not fetch uploaded images: {response.status_code}")
            print(f"   Response: {response.text[:200]}")

    except Exception as e:
        print(f"❌ Error checking images: {e}")


def test_simple_generation():
    """Test a simple generation without references."""
    print("=" * 60)
    print("TESTING SIMPLE GENERATION (no references)")
    print("=" * 60)

    # Try Phoenix model (widely supported)
    phoenix_id = "6b645e3a-d64f-4341-a6d8-7a3690fbf042"

    url = "https://cloud.leonardo.ai/api/rest/v2/generations"

    payload = {
        "model": phoenix_id,
        "parameters": {
            "width": 1024,
            "height": 1024,
            "prompt": "A professional portrait photo of a confident woman in business attire, warm lighting, high quality",
            "quantity": 1,
            "prompt_enhance": "OFF",
        },
        "public": False
    }

    print(f"\nTesting with Phoenix model: {phoenix_id}")
    print(f"Prompt: {payload['parameters']['prompt'][:50]}...")

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"\nResponse status: {response.status_code}")
        print(f"Response: {response.json()}")

        if response.status_code == 200:
            print("\n✅ Generation started successfully!")
        else:
            print("\n❌ Generation failed")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("\n🔍 LEONARDO AI CONFIGURATION CHECK\n")

    list_models()
    print("\n")
    check_reference_images()
    print("\n")

    # Ask before testing generation (costs credits)
    answer = input("Test a simple generation? (costs ~10 credits) [y/N]: ")
    if answer.lower() == 'y':
        test_simple_generation()

    print("\n✅ Check complete!\n")
