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

    # Text styling
    TEXT_COLOR = (255, 255, 255)  # White
    SHADOW_COLOR = (0, 0, 0)  # Black
    SHADOW_OFFSET = 4

    # Semi-transparent bar
    BAR_COLOR = (0, 0, 0)  # Black
    BAR_OPACITY = 150  # 0-255, where 150 ≈ 60% opacity
    BAR_PADDING = 20  # Pixels above/below text

    # Font settings
    DEFAULT_FONT_SIZE = 64
    MIN_FONT_SIZE = 36
    MAX_TEXT_WIDTH_RATIO = 0.9  # Text should fit within 90% of image width

    def __init__(self):
        """Initialize the thumbnail generator."""
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self._font_path = self._find_font()
        log_info("ThumbnailGenerator initialized")

    def _find_font(self) -> Optional[str]:
        """Find a suitable bold font on the system."""
        # Common font paths to check
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
        ]
        for font_path in font_candidates:
            if os.path.exists(font_path):
                return font_path
        return None  # Will use default

    def _download_image(self, url: str) -> Image.Image:
        """Download image from URL and return as PIL Image."""
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert('RGBA')

    def _detect_face_region(self, image: Image.Image) -> Optional[Tuple[int, int, int, int]]:
        """Detect face in image and return bounding box (x, y, w, h)."""
        # Convert PIL to OpenCV format
        cv_image = cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(50, 50)
        )

        if len(faces) == 0:
            log_warning("No face detected in image")
            return None

        # Return the largest face (most likely the main subject)
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        return tuple(largest_face)

    def _determine_text_position(
        self,
        image_size: Tuple[int, int],
        face_region: Optional[Tuple[int, int, int, int]],
        text_height: int
    ) -> str:
        """Determine whether to place text at 'top' or 'bottom' based on face location."""
        width, height = image_size

        if face_region is None:
            # No face detected - default to bottom (common for thumbnails)
            return "bottom"

        face_x, face_y, face_w, face_h = face_region
        face_center_y = face_y + (face_h / 2)

        # Calculate safe zones
        top_zone_end = height * 0.35  # Top 35% of image
        bottom_zone_start = height * 0.65  # Bottom 35% of image

        # If face is in upper portion, place text at bottom
        if face_center_y < height * 0.5:
            return "bottom"
        else:
            return "top"

    def _calculate_font_size(
        self,
        text: str,
        max_width: int,
        draw: ImageDraw.Draw
    ) -> Tuple[ImageFont.FreeTypeFont, int, int]:
        """Calculate appropriate font size to fit text within max_width."""
        font_size = self.DEFAULT_FONT_SIZE

        while font_size >= self.MIN_FONT_SIZE:
            if self._font_path:
                font = ImageFont.truetype(self._font_path, font_size)
            else:
                font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            if text_width <= max_width:
                return font, text_width, text_height

            font_size -= 4

        # Return minimum size if we couldn't fit
        if self._font_path:
            font = ImageFont.truetype(self._font_path, self.MIN_FONT_SIZE)
        else:
            font = ImageFont.load_default()
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
                - thumbnail_bytes: bytes (PNG image data)
                - error: str (if failed)
        """
        try:
            log_info(f"Generating thumbnail with text: {title_text[:50]}...")

            # Download source image
            image = self._download_image(image_url)
            width, height = image.size
            log_info(f"Source image size: {width}x{height}")

            # Detect face for dynamic text placement
            face_region = self._detect_face_region(image)
            if face_region:
                log_info(f"Face detected at: {face_region}")

            # Create drawing context
            draw = ImageDraw.Draw(image)

            # Calculate font size and text dimensions
            max_text_width = int(width * self.MAX_TEXT_WIDTH_RATIO)
            font, text_width, text_height = self._calculate_font_size(
                title_text, max_text_width, draw
            )

            # Determine text position (top or bottom)
            position = self._determine_text_position(image.size, face_region, text_height)
            log_info(f"Text position: {position}")

            # Calculate bar and text coordinates
            bar_height = text_height + (self.BAR_PADDING * 2)
            text_x = (width - text_width) // 2  # Center horizontally

            if position == "top":
                bar_y = 0
                text_y = self.BAR_PADDING
            else:  # bottom
                bar_y = height - bar_height
                text_y = bar_y + self.BAR_PADDING

            # Draw semi-transparent bar
            bar_overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
            bar_draw = ImageDraw.Draw(bar_overlay)
            bar_draw.rectangle(
                [0, bar_y, width, bar_y + bar_height],
                fill=(*self.BAR_COLOR, self.BAR_OPACITY)
            )
            image = Image.alpha_composite(image, bar_overlay)

            # Redraw on composited image
            draw = ImageDraw.Draw(image)

            # Draw text shadow
            shadow_x = text_x + self.SHADOW_OFFSET
            shadow_y = text_y + self.SHADOW_OFFSET
            draw.text((shadow_x, shadow_y), title_text, font=font, fill=self.SHADOW_COLOR)

            # Draw main text
            draw.text((text_x, text_y), title_text, font=font, fill=self.TEXT_COLOR)

            # Convert to RGB for output (remove alpha)
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
            return {
                'success': False,
                'error': str(e)
            }
