"""
List Leonardo AI Elements to find the Refiloe 2.0 Element ID.

Usage:
    python scripts/leonardo_list_elements.py

Requires:
    - LEONARDO_API_KEY environment variable
"""

import os
import sys
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


LEONARDO_API_BASE = "https://cloud.leonardo.ai/api/rest/v1"


def get_user_info(api_key: str) -> dict:
    """Get current user info including user ID."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    response = requests.get(f"{LEONARDO_API_BASE}/me", headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def list_elements(api_key: str) -> list:
    """List all user's trained Elements/LoRAs."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    # Try the elements/lora endpoint
    response = requests.get(
        f"{LEONARDO_API_BASE}/elements",
        headers=headers,
        timeout=30,
    )

    if response.status_code == 200:
        return response.json()

    print(f"Elements endpoint returned: {response.status_code}")
    print(f"Response: {response.text}")

    # Try alternative endpoint - user's custom models/loras
    response2 = requests.get(
        f"{LEONARDO_API_BASE}/models",
        headers=headers,
        timeout=30,
    )

    if response2.status_code == 200:
        return response2.json()

    return {}


def list_user_datasets(api_key: str) -> list:
    """List user's datasets which may contain element info."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    response = requests.get(
        f"{LEONARDO_API_BASE}/datasets",
        headers=headers,
        timeout=30,
    )

    if response.status_code == 200:
        return response.json()

    return {}


def get_user_elements(api_key: str, user_id: str) -> list:
    """Get elements for a specific user."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    # Try user-specific elements endpoint
    response = requests.get(
        f"{LEONARDO_API_BASE}/elements/user/{user_id}",
        headers=headers,
        timeout=30,
    )

    if response.status_code == 200:
        return response.json()

    return {}


def main():
    api_key = os.getenv("LEONARDO_API_KEY")
    if not api_key:
        print("❌ Error: LEONARDO_API_KEY environment variable not set")
        print("\nSet it with:")
        print("  export LEONARDO_API_KEY=your_key_here")
        sys.exit(1)

    print("=" * 60)
    print("LEONARDO AI - ELEMENT ID FINDER")
    print("=" * 60)

    # Get user info
    print("\n📋 Getting user info...")
    try:
        user_data = get_user_info(api_key)
        user_info = user_data.get("user_details", [{}])[0]
        user_id = user_info.get("user", {}).get("id")
        username = user_info.get("user", {}).get("username", "Unknown")
        print(f"   User: {username}")
        print(f"   User ID: {user_id}")
    except Exception as e:
        print(f"❌ Failed to get user info: {e}")
        user_id = None

    # List elements
    print("\n🎨 Fetching Elements...")
    print("-" * 60)

    try:
        elements_data = list_elements(api_key)
        print(f"   Raw response: {elements_data}")

        # Handle different response structures
        elements = []
        if isinstance(elements_data, dict):
            elements = elements_data.get("elements", []) or elements_data.get("loras", []) or elements_data.get("custom_models", [])
        elif isinstance(elements_data, list):
            elements = elements_data

        if elements:
            print(f"\n   Found {len(elements)} elements:\n")
            for elem in elements:
                elem_id = elem.get("id") or elem.get("akUUID") or elem.get("uuid") or "N/A"
                elem_name = elem.get("name") or elem.get("title") or "Unnamed"
                elem_status = elem.get("status", "N/A")

                print(f"   📦 Name: {elem_name}")
                print(f"      ID (akUUID): {elem_id}")
                print(f"      Status: {elem_status}")
                print()

                # Check if this is Refiloe
                if "refiloe" in elem_name.lower():
                    print("   ⭐ THIS LOOKS LIKE YOUR REFILOE ELEMENT!")
                    print(f"   👉 Add to Railway: LEONARDO_REFILOE_ELEMENT_ID={elem_id}")
                    print()
        else:
            print("   No elements found in main endpoint")
    except Exception as e:
        print(f"   ❌ Failed to list elements: {e}")

    # Try user-specific elements
    if user_id:
        print("\n🔍 Checking user-specific elements...")
        try:
            user_elements = get_user_elements(api_key, user_id)
            print(f"   Response: {user_elements}")
        except Exception as e:
            print(f"   ❌ Failed: {e}")

    # List datasets (sometimes elements are linked to datasets)
    print("\n📁 Checking datasets...")
    try:
        datasets = list_user_datasets(api_key)
        ds_list = datasets.get("datasets", [])

        if ds_list:
            print(f"   Found {len(ds_list)} datasets:")
            for ds in ds_list:
                ds_id = ds.get("id", "N/A")
                ds_name = ds.get("name", "Unnamed")
                ds_status = ds.get("status", "N/A")

                print(f"\n   📁 Name: {ds_name}")
                print(f"      ID: {ds_id}")
                print(f"      Status: {ds_status}")

                # Check for associated model/element
                if ds.get("modelId"):
                    print(f"      Model ID: {ds.get('modelId')}")

                if "refiloe" in ds_name.lower():
                    print("   ⭐ THIS MAY BE RELATED TO YOUR REFILOE ELEMENT!")
        else:
            print("   No datasets found")
    except Exception as e:
        print(f"   ❌ Failed to list datasets: {e}")

    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("""
1. Find the Element ID for 'Refiloe 2.0' above
2. Add to Railway environment variables:
   LEONARDO_REFILOE_ELEMENT_ID=<the-element-id>
3. Deploy and test image generation

If you don't see 'Refiloe 2.0' listed, try:
- Check Leonardo AI dashboard under 'Your Elements'
- The ID might be in the browser URL when viewing the element
- Look for 'akUUID' or 'id' field in the element details
""")


if __name__ == "__main__":
    main()
