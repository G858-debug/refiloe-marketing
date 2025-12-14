#!/usr/bin/env python3
"""Upload reference image to Leonardo AI.

This script uploads an image to Leonardo AI and returns the image ID
that can be used as LEONARDO_REFILOE_REFERENCE_ID for character consistency.

Usage:
    python upload_reference_image.py <image_file_path>

Example:
    python upload_reference_image.py /path/to/refiloe_reference.jpg
"""

import os
import sys
import requests


LEONARDO_API_BASE = "https://cloud.leonardo.ai/api/rest/v1"


def upload_reference_image(file_path: str) -> str:
    """Upload image to Leonardo AI and return image ID.

    Args:
        file_path: Path to the image file to upload.

    Returns:
        The Leonardo AI image ID.

    Raises:
        ValueError: If file doesn't exist or API key is missing.
        requests.RequestException: If upload fails.
    """
    # Validate file exists
    if not os.path.exists(file_path):
        raise ValueError(f"File not found: {file_path}")

    # Get API key from environment
    api_key = os.getenv("LEONARDO_API_KEY")
    if not api_key:
        raise ValueError(
            "LEONARDO_API_KEY environment variable is required.\n"
            "Get your API key from: https://leonardo.ai/ → Settings → API"
        )

    # Determine file extension
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext in ['.jpg', '.jpeg']:
        extension = 'jpg'
    elif file_ext == '.png':
        extension = 'png'
    else:
        # Default to jpg for other formats
        extension = 'jpg'
        print(f"Warning: Unknown extension '{file_ext}', using 'jpg'")

    print(f"Uploading {file_path} to Leonardo AI...")
    print(f"File extension: {extension}")

    # Prepare multipart upload
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    try:
        with open(file_path, 'rb') as image_file:
            files = {
                'file': (os.path.basename(file_path), image_file, f'image/{extension}')
            }
            data = {
                'extension': extension
            }

            response = requests.post(
                f"{LEONARDO_API_BASE}/init-image",
                headers=headers,
                files=files,
                data=data,
                timeout=60,
            )
            response.raise_for_status()

    except requests.Timeout:
        raise requests.RequestException("Upload timed out. Please try again.")
    except requests.RequestException as e:
        error_msg = f"Upload failed: {e}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                error_msg += f"\nAPI Error: {error_detail}"
            except:
                error_msg += f"\nResponse: {e.response.text}"
        raise requests.RequestException(error_msg)

    # Parse response
    result = response.json()

    # Extract image ID from response
    # Leonardo API returns: {"uploadInitImage": {"id": "..."}}
    upload_data = result.get("uploadInitImage", {})
    image_id = upload_data.get("id")

    if not image_id:
        raise ValueError(f"No image ID in response: {result}")

    return image_id


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python upload_reference_image.py <image_file_path>")
        print("\nExample:")
        print("  python upload_reference_image.py /path/to/refiloe_reference.jpg")
        print("\nMake sure LEONARDO_API_KEY environment variable is set.")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        image_id = upload_reference_image(file_path)

        print("\n" + "="*60)
        print("✓ Upload successful!")
        print("="*60)
        print(f"\nImage ID: {image_id}")
        print("\nTo use this as your reference image, add this to your")
        print("Railway environment variables:")
        print(f"\n  LEONARDO_REFILOE_REFERENCE_ID={image_id}")
        print("\n" + "="*60)

        return 0

    except ValueError as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        return 1
    except requests.RequestException as e:
        print(f"\n✗ Upload failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
