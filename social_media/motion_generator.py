"""Leonardo AI Motion 2.0 video generation for Refiloe marketing content.

This module provides video generation using Leonardo AI's Motion 2.0 API,
converting static images into dynamic 5-second video clips.

Features:
- Image-to-video generation using Motion 2.0
- 720p resolution output with smooth video interpolation
- Token usage tracking for cost management
- Batch animation support for multiple images
"""

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from utils.logger import log_info, log_error, log_warning, log_debug


# Leonardo Motion API endpoint (V1)
LEONARDO_MOTION_API_BASE = "https://cloud.leonardo.ai/api/rest/v1"
MOTION_ENDPOINT = f"{LEONARDO_MOTION_API_BASE}/generations-image-to-video"

# Motion 2.0 settings
MOTION_RESOLUTION = "RESOLUTION_720"  # 720p output
TOKENS_PER_CLIP = 300  # Cost per 5-second clip at 720p


class MotionGenerationError(Exception):
    """Raised when Leonardo AI Motion video generation fails."""


class MotionGenerator:
    """Generate videos using Leonardo AI Motion 2.0 from static images."""

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        """Initialize Leonardo AI Motion generator.

        Args:
            api_key: Leonardo AI API key. Defaults to LEONARDO_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("LEONARDO_API_KEY")
        if not self.api_key:
            raise ValueError("LEONARDO_API_KEY environment variable required")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

        # Polling settings
        self.poll_interval = 5  # seconds
        self.poll_timeout = 300  # seconds (videos take longer than images)

        # Token tracking
        self._tokens_used_this_session = 0
        self._generation_count = 0

        log_info("MotionGenerator initialized with Motion 2.0")

    def animate_image(
        self,
        image_id: str,
        motion_prompt: str,
    ) -> Dict[str, Any]:
        """Animate a Leonardo image using Motion 2.0.

        Args:
            image_id: The Leonardo image ID to animate.
            motion_prompt: Description of the desired motion/animation.

        Returns:
            Dict containing:
                - video_url: URL of the generated video
                - generation_id: Leonardo generation ID
                - motion_prompt: The prompt used
                - tokens_used: Tokens consumed for this generation

        Raises:
            MotionGenerationError: If video generation fails.
        """
        log_info(f"Starting Motion 2.0 animation for image: {image_id}")
        log_debug(f"Motion prompt: {motion_prompt}")

        # Build Motion 2.0 API payload
        # NOTE: Omitting modelParameter to use standard Motion 2.0 (NOT Motion 2.0 Fast)
        payload = {
            "imageType": "GENERATED",
            "imageId": image_id,
            "resolution": MOTION_RESOLUTION,
            "frameInterpolation": True,  # Smooth Video option
            "promptEnhance": True,
            "isPublic": False,
            "prompt": motion_prompt,
        }

        log_debug(f"Motion API payload: {payload}")

        # Start generation
        try:
            response = self.session.post(
                MOTION_ENDPOINT,
                json=payload,
                timeout=30,
            )

            if not response.ok:
                log_error(f"Motion API error status: {response.status_code}")
                log_error(f"Motion API error response: {response.text}")
                response.raise_for_status()

            generation_data = response.json()
            log_debug(f"Motion API response: {generation_data}")

            # Handle error responses
            if isinstance(generation_data, list):
                log_error(f"Motion API returned list response: {generation_data}")
                if generation_data and isinstance(generation_data[0], dict):
                    error_msg = generation_data[0].get("message", "Unknown error")
                    error_code = generation_data[0].get("code", "N/A")
                    raise MotionGenerationError(f"API error [{error_code}]: {error_msg}")
                else:
                    raise MotionGenerationError(f"API returned unexpected response: {generation_data}")

        except requests.RequestException as e:
            log_error(f"Motion API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                log_error(f"Motion error details: {e.response.text}")
            raise MotionGenerationError(f"Failed to start motion generation: {e}")

        # Extract generation ID
        generation_id = generation_data.get("motionGenerationJob", {}).get("generationId")
        if not generation_id:
            # Try alternate response structure
            generation_id = generation_data.get("generationId")

        if not generation_id:
            log_error(f"Missing generation ID in response. Full response: {generation_data}")
            raise MotionGenerationError("No generation ID found in response")

        log_info(f"Motion generation started: {generation_id}")

        # Poll for completion
        video_url = self._poll_for_completion(generation_id)

        # Track token usage
        self._tokens_used_this_session += TOKENS_PER_CLIP
        self._generation_count += 1
        log_info(f"Motion generation complete. Tokens used: {TOKENS_PER_CLIP}. "
                 f"Session total: {self._tokens_used_this_session}")

        return {
            "video_url": video_url,
            "generation_id": generation_id,
            "motion_prompt": motion_prompt,
            "tokens_used": TOKENS_PER_CLIP,
            "resolution": MOTION_RESOLUTION,
        }

    def animate_batch(
        self,
        image_ids: List[str],
        motion_prompts: List[str],
    ) -> List[Dict[str, Any]]:
        """Animate multiple images sequentially.

        Args:
            image_ids: List of Leonardo image IDs to animate.
            motion_prompts: List of motion descriptions (must match image_ids length).

        Returns:
            List of dicts, each containing video generation results.

        Raises:
            ValueError: If image_ids and motion_prompts have different lengths.
            MotionGenerationError: If any generation fails.
        """
        if len(image_ids) != len(motion_prompts):
            raise ValueError(
                f"image_ids ({len(image_ids)}) and motion_prompts ({len(motion_prompts)}) "
                "must have the same length"
            )

        log_info(f"Starting batch animation of {len(image_ids)} images")
        estimated_tokens = self.estimate_tokens(len(image_ids))
        log_info(f"Estimated token cost: {estimated_tokens}")

        results = []
        for i, (image_id, motion_prompt) in enumerate(zip(image_ids, motion_prompts)):
            log_info(f"Processing batch item {i + 1}/{len(image_ids)}: {image_id}")
            try:
                result = self.animate_image(image_id, motion_prompt)
                results.append(result)
            except MotionGenerationError as e:
                log_error(f"Failed to animate image {image_id}: {e}")
                results.append({
                    "error": str(e),
                    "image_id": image_id,
                    "motion_prompt": motion_prompt,
                })

        successful = sum(1 for r in results if "video_url" in r)
        log_info(f"Batch complete: {successful}/{len(image_ids)} successful")

        return results

    def estimate_tokens(self, num_clips: int) -> int:
        """Estimate token cost for generating clips.

        Args:
            num_clips: Number of video clips to generate.

        Returns:
            Estimated token cost (300 tokens per clip at 720p).
        """
        return num_clips * TOKENS_PER_CLIP

    def get_monthly_usage(self) -> Dict[str, Any]:
        """Get cumulative token usage for this session.

        Returns:
            Dict containing:
                - tokens_used: Total tokens used this session
                - generation_count: Number of videos generated
                - cost_per_clip: Token cost per clip
        """
        return {
            "tokens_used": self._tokens_used_this_session,
            "generation_count": self._generation_count,
            "cost_per_clip": TOKENS_PER_CLIP,
        }

    def _poll_for_completion(self, generation_id: str) -> str:
        """Poll Leonardo API until video generation completes.

        Args:
            generation_id: The generation ID to poll.

        Returns:
            URL of the generated video.

        Raises:
            MotionGenerationError: If generation fails or times out.
        """
        start_time = time.time()
        poll_url = f"{LEONARDO_MOTION_API_BASE}/generations/{generation_id}"

        while time.time() - start_time < self.poll_timeout:
            try:
                response = self.session.get(
                    poll_url,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                log_warning(f"Poll request failed: {e}, retrying...")
                time.sleep(self.poll_interval)
                continue

            # V1 API response structure
            generation_data = data.get("generations_by_pk", {})
            status = generation_data.get("status")

            if status == "COMPLETE":
                # Look for video URL in generated_images
                images = generation_data.get("generated_images", [])
                if images:
                    # Motion API returns video URL in the motionMP4URL field
                    video_url = images[0].get("motionMP4URL")
                    if not video_url:
                        # Fallback to regular URL
                        video_url = images[0].get("url")

                    if video_url:
                        log_info(f"Motion generation complete: {video_url}")
                        return video_url

                raise MotionGenerationError("Generation complete but no video URL returned")

            elif status == "FAILED":
                gen_data = data.get("generations_by_pk", {})
                failure_info = {
                    "status": status,
                    "generation_id": generation_id,
                }
                log_error(f"Motion generation failed: {failure_info}")
                raise MotionGenerationError(f"Motion generation FAILED: {failure_info}")

            log_debug(f"Motion generation status: {status}, waiting...")
            time.sleep(self.poll_interval)

        raise MotionGenerationError(f"Motion generation timed out after {self.poll_timeout}s")


# Convenience function for quick animation
def animate_leonardo_image(
    image_id: str,
    motion_prompt: str,
) -> Dict[str, Any]:
    """Animate a Leonardo image with motion.

    Args:
        image_id: The Leonardo image ID to animate.
        motion_prompt: Description of the desired motion/animation.

    Returns:
        Dict with generated video details.
    """
    generator = MotionGenerator()
    return generator.animate_image(image_id, motion_prompt)
