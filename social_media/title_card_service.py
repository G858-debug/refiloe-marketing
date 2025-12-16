"""Title Card Service - orchestrates thumbnail generation and video processing.

Provides a simple interface to add title cards to HeyGen videos.
"""

import os
import tempfile
from typing import Dict, Optional
from utils.logger import log_info, log_error

from social_media.thumbnail_generator import ThumbnailGenerator
from social_media.video_processor import VideoProcessor


class TitleCardService:
    """Service to add title cards to videos."""

    DEFAULT_TITLE_CARD_DURATION = 1.0  # seconds

    def __init__(self):
        """Initialize the title card service."""
        self.thumbnail_generator = ThumbnailGenerator()
        self.video_processor = VideoProcessor()
        self.temp_dir = tempfile.gettempdir()
        log_info("TitleCardService initialized")

    def create_video_with_title_card(
        self,
        source_image_url: str,
        video_url: str,
        title_text: str,
        output_path: Optional[str] = None,
        title_card_duration: float = DEFAULT_TITLE_CARD_DURATION
    ) -> Dict:
        """Create a video with a title card prepended.

        This is the main entry point - takes the HeyGen avatar image,
        adds text overlay, converts to title card, and prepends to video.

        Args:
            source_image_url: URL of HeyGen avatar image used for video
            video_url: URL of the HeyGen video
            title_text: Text to overlay (reel_title)
            output_path: Optional path for output video
            title_card_duration: Duration of title card in seconds

        Returns:
            Dict with:
                - success: bool
                - video_path: str (path to final video with title card)
                - thumbnail_path: str (path to thumbnail image)
                - title_card_duration: float
                - error: str (if failed)
        """
        thumbnail_path = None

        try:
            log_info("="*60)
            log_info("TITLE CARD SERVICE - Starting")
            log_info(f"Title text: '{title_text}'")
            log_info(f"Title card duration: {title_card_duration}s")
            log_info("="*60)

            # Step 1: Generate thumbnail with text overlay
            log_info("Step 1: Generating thumbnail with text overlay...")
            thumbnail_path = os.path.join(
                self.temp_dir, f"thumbnail_{os.getpid()}.jpg"
            )

            thumb_result = self.thumbnail_generator.generate_thumbnail(
                image_url=source_image_url,
                title_text=title_text,
                output_path=thumbnail_path
            )

            if not thumb_result.get('success'):
                raise Exception(f"Thumbnail generation failed: {thumb_result.get('error')}")

            log_info(f"Thumbnail generated: {thumbnail_path}")
            log_info(f"Text position: {thumb_result.get('text_position')}")

            # Step 2: Process video with title card
            log_info("Step 2: Processing video with title card...")

            video_result = self.video_processor.process_video_with_title_card(
                thumbnail_path=thumbnail_path,
                video_url=video_url,
                output_path=output_path,
                title_card_duration=title_card_duration
            )

            if not video_result.get('success'):
                raise Exception(f"Video processing failed: {video_result.get('error')}")

            log_info("="*60)
            log_info("TITLE CARD SERVICE - Complete")
            log_info(f"Output video: {video_result.get('output_path')}")
            log_info("="*60)

            return {
                'success': True,
                'video_path': video_result.get('output_path'),
                'thumbnail_path': thumbnail_path,
                'title_card_duration': title_card_duration,
                'text_position': thumb_result.get('text_position')
            }

        except Exception as e:
            log_error(f"Title card service failed: {e}")
            import traceback
            log_error(traceback.format_exc())

            # Clean up thumbnail if created
            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    os.remove(thumbnail_path)
                except:
                    pass

            return {
                'success': False,
                'error': str(e)
            }


# Convenience function for direct use
def add_title_card_to_video(
    source_image_url: str,
    video_url: str,
    title_text: str,
    output_path: Optional[str] = None,
    title_card_duration: float = 1.0
) -> Dict:
    """Convenience function to add title card to a video.

    Args:
        source_image_url: URL of the source image (HeyGen avatar)
        video_url: URL of the HeyGen video
        title_text: Text for the title card (reel_title)
        output_path: Optional output path
        title_card_duration: Duration of title card in seconds

    Returns:
        Dict with success, video_path, thumbnail_path, or error
    """
    service = TitleCardService()
    return service.create_video_with_title_card(
        source_image_url=source_image_url,
        video_url=video_url,
        title_text=title_text,
        output_path=output_path,
        title_card_duration=title_card_duration
    )
