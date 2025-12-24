"""Leonardo Reference Image Manager

Handles reference images for character consistency:
- Fetches active reference from database
- Uploads to Leonardo if needed
- Caches Leonardo IDs for reuse
- Auto-re-uploads if Leonardo ID becomes invalid
"""

import os
import requests
import tempfile
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from utils.logger import log_info, log_error, log_warning


class LeonardoReferenceManager:
    """Manages reference images for Leonardo AI generation."""

    LEONARDO_API_BASE = "https://cloud.leonardo.ai/api/rest/v1"

    def __init__(self, supabase_client, api_key: Optional[str] = None):
        """Initialize the reference manager.

        Args:
            supabase_client: Supabase client instance
            api_key: Leonardo API key (defaults to env var)
        """
        self.supabase = supabase_client
        self.api_key = api_key or os.getenv("LEONARDO_API_KEY")

        if not self.api_key:
            log_warning("LEONARDO_API_KEY not set - reference uploads will fail")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def get_active_reference(self) -> Optional[Dict[str, Any]]:
        """Get the active reference image from database.

        Returns:
            Reference image record or None if not found
        """
        try:
            result = self.supabase.table('leonardo_reference_images').select('*').eq(
                'is_active', True
            ).limit(1).execute()

            if result.data and len(result.data) > 0:
                return result.data[0]

            log_warning("No active reference image found in database")
            return None

        except Exception as e:
            log_error(f"Error fetching reference image: {e}")
            return None

    def get_leonardo_id(self, force_refresh: bool = False) -> Optional[str]:
        """Get a valid Leonardo image ID for the reference image.

        If the cached ID is missing or force_refresh is True, uploads to Leonardo.

        Args:
            force_refresh: If True, re-upload even if ID exists

        Returns:
            Leonardo image ID or None if unavailable
        """
        reference = self.get_active_reference()

        if not reference:
            log_warning("No reference image configured")
            return None

        leonardo_id = reference.get('leonardo_image_id')

        # Use cached ID if available and not forcing refresh
        if leonardo_id and not force_refresh:
            log_info(f"Using cached Leonardo ID: {leonardo_id}")

            # Update last_used timestamp
            try:
                self.supabase.table('leonardo_reference_images').update({
                    'last_used': datetime.now(timezone.utc).isoformat()
                }).eq('id', reference['id']).execute()
            except:
                pass  # Non-critical

            return leonardo_id

        # Need to upload to Leonardo
        log_info("Uploading reference image to Leonardo...")

        supabase_url = reference.get('supabase_storage_url')
        if not supabase_url:
            log_error("No Supabase storage URL for reference image")
            return None

        # Upload and get new Leonardo ID
        new_leonardo_id = self._upload_to_leonardo(supabase_url)

        if new_leonardo_id:
            # Cache the new ID
            self._update_cached_id(reference['id'], new_leonardo_id)
            return new_leonardo_id

        return None

    def invalidate_cached_id(self) -> None:
        """Mark the cached Leonardo ID as invalid.

        Called when generation fails due to invalid reference.
        """
        reference = self.get_active_reference()

        if reference:
            log_info(f"Invalidating cached Leonardo ID for reference: {reference['name']}")

            try:
                self.supabase.table('leonardo_reference_images').update({
                    'leonardo_image_id': None,
                    'leonardo_upload_status': 'invalid',
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }).eq('id', reference['id']).execute()
            except Exception as e:
                log_error(f"Error invalidating cached ID: {e}")

    def _upload_to_leonardo(self, image_url: str) -> Optional[str]:
        """Upload an image to Leonardo from URL.

        Args:
            image_url: URL of the image to upload

        Returns:
            Leonardo image ID or None if failed
        """
        try:
            # Step 1: Get presigned upload URL from Leonardo
            init_response = self.session.post(
                f"{self.LEONARDO_API_BASE}/init-image",
                json={"extension": "jpg"},
                timeout=30
            )
            init_response.raise_for_status()
            init_data = init_response.json()

            log_info(f"Leonardo init-image response: {init_data}")

            # Handle nested response structure
            upload_info = init_data.get("uploadInitImage", init_data)

            upload_url = upload_info.get("url")
            image_id = upload_info.get("id")
            fields = upload_info.get("fields", {})

            # Handle case where fields is a JSON string
            if isinstance(fields, str):
                import json
                try:
                    fields = json.loads(fields)
                except json.JSONDecodeError:
                    log_error(f"Could not parse fields as JSON: {fields}")
                    fields = {}

            if not upload_url or not image_id:
                log_error(f"Failed to get upload URL from Leonardo: {init_data}")
                return None

            log_info(f"Got Leonardo upload URL, image ID will be: {image_id}")
            log_info(f"Fields type: {type(fields)}, value: {fields}")

            # Step 2: Download image from Supabase
            log_info(f"Downloading image from: {image_url}")
            img_response = requests.get(image_url, timeout=60)
            img_response.raise_for_status()
            image_data = img_response.content

            log_info(f"Downloaded {len(image_data)} bytes")

            # Step 3: Upload to Leonardo's presigned URL
            log_info("Uploading to Leonardo...")

            # Prepare multipart form data - fields should be a dict
            if isinstance(fields, dict) and fields:
                upload_data = {**fields}
                files = {'file': ('image.jpg', image_data, 'image/jpeg')}

                upload_response = requests.post(
                    upload_url,
                    data=upload_data,
                    files=files,
                    timeout=120
                )
            else:
                # If no fields, try direct PUT upload
                log_info("No fields provided, trying direct PUT upload...")
                upload_response = requests.put(
                    upload_url,
                    data=image_data,
                    headers={'Content-Type': 'image/jpeg'},
                    timeout=120
                )

            log_info(f"Upload response status: {upload_response.status_code}")

            if upload_response.status_code in [200, 201, 204]:
                log_info(f"✅ Successfully uploaded to Leonardo: {image_id}")
                return image_id
            else:
                log_error(f"Leonardo upload failed: {upload_response.status_code} - {upload_response.text[:500]}")
                return None

        except Exception as e:
            log_error(f"Error uploading to Leonardo: {e}")
            import traceback
            log_error(traceback.format_exc())
            return None

    def _update_cached_id(self, record_id: str, leonardo_id: str) -> None:
        """Update the cached Leonardo ID in database.

        Args:
            record_id: Database record ID
            leonardo_id: New Leonardo image ID
        """
        try:
            self.supabase.table('leonardo_reference_images').update({
                'leonardo_image_id': leonardo_id,
                'leonardo_upload_status': 'active',
                'last_leonardo_upload': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', record_id).execute()

            log_info(f"Cached Leonardo ID updated: {leonardo_id}")

        except Exception as e:
            log_error(f"Error updating cached ID: {e}")
