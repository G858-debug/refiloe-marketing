"""HeyGen Photo Avatar Looks Generator for Refiloe.

This module provides functionality to generate different avatar 'looks' (outfits,
environments, poses) for the Refiloe character using HeyGen's Photo Avatar API.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz
import requests

from utils.logger import log_debug, log_error, log_info, log_warning


HEYGEN_API_BASE_URL = "https://api.heygen.com"


class LookGenerationError(Exception):
    """Raised when HeyGen look generation fails."""


class MotionAdditionError(Exception):
    """Raised when adding motion to a look fails."""


# Define 10 distinct looks for Refiloe avatar
REFILOE_LOOKS: Dict[str, Dict[str, Any]] = {
    "gym_trainer": {
        "name": "Gym Trainer",
        "description": "Athletic wear in a modern gym setting",
        "prompt": (
            "Professional fitness trainer wearing athletic wear (black sports top, "
            "leggings), standing confidently in a modern gym with weight equipment "
            "and mirrors in the background, natural lighting, motivational atmosphere"
        ),
        "environment": "gym",
        "attire": "athletic",
        "mood": "energetic",
    },
    "office_professional": {
        "name": "Office Professional",
        "description": "Business attire in a corporate office",
        "prompt": (
            "Business professional wearing smart business attire (blazer, blouse), "
            "seated at a modern office desk with a laptop, minimalist corporate "
            "background with plants, professional lighting, confident posture"
        ),
        "environment": "office",
        "attire": "formal",
        "mood": "professional",
    },
    "outdoor_wellness": {
        "name": "Outdoor Wellness Coach",
        "description": "Casual activewear in an outdoor park setting",
        "prompt": (
            "Wellness coach in comfortable activewear (tank top, joggers), standing "
            "in a beautiful park with trees and greenery, morning sunlight, peaceful "
            "and approachable expression, nature background"
        ),
        "environment": "outdoor",
        "attire": "casual_athletic",
        "mood": "peaceful",
    },
    "nutrition_expert": {
        "name": "Nutrition Expert",
        "description": "Smart casual in a modern kitchen",
        "prompt": (
            "Nutrition expert wearing smart casual outfit (clean blouse, jeans), "
            "standing in a bright modern kitchen with fresh fruits and vegetables "
            "visible, warm lighting, friendly and knowledgeable expression"
        ),
        "environment": "kitchen",
        "attire": "smart_casual",
        "mood": "friendly",
    },
    "yoga_instructor": {
        "name": "Yoga Instructor",
        "description": "Yoga attire in a serene studio",
        "prompt": (
            "Yoga instructor in comfortable yoga wear (fitted top, leggings), "
            "seated peacefully in a bright yoga studio with wooden floors, soft "
            "natural lighting, plants in background, calm and centered expression"
        ),
        "environment": "yoga_studio",
        "attire": "yoga",
        "mood": "serene",
    },
    "motivational_speaker": {
        "name": "Motivational Speaker",
        "description": "Smart dress on a stage setting",
        "prompt": (
            "Motivational speaker wearing elegant smart dress or suit, standing "
            "confidently on a stage with subtle lighting effects, professional "
            "backdrop, empowering and inspiring expression, presentation ready"
        ),
        "environment": "stage",
        "attire": "elegant",
        "mood": "inspiring",
    },
    "home_workout": {
        "name": "Home Workout Guide",
        "description": "Workout clothes in a home gym space",
        "prompt": (
            "Fitness guide in colorful workout clothes (sports bra, shorts), "
            "energetic pose in a clean home gym setup with yoga mat and dumbbells, "
            "bright natural window light, encouraging and accessible vibe"
        ),
        "environment": "home",
        "attire": "workout",
        "mood": "encouraging",
    },
    "podcast_host": {
        "name": "Podcast Host",
        "description": "Casual smart wear in a podcast studio",
        "prompt": (
            "Podcast host wearing casual smart outfit (nice sweater, minimal jewelry), "
            "seated at a professional podcast setup with microphone, headphones nearby, "
            "warm studio lighting, conversational and engaging expression"
        ),
        "environment": "podcast_studio",
        "attire": "casual_smart",
        "mood": "conversational",
    },
    "retreat_leader": {
        "name": "Wellness Retreat Leader",
        "description": "Flowing clothes in a beach/resort setting",
        "prompt": (
            "Wellness retreat leader wearing flowing comfortable clothes (linen dress "
            "or loose pants and top), standing at a beautiful beach or resort location, "
            "golden hour lighting, ocean or mountains in background, tranquil expression"
        ),
        "environment": "resort",
        "attire": "flowing",
        "mood": "tranquil",
    },
    "studio_portrait": {
        "name": "Studio Portrait",
        "description": "Professional headshot style",
        "prompt": (
            "Professional portrait with neutral background, wearing a clean solid-colored "
            "top, studio lighting highlighting facial features, confident and warm smile, "
            "high-quality headshot suitable for marketing materials"
        ),
        "environment": "studio",
        "attire": "neutral",
        "mood": "confident",
    },
}


class LooksGenerator:
    """Generate and manage avatar looks via HeyGen Photo Avatar API."""

    def __init__(self, supabase_client=None):
        """Initialize the LooksGenerator.

        Args:
            supabase_client: Optional Supabase client for database operations.
        """
        self.supabase_client = supabase_client

        self.api_key = os.getenv("HEYGEN_API_KEY")
        if not self.api_key:
            raise ValueError("HEYGEN_API_KEY environment variable is required")

        self.group_id = os.getenv("HEYGEN_AVATAR_GROUP")
        self.sa_tz = pytz.timezone("Africa/Johannesburg")
        self.max_retries = 5
        self.retry_backoff = 5
        self.poll_interval = 10
        self.poll_timeout = int(os.getenv("HEYGEN_LOOK_POLL_TIMEOUT", "300"))

        self.looks_table = os.getenv("HEYGEN_LOOKS_TABLE", "avatar_looks")

        log_info("LooksGenerator initialized with HeyGen Photo Avatar integration")

    @property
    def _headers(self) -> Dict[str, str]:
        """Return headers for HeyGen API requests."""
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def get_available_looks(self) -> Dict[str, Dict[str, Any]]:
        """Return all available look definitions for Refiloe.

        Returns:
            Dict mapping look_type keys to look configuration dictionaries.
        """
        return REFILOE_LOOKS.copy()

    def get_look_details(self, look_type: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific look type.

        Args:
            look_type: The key identifying the look (e.g., 'gym_trainer').

        Returns:
            Look configuration dictionary or None if not found.
        """
        return REFILOE_LOOKS.get(look_type)

    def generate_avatar_look(
        self,
        group_id: Optional[str] = None,
        look_type: str = "studio_portrait",
        *,
        custom_prompt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a new avatar look using HeyGen's Photo Avatar API.

        This calls HeyGen's /v2/photo_avatar/look/generate endpoint to create
        a new look (outfit/environment/pose) for an existing photo avatar group.

        Args:
            group_id: HeyGen photo avatar group ID. Defaults to env var if not provided.
            look_type: Key from REFILOE_LOOKS defining the look style.
            custom_prompt: Optional custom prompt to override the default look prompt.
            metadata: Optional metadata to include with the generated look.

        Returns:
            Dict containing:
                - look_id: The generated look ID
                - photo_avatar_id: The resulting photo avatar ID
                - status: Generation status
                - look_type: The look type used
                - prompt: The prompt used for generation

        Raises:
            LookGenerationError: If look generation fails.
            ValueError: If look_type is invalid or group_id is not available.
        """
        resolved_group_id = group_id or self.group_id
        if not resolved_group_id:
            raise ValueError(
                "Photo avatar group ID is required. Provide group_id parameter "
                "or set HEYGEN_AVATAR_GROUP environment variable."
            )

        look_config = REFILOE_LOOKS.get(look_type)
        if not look_config and not custom_prompt:
            raise ValueError(
                f"Unknown look_type '{look_type}'. Available types: {list(REFILOE_LOOKS.keys())}"
            )

        generation_prompt = custom_prompt or (look_config.get("prompt") if look_config else "")
        if not generation_prompt:
            raise ValueError("A generation prompt is required")

        log_info(f"Starting avatar look generation for type '{look_type}'")

        payload: Dict[str, Any] = {
            "group_id": resolved_group_id,
            "prompt": generation_prompt,
        }

        if metadata:
            payload["callback_data"] = metadata

        # Enhanced logging for debugging API requests
        log_info("="*70)
        log_info("HeyGen Photo Avatar Look Generation Request")
        log_info("="*70)
        log_info(f"Endpoint: /v2/photo_avatar/look/generate")
        log_info(f"Group ID: {resolved_group_id}")
        log_info(f"Prompt length: {len(generation_prompt)} characters")
        log_info(f"Prompt preview: {generation_prompt[:200]}...")
        log_info(f"Full payload: {json.dumps(payload, indent=2)}")
        log_info("="*70)

        try:
            response = self._post_with_retry(
                "/v2/photo_avatar/look/generate",
                json=payload,
            )

            data = response.get("data", {})
            look_id = data.get("look_id") or data.get("id") or response.get("look_id")

            if not look_id:
                raise LookGenerationError(
                    "HeyGen response did not include a look identifier"
                )

            log_info(f"Look generation initiated (look_id={look_id}, type={look_type})")

            # Poll for completion
            result = self._poll_look_status(look_id)

            if result.get("status") not in ("completed", "done", "ready"):
                raise LookGenerationError(
                    f"Look generation failed with status: {result.get('status')}"
                )

            photo_avatar_id = (
                result.get("photo_avatar_id")
                or result.get("avatar_id")
                or result.get("talking_photo_id")
            )

            generation_result = {
                "look_id": look_id,
                "photo_avatar_id": photo_avatar_id,
                "status": result.get("status"),
                "look_type": look_type,
                "prompt": generation_prompt,
                "group_id": resolved_group_id,
                "preview_url": result.get("preview_url") or result.get("image_url"),
                "created_at": datetime.now(self.sa_tz).isoformat(),
            }

            if look_config:
                generation_result["look_config"] = {
                    "name": look_config.get("name"),
                    "environment": look_config.get("environment"),
                    "attire": look_config.get("attire"),
                    "mood": look_config.get("mood"),
                }

            log_info(
                f"Avatar look generation complete (look_id={look_id}, "
                f"photo_avatar_id={photo_avatar_id})"
            )

            return generation_result

        except requests.RequestException as exc:
            log_error(f"HeyGen look generation request failed: {exc}")
            raise LookGenerationError(f"Failed to generate avatar look: {exc}") from exc

    def add_motion_to_look(
        self,
        photo_avatar_id: str,
        motion_prompt: str,
        *,
        motion_type: str = "natural",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add motion/animation to a photo avatar look.

        This calls HeyGen's /v2/photo_avatar/add_motion endpoint to add
        motion capabilities to a static photo avatar.

        Args:
            photo_avatar_id: The ID of the photo avatar to add motion to.
            motion_prompt: Text describing the desired motion/animation.
            motion_type: Type of motion (natural, energetic, subtle). Default: natural.
            metadata: Optional metadata to include with the motion request.

        Returns:
            Dict containing:
                - motion_id: The motion task ID
                - photo_avatar_id: The photo avatar ID
                - status: Motion addition status
                - motion_prompt: The prompt used

        Raises:
            MotionAdditionError: If adding motion fails.
            ValueError: If photo_avatar_id is not provided.
        """
        if not photo_avatar_id:
            raise ValueError("photo_avatar_id is required")

        if not motion_prompt:
            raise ValueError("motion_prompt is required")

        log_info(f"Adding motion to photo avatar {photo_avatar_id}")

        payload: Dict[str, Any] = {
            "photo_avatar_id": photo_avatar_id,
            "motion_prompt": motion_prompt,
        }

        if motion_type:
            payload["motion_type"] = motion_type

        if metadata:
            payload["callback_data"] = metadata

        try:
            response = self._post_with_retry(
                "/v2/photo_avatar/add_motion",
                json=payload,
            )

            data = response.get("data", {})
            motion_id = (
                data.get("motion_id")
                or data.get("task_id")
                or data.get("id")
                or response.get("motion_id")
            )

            if not motion_id:
                raise MotionAdditionError(
                    "HeyGen response did not include a motion task identifier"
                )

            log_info(f"Motion addition initiated (motion_id={motion_id})")

            # Poll for completion
            result = self._poll_motion_status(motion_id, photo_avatar_id)

            if result.get("status") not in ("completed", "done", "ready"):
                raise MotionAdditionError(
                    f"Motion addition failed with status: {result.get('status')}"
                )

            motion_result = {
                "motion_id": motion_id,
                "photo_avatar_id": photo_avatar_id,
                "status": result.get("status"),
                "motion_prompt": motion_prompt,
                "motion_type": motion_type,
                "preview_url": result.get("preview_url") or result.get("video_url"),
                "created_at": datetime.now(self.sa_tz).isoformat(),
            }

            log_info(
                f"Motion added successfully to photo avatar {photo_avatar_id} "
                f"(motion_id={motion_id})"
            )

            return motion_result

        except requests.RequestException as exc:
            log_error(f"HeyGen add motion request failed: {exc}")
            raise MotionAdditionError(f"Failed to add motion: {exc}") from exc

    def save_look_to_database(
        self,
        look_data: Dict[str, Any],
        *,
        include_motion: bool = False,
    ) -> str:
        """Save generated look information to Supabase avatar_looks table.

        Args:
            look_data: Dictionary containing look information from generation.
            include_motion: Whether motion data is included.

        Returns:
            str: The UUID of the saved record, or empty string if failed.
        """
        if not self.supabase_client:
            log_warning("Supabase client not configured; skipping database save")
            return ""

        try:
            record_id = str(uuid.uuid4())

            db_record = {
                "id": record_id,
                "look_id": look_data.get("look_id"),
                "photo_avatar_id": look_data.get("photo_avatar_id"),
                "group_id": look_data.get("group_id"),
                "look_type": look_data.get("look_type"),
                "prompt": look_data.get("prompt"),
                "status": look_data.get("status"),
                "preview_url": look_data.get("preview_url"),
                "look_config": look_data.get("look_config"),
                "has_motion": include_motion,
                "motion_id": look_data.get("motion_id") if include_motion else None,
                "motion_prompt": look_data.get("motion_prompt") if include_motion else None,
                "motion_type": look_data.get("motion_type") if include_motion else None,
                "created_at": datetime.now(self.sa_tz).isoformat(),
                "updated_at": datetime.now(self.sa_tz).isoformat(),
            }

            # Remove None values
            db_record = {k: v for k, v in db_record.items() if v is not None}

            result = self.supabase_client.table(self.looks_table).insert(db_record).execute()

            if result and hasattr(result, "data") and result.data:
                log_info(f"Saved avatar look to database (id={record_id})")
                return record_id

            log_error("Failed to save avatar look - unexpected result structure")
            return ""

        except Exception as exc:
            log_error(f"Error saving avatar look to database: {exc}")
            return ""

    def get_saved_looks(
        self,
        *,
        look_type: Optional[str] = None,
        has_motion: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve saved looks from the database.

        Args:
            look_type: Optional filter by look type.
            has_motion: Optional filter by motion status.
            limit: Maximum number of records to return.

        Returns:
            List of look records from the database.
        """
        if not self.supabase_client:
            log_warning("Supabase client not configured; cannot retrieve looks")
            return []

        try:
            query = self.supabase_client.table(self.looks_table).select("*")

            if look_type:
                query = query.eq("look_type", look_type)

            if has_motion is not None:
                query = query.eq("has_motion", has_motion)

            result = query.order("created_at", desc=True).limit(limit).execute()

            if result.data:
                log_info(f"Retrieved {len(result.data)} avatar looks from database")
                return result.data

            log_info("No avatar looks found in database")
            return []

        except Exception as exc:
            log_error(f"Error retrieving avatar looks: {exc}")
            return []

    def update_look_with_motion(
        self,
        record_id: str,
        motion_data: Dict[str, Any],
    ) -> bool:
        """Update an existing look record with motion information.

        Args:
            record_id: The database record ID to update.
            motion_data: Motion data from add_motion_to_look.

        Returns:
            bool: True if update successful, False otherwise.
        """
        if not self.supabase_client:
            log_warning("Supabase client not configured; cannot update look")
            return False

        try:
            update_data = {
                "has_motion": True,
                "motion_id": motion_data.get("motion_id"),
                "motion_prompt": motion_data.get("motion_prompt"),
                "motion_type": motion_data.get("motion_type"),
                "motion_preview_url": motion_data.get("preview_url"),
                "updated_at": datetime.now(self.sa_tz).isoformat(),
            }

            result = (
                self.supabase_client.table(self.looks_table)
                .update(update_data)
                .eq("id", record_id)
                .execute()
            )

            if result and result.data:
                log_info(f"Updated look record {record_id} with motion data")
                return True

            log_error(f"Failed to update look record {record_id}")
            return False

        except Exception as exc:
            log_error(f"Error updating look with motion: {exc}")
            return False

    def generate_look_with_motion(
        self,
        group_id: Optional[str] = None,
        look_type: str = "studio_portrait",
        motion_prompt: str = "natural head movement and subtle expressions",
        *,
        custom_prompt: Optional[str] = None,
        motion_type: str = "natural",
        save_to_database: bool = True,
    ) -> Dict[str, Any]:
        """Generate a look and add motion in one operation.

        This is a convenience method that combines generate_avatar_look and
        add_motion_to_look into a single workflow.

        Args:
            group_id: HeyGen photo avatar group ID.
            look_type: Key from REFILOE_LOOKS defining the look style.
            motion_prompt: Text describing the desired motion/animation.
            custom_prompt: Optional custom prompt for look generation.
            motion_type: Type of motion (natural, energetic, subtle).
            save_to_database: Whether to save the result to the database.

        Returns:
            Dict containing combined look and motion data.

        Raises:
            LookGenerationError: If look generation fails.
            MotionAdditionError: If motion addition fails.
        """
        log_info(f"Starting combined look+motion generation for type '{look_type}'")

        # Step 1: Generate the look
        look_result = self.generate_avatar_look(
            group_id=group_id,
            look_type=look_type,
            custom_prompt=custom_prompt,
        )

        photo_avatar_id = look_result.get("photo_avatar_id")
        if not photo_avatar_id:
            raise LookGenerationError(
                "Look generation did not return a photo_avatar_id for motion"
            )

        # Step 2: Add motion
        motion_result = self.add_motion_to_look(
            photo_avatar_id=photo_avatar_id,
            motion_prompt=motion_prompt,
            motion_type=motion_type,
        )

        # Combine results
        combined_result = {
            **look_result,
            "motion_id": motion_result.get("motion_id"),
            "motion_prompt": motion_result.get("motion_prompt"),
            "motion_type": motion_result.get("motion_type"),
            "motion_preview_url": motion_result.get("preview_url"),
            "has_motion": True,
        }

        # Step 3: Save to database if requested
        if save_to_database:
            record_id = self.save_look_to_database(combined_result, include_motion=True)
            combined_result["database_record_id"] = record_id

        log_info(
            f"Combined look+motion generation complete for '{look_type}' "
            f"(photo_avatar_id={photo_avatar_id})"
        )

        return combined_result

    # -------------------------------------------------------------------------
    # HTTP helpers

    def _post_with_retry(
        self,
        endpoint: str,
        *,
        json: Dict[str, Any],
    ) -> Dict[str, Any]:
        """POST request with retry logic.

        Args:
            endpoint: API endpoint path.
            json: JSON payload.

        Returns:
            Response JSON as dictionary.

        Raises:
            requests.RequestException: If all retries fail.
        """
        url = f"{HEYGEN_API_BASE_URL}{endpoint}"

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    url,
                    headers=self._headers,
                    json=json,
                    timeout=60,
                )

                if response.status_code == 429:
                    wait_time = self.retry_backoff * attempt
                    log_warning(
                        f"HeyGen rate limit hit. Retrying in {wait_time}s (attempt {attempt})"
                    )
                    time.sleep(wait_time)
                    continue

                if response.status_code >= 500:
                    wait_time = self.retry_backoff * attempt
                    log_warning(
                        f"HeyGen server error {response.status_code}. Retrying in {wait_time}s"
                    )
                    time.sleep(wait_time)
                    continue

                # Enhanced error logging for non-successful responses
                if not response.ok:
                    log_error(f"HeyGen API Error Response:")
                    log_error(f"Status Code: {response.status_code}")
                    log_error(f"Response Headers: {dict(response.headers)}")
                    try:
                        error_body = response.json()
                        log_error(f"Response Body: {json.dumps(error_body, indent=2)}")
                    except:
                        log_error(f"Response Text: {response.text}")

                response.raise_for_status()
                return response.json()

            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    log_error(
                        f"HeyGen request failed after {self.max_retries} attempts: {exc}"
                    )
                    raise

                wait_time = self.retry_backoff * attempt
                log_warning(f"HeyGen request error ({exc}). Retrying in {wait_time}s")
                time.sleep(wait_time)

        raise LookGenerationError("Failed to communicate with HeyGen API")

    def _get_with_retry(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """GET request with retry logic.

        Args:
            endpoint: API endpoint path.
            params: Query parameters.

        Returns:
            Response JSON as dictionary.

        Raises:
            requests.RequestException: If all retries fail.
        """
        url = f"{HEYGEN_API_BASE_URL}{endpoint}"

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(
                    url,
                    headers=self._headers,
                    params=params,
                    timeout=45,
                )

                if response.status_code == 429:
                    wait_time = self.retry_backoff * attempt
                    log_warning(
                        f"HeyGen rate limit hit. Retrying in {wait_time}s (attempt {attempt})"
                    )
                    time.sleep(wait_time)
                    continue

                if response.status_code >= 500:
                    wait_time = self.retry_backoff * attempt
                    log_warning(
                        f"HeyGen server error {response.status_code}. Retrying in {wait_time}s"
                    )
                    time.sleep(wait_time)
                    continue

                # Enhanced error logging for non-successful responses
                if not response.ok:
                    log_error(f"HeyGen API Error Response:")
                    log_error(f"Status Code: {response.status_code}")
                    log_error(f"Response Headers: {dict(response.headers)}")
                    try:
                        error_body = response.json()
                        log_error(f"Response Body: {json.dumps(error_body, indent=2)}")
                    except:
                        log_error(f"Response Text: {response.text}")

                response.raise_for_status()
                return response.json()

            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    log_error(
                        f"HeyGen GET request failed after {self.max_retries} attempts: {exc}"
                    )
                    raise

                wait_time = self.retry_backoff * attempt
                log_warning(f"HeyGen request error ({exc}). Retrying in {wait_time}s")
                time.sleep(wait_time)

        raise LookGenerationError("Failed to communicate with HeyGen API")

    def _poll_look_status(self, look_id: str) -> Dict[str, Any]:
        """Poll for look generation status until completion or timeout.

        Args:
            look_id: The look generation task ID.

        Returns:
            Final status response data.

        Raises:
            LookGenerationError: If polling times out.
        """
        deadline = time.time() + self.poll_timeout

        while time.time() < deadline:
            for attempt in range(self.max_retries):
                try:
                    response = self._get_with_retry(
                        f"/v2/photo_avatar/look/{look_id}/status",
                    )

                    data = response.get("data", response)
                    status = data.get("status")

                    log_debug(f"Look {look_id} status: {status}")

                    if status in ("completed", "done", "ready", "failed", "error"):
                        data.setdefault("look_id", look_id)
                        return data

                    break

                except Exception as exc:
                    if attempt < self.max_retries - 1:
                        log_warning(
                            f"Look status check failed (attempt {attempt + 1}/{self.max_retries}): {exc}"
                        )
                        time.sleep(self.retry_backoff)
                        continue
                    raise

            time.sleep(self.poll_interval)

        raise LookGenerationError(
            f"Timed out waiting for look {look_id} to complete"
        )

    def _poll_motion_status(
        self,
        motion_id: str,
        photo_avatar_id: str,
    ) -> Dict[str, Any]:
        """Poll for motion addition status until completion or timeout.

        Args:
            motion_id: The motion task ID.
            photo_avatar_id: The photo avatar ID.

        Returns:
            Final status response data.

        Raises:
            MotionAdditionError: If polling times out.
        """
        deadline = time.time() + self.poll_timeout

        while time.time() < deadline:
            for attempt in range(self.max_retries):
                try:
                    response = self._get_with_retry(
                        f"/v2/photo_avatar/motion/{motion_id}/status",
                    )

                    data = response.get("data", response)
                    status = data.get("status")

                    log_debug(f"Motion {motion_id} status: {status}")

                    if status in ("completed", "done", "ready", "failed", "error"):
                        data.setdefault("motion_id", motion_id)
                        data.setdefault("photo_avatar_id", photo_avatar_id)
                        return data

                    break

                except Exception as exc:
                    if attempt < self.max_retries - 1:
                        log_warning(
                            f"Motion status check failed (attempt {attempt + 1}/{self.max_retries}): {exc}"
                        )
                        time.sleep(self.retry_backoff)
                        continue
                    raise

            time.sleep(self.poll_interval)

        raise MotionAdditionError(
            f"Timed out waiting for motion {motion_id} to complete"
        )
