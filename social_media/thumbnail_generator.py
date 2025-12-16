"""Thumbnail generator for Facebook Reels.

Adds text overlays to HeyGen avatar images while avoiding the face region.
"""

import os
import io
import requests
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Optional, Tuple
from utils.logger import log_info, log_error, log_warning


class ThumbnailGenerator:
    """Generate thumbnails with text overlays for video content."""

    # Text styling - high contrast white with shadow
    TEXT_COLOR = (255, 255, 255)  # White
    SHADOW_COLOR = (0, 0, 0)  # Black
    SHADOW_OFFSET = 4

    # Semi-transparent bar behind text
    BAR_COLOR = (0, 0, 0)  # Black
    BAR_OPACITY = 150  # 0-255, where 150 ≈ 60% opacity
    BAR_PADDING_VERTICAL = 30  # Pixels above/below text
    BAR_PADDING_HORIZONTAL = 40  # Pixels left/right of text

    # Font settings
    DEFAULT_FONT_SIZE = 72
    MIN_FONT_SIZE = 40
    MAX_TEXT_WIDTH_RATIO = 0.85  # Text should fit within 85% of image width

    def __init__(self):
        """Initialize the thumbnail generator."""
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self._font_path = self._find_bold_font()
        log_info("ThumbnailGenerator initialized")

    def _find_bold_font(self) -> Optional[str]:
        """Find a suitable bold sans-serif font on the system."""
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        ]
        for font_path in font_candidates:
            if os.path.exists(font_path):
                log_info(f"Using font: {font_path}")
                return font_path
        log_warning("No bold font found, using default")
        return None

    def _download_image(self, url: str) -> Image.Image:
        """Download image from URL and return as PIL Image."""
        log_info(f"Downloading image from: {url[:80]}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert('RGBA')

    def _detect_face_region(self, image: Image.Image) -> Optional[Tuple[int, int, int, int]]:
        """Detect face in image and return bounding box (x, y, w, h)."""
        cv_image = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50)
        )

        if len(faces) == 0:
            log_warning("No face detected in image")
            return None

        largest_face = max(faces, key=lambda f: f[2] * f[3])
        return tuple(largest_face)

    def _determine_text_position(
        self,
        image_height: int,
        face_region: Optional[Tuple[int, int, int, int]]
    ) -> str:
        """Determine whether to place text at 'top' or 'bottom' based on face location."""
        if face_region is None:
            return "bottom"  # Default to bottom if no face detected

        face_x, face_y, face_w, face_h = face_region
        face_center_y = face_y + (face_h / 2)

        # If face center is in upper half, place text at bottom (and vice versa)
        if face_center_y < image_height * 0.5:
            return "bottom"
        else:
            return "top"

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Get font at specified size."""
        if self._font_path:
            return ImageFont.truetype(self._font_path, size)
        return ImageFont.load_default()

    def _calculate_font_size(
        self,
        text: str,
        max_width: int,
        draw: ImageDraw.Draw
    ) -> Tuple[ImageFont.FreeTypeFont, int, int]:
        """Calculate appropriate font size to fit text within max_width."""
        font_size = self.DEFAULT_FONT_SIZE

        while font_size >= self.MIN_FONT_SIZE:
            font = self._get_font(font_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            if text_width <= max_width:
                return font, text_width, text_height

            font_size -= 4

        # Return minimum size
        font = self._get_font(self.MIN_FONT_SIZE)
        bbox = draw.textbbox((0, 0), text, font=font)
        return font, bbox[2] - bbox[0], bbox[3] - bbox[1]

    def generate_thumbnail(
        self,
        image_url: str,
        title_text: str,
        output_path: Optional[str] = None
    ) -> Dict:
        """Generate a thumbnail with text overlay.

        Args:
            image_url: URL of the source image (HeyGen avatar image)
            title_text: Text to overlay (the reel_title)
            output_path: Optional path to save the thumbnail

        Returns:
            Dict with:
                - success: bool
                - thumbnail_path: str (if output_path provided)
                - thumbnail_bytes: bytes (JPEG image data)
                - width: int
                - height: int
                - text_position: str ('top' or 'bottom')
                - error: str (if failed)
        """
        try:
            log_info(f"Generating thumbnail with text: '{title_text[:50]}...'")

            # Download source image
            image = self._download_image(image_url)
            width, height = image.size
            log_info(f"Source image size: {width}x{height}")

            # Detect face for dynamic text placement
            face_region = self._detect_face_region(image)
            if face_region:
                log_info(f"Face detected at: {face_region}")

            # Determine text position
            position = self._determine_text_position(height, face_region)
            log_info(f"Text will be placed at: {position}")

            # Create drawing context for measurements
            temp_draw = ImageDraw.Draw(image)

            # Calculate font size and text dimensions
            max_text_width = int(width * self.MAX_TEXT_WIDTH_RATIO)
            font, text_width, text_height = self._calculate_font_size(
                title_text, max_text_width, temp_draw
            )

            # Calculate bar and text coordinates
            bar_height = text_height + (self.BAR_PADDING_VERTICAL * 2)
            text_x = (width - text_width) // 2  # Center horizontally

            if position == "top":
                bar_y = 0
                text_y = self.BAR_PADDING_VERTICAL
            else:  # bottom
                bar_y = height - bar_height
                text_y = bar_y + self.BAR_PADDING_VERTICAL

            # Draw semi-transparent bar
            bar_overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
            bar_draw = ImageDraw.Draw(bar_overlay)
            bar_draw.rectangle(
                [0, bar_y, width, bar_y + bar_height],
                fill=(*self.BAR_COLOR, self.BAR_OPACITY)
            )
            image = Image.alpha_composite(image, bar_overlay)

            # Draw text with shadow
            draw = ImageDraw.Draw(image)

            # Shadow
            draw.text(
                (text_x + self.SHADOW_OFFSET, text_y + self.SHADOW_OFFSET),
                title_text, font=font, fill=self.SHADOW_COLOR
            )

            # Main text
            draw.text((text_x, text_y), title_text, font=font, fill=self.TEXT_COLOR)

            # Convert to RGB (remove alpha)
            output_image = image.convert('RGB')

            # Save to bytes
            img_bytes = io.BytesIO()
            output_image.save(img_bytes, format='JPEG', quality=95)
            img_bytes.seek(0)

            result = {
                'success': True,
                'thumbnail_bytes': img_bytes.getvalue(),
                'width': width,
                'height': height,
                'text_position': position
            }

            # Optionally save to file
            if output_path:
                output_image.save(output_path, 'JPEG', quality=95)
                result['thumbnail_path'] = output_path
                log_info(f"Thumbnail saved to: {output_path}")

            log_info("Thumbnail generated successfully")
            return result

        except Exception as e:
            log_error(f"Thumbnail generation failed: {e}")
            import traceback
            log_error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }
