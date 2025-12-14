"""
Supabase Storage utility for uploading files.

This module provides functions to upload files to Supabase Storage buckets
and retrieve public URLs for the uploaded files.
"""

import os
import requests
from typing import Optional, Tuple
from utils.logger import log_info, log_error, log_warning


class SupabaseStorage:
    """Client for uploading files to Supabase Storage."""

    def __init__(self, supabase_url: Optional[str] = None, service_key: Optional[str] = None):
        """Initialize the storage client.

        Args:
            supabase_url: Supabase project URL (defaults to SUPABASE_URL env var)
            service_key: Supabase service key (defaults to SUPABASE_SERVICE_KEY env var)
        """
        self.supabase_url = supabase_url or os.getenv('SUPABASE_URL')
        self.service_key = service_key or os.getenv('SUPABASE_SERVICE_KEY')

        if not self.supabase_url or not self.service_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")

        # Remove trailing slash if present
        self.supabase_url = self.supabase_url.rstrip('/')
        self.storage_url = f"{self.supabase_url}/storage/v1"

        self.headers = {
            'Authorization': f'Bearer {self.service_key}',
            'apikey': self.service_key,
        }

    def upload_file(
        self,
        bucket: str,
        file_path: str,
        destination_path: Optional[str] = None,
        content_type: str = 'image/png'
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Upload a file to Supabase Storage.

        Args:
            bucket: Name of the storage bucket
            file_path: Local path to the file to upload
            destination_path: Path in the bucket (defaults to filename)
            content_type: MIME type of the file

        Returns:
            Tuple of (success, public_url, error_message)
        """
        try:
            # Read file
            if not os.path.exists(file_path):
                return False, None, f"File not found: {file_path}"

            with open(file_path, 'rb') as f:
                file_data = f.read()

            # Use filename if no destination path provided
            if not destination_path:
                destination_path = os.path.basename(file_path)

            # Upload to Supabase Storage
            upload_url = f"{self.storage_url}/object/{bucket}/{destination_path}"

            headers = {
                **self.headers,
                'Content-Type': content_type,
                'x-upsert': 'true',  # Overwrite if exists
            }

            log_info(f"Uploading to Supabase Storage: {bucket}/{destination_path}")

            response = requests.post(
                upload_url,
                headers=headers,
                data=file_data,
                timeout=60
            )

            if response.status_code in [200, 201]:
                # Construct public URL
                public_url = f"{self.supabase_url}/storage/v1/object/public/{bucket}/{destination_path}"
                log_info(f"✅ Upload successful: {public_url}")
                return True, public_url, None
            else:
                error_msg = f"Upload failed: {response.status_code} - {response.text}"
                log_error(error_msg)
                return False, None, error_msg

        except Exception as e:
            error_msg = f"Upload exception: {str(e)}"
            log_error(error_msg)
            return False, None, error_msg

    def upload_bytes(
        self,
        bucket: str,
        file_data: bytes,
        destination_path: str,
        content_type: str = 'image/png'
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Upload bytes directly to Supabase Storage.

        Args:
            bucket: Name of the storage bucket
            file_data: File content as bytes
            destination_path: Path in the bucket
            content_type: MIME type of the file

        Returns:
            Tuple of (success, public_url, error_message)
        """
        try:
            upload_url = f"{self.storage_url}/object/{bucket}/{destination_path}"

            headers = {
                **self.headers,
                'Content-Type': content_type,
                'x-upsert': 'true',
            }

            log_info(f"Uploading bytes to Supabase Storage: {bucket}/{destination_path}")

            response = requests.post(
                upload_url,
                headers=headers,
                data=file_data,
                timeout=60
            )

            if response.status_code in [200, 201]:
                public_url = f"{self.supabase_url}/storage/v1/object/public/{bucket}/{destination_path}"
                log_info(f"✅ Upload successful: {public_url}")
                return True, public_url, None
            else:
                error_msg = f"Upload failed: {response.status_code} - {response.text}"
                log_error(error_msg)
                return False, None, error_msg

        except Exception as e:
            error_msg = f"Upload exception: {str(e)}"
            log_error(error_msg)
            return False, None, error_msg

    def delete_file(self, bucket: str, file_path: str) -> Tuple[bool, Optional[str]]:
        """Delete a file from Supabase Storage.

        Args:
            bucket: Name of the storage bucket
            file_path: Path to the file in the bucket

        Returns:
            Tuple of (success, error_message)
        """
        try:
            delete_url = f"{self.storage_url}/object/{bucket}/{file_path}"

            response = requests.delete(
                delete_url,
                headers=self.headers,
                timeout=30
            )

            if response.status_code in [200, 204]:
                log_info(f"✅ Deleted: {bucket}/{file_path}")
                return True, None
            else:
                error_msg = f"Delete failed: {response.status_code} - {response.text}"
                log_error(error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"Delete exception: {str(e)}"
            log_error(error_msg)
            return False, error_msg


# Singleton instance for convenience
_storage_client: Optional[SupabaseStorage] = None


def get_storage_client() -> Optional[SupabaseStorage]:
    """Get or create the global storage client."""
    global _storage_client

    if _storage_client is None:
        try:
            _storage_client = SupabaseStorage()
        except ValueError as e:
            log_error(f"Failed to initialize storage client: {e}")
            return None

    return _storage_client


def upload_carousel_slide(file_path: str, post_id: str, slide_number: int) -> Tuple[bool, Optional[str], Optional[str]]:
    """Convenience function to upload a carousel slide image.

    Args:
        file_path: Local path to the slide image
        post_id: Post ID for organizing files
        slide_number: Slide number (1-based)

    Returns:
        Tuple of (success, public_url, error_message)
    """
    client = get_storage_client()
    if not client:
        return False, None, "Storage client not available"

    # Create destination path: carousel-images/post_id/slide_01.png
    destination = f"carousel-images/{post_id}/slide_{slide_number:02d}.png"

    return client.upload_file(
        bucket='media',  # We'll use a 'media' bucket
        file_path=file_path,
        destination_path=destination,
        content_type='image/png'
    )
