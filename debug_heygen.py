#!/usr/bin/env python3
"""
Diagnostic script to test different HeyGen API endpoints and find the correct format.
This will help us figure out how to access your avatars.
"""

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('HEYGEN_API_KEY')
if not api_key:
    print("ERROR: HEYGEN_API_KEY not found in environment")
    exit(1)

print(f"Using API Key: {api_key[:10]}..." if len(api_key) > 10 else api_key)
print("-" * 60)

# Test avatar ID from your system
test_avatar_id = "e39d22ad46c34b5599dc939c63ba1d89"

# Different API endpoints to test
endpoints_to_test = [
    {
        "name": "List Avatars (v2)",
        "url": "https://api.heygen.com/v2/avatars",
        "method": "GET",
        "headers": {"X-API-KEY": api_key}
    },
    {
        "name": "List Avatars (v1)",
        "url": "https://api.heygen.com/v1/avatar.list",
        "method": "GET",
        "headers": {"X-API-KEY": api_key}
    },
    {
        "name": "Get Specific Avatar (v2)",
        "url": f"https://api.heygen.com/v2/avatar/{test_avatar_id}",
        "method": "GET",
        "headers": {"X-API-KEY": api_key}
    },
    {
        "name": "Get Specific Avatar (v1)",
        "url": f"https://api.heygen.com/v1/avatar/{test_avatar_id}",
        "method": "GET",
        "headers": {"X-API-KEY": api_key}
    },
    {
        "name": "List Templates",
        "url": "https://api.heygen.com/v1/template.list",
        "method": "GET",
        "headers": {"X-API-KEY": api_key}
    }
]

# Test each endpoint
for endpoint in endpoints_to_test:
    print(f"\nTesting: {endpoint['name']}")
    print(f"URL: {endpoint['url']}")
    
    try:
        response = requests.request(
            method=endpoint['method'],
            url=endpoint['url'],
            headers=endpoint['headers'],
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("SUCCESS! Response structure:")
            
            # Print the structure of the response
            if isinstance(data, dict):
                print(f"  Keys: {list(data.keys())}")
                
                # Look for avatars in different places
                if 'data' in data:
                    if 'avatars' in data['data']:
                        avatars = data['data']['avatars']
                        print(f"  Found {len(avatars)} avatars")
                        if avatars and len(avatars) > 0:
                            print("\n  First avatar structure:")
                            first = avatars[0]
                            for key, value in first.items():
                                if key in ['avatar_id', 'avatar_name', 'preview_url']:
                                    print(f"    {key}: {value}")
                    else:
                        print(f"  data keys: {list(data['data'].keys()) if isinstance(data['data'], dict) else type(data['data'])}")
                
                if 'avatars' in data:
                    avatars = data['avatars']
                    print(f"  Found {len(avatars)} avatars directly")
                    if avatars and len(avatars) > 0:
                        print("\n  First avatar structure:")
                        first = avatars[0]
                        for key, value in first.items():
                            if key in ['avatar_id', 'avatar_name', 'preview_url']:
                                print(f"    {key}: {value}")
                
                # Check if the test avatar exists
                if endpoint['name'].startswith("Get Specific"):
                    print(f"\n  Avatar details: {json.dumps(data, indent=2)[:500]}...")
                    
        else:
            print(f"Failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error: {json.dumps(error_data, indent=2)[:200]}")
            except:
                print(f"Error: {response.text[:200]}")
                
    except Exception as e:
        print(f"Exception: {str(e)}")

print("\n" + "=" * 60)
print("DIAGNOSTICS COMPLETE")
print("\nNext steps:")
print("1. Look for successful endpoints above")
print("2. Check if your avatar IDs appear in the avatar lists")
print("3. Note the correct format for avatar IDs in your account")
