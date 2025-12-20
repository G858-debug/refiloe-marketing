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
    SHADOW_OFFSET = 6

    # Semi-transparent bar behind text
    BAR_COLOR = (0, 0, 0)  # Black
    BAR_OPACITY = 230  # 0-255, where 230 ≈ 90% opacity for strong contrast
    BAR_PADDING_VERTICAL = 70  # Pixels above/below text
    BAR_PADDING_HORIZONTAL = 80  # Pixels left/right of text

    # Font settings - sized for 1080x1920 vertical video thumbnails
    DEFAULT_FONT_SIZE = 160
    MIN_FONT_SIZE = 80
    MAX_TEXT_WIDTH_RATIO = 0.85  # Text should fit within 85% of image width (leaves padding on sides)
    EDGE_PADDING = 50  # Minimum pixels from edge
    BOTTOM_PADDING = 60  # Gap between text and bottom edge
    MAX_TEXT_LINES = 2  # Maximum number of text lines

    def __init__(self):
        """Initialize the thumbnail generator."""
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self._font_path = self._find_bold_font()
        log_info("ThumbnailGenerator initialized")

    def _find_bold_font(self) -> Optional[str]:
        """Find a suitable extra-bold/black sans-serif font on the system."""
        # Prioritize Black/ExtraBold weights for maximum thickness
        font_candidates = [
            # Black/Heavy weights (thickest)
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Black.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-ExtraBold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            # Regular bold as fallback
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
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

        # Fallback: Try Pillow 10.1+ load_default with size parameter
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            # Older Pillow - load_default doesn't accept size
            # Last resort: use load_default (will be tiny)
            log_warning(f"Pillow version doesn't support sized default font. Text will be very small.")
            return ImageFont.load_default()

    def _calculate_font_size(
        self,
        text: str,
        max_width: int,
        draw: ImageDraw.Draw
    ) -> Tuple[ImageFont.FreeTypeFont, list, int, int]:
        """Calculate appropriate font size to fit text, with multi-line support.

        Returns: (font, lines, total_width, total_height)
        """
        font_size = self.DEFAULT_FONT_SIZE
        line_spacing = 1.2  # 20% extra space between lines

        while font_size >= self.MIN_FONT_SIZE:
            font = self._get_font(font_size)
            lines = self._wrap_text(text, font, max_width, draw)

            # Check if lines fit within max allowed
            if len(lines) <= self.MAX_TEXT_LINES:
                # Calculate total dimensions
                max_line_width = 0
                total_height = 0

                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_width = bbox[2] - bbox[0]
                    line_height = bbox[3] - bbox[1]
                    max_line_width = max(max_line_width, line_width)
                    total_height += int(line_height * line_spacing)

                return font, lines, max_line_width, total_height

            font_size -= 4

        # Return minimum size with wrapped text
        font = self._get_font(self.MIN_FONT_SIZE)
        lines = self._wrap_text(text, font, max_width, draw)[:self.MAX_TEXT_LINES]

        max_line_width = 0
        total_height = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            max_line_width = max(max_line_width, bbox[2] - bbox[0])
            total_height += int((bbox[3] - bbox[1]) * line_spacing)

        return font, lines, max_line_width, total_height

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> list:
        """Wrap text to fit within max_width, returning list of lines."""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            test_width = bbox[2] - bbox[0]

            if test_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        return lines

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

            # Convert to all caps for thumbnail impact
            title_text = title_text.upper()

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

            # Calculate font size and text dimensions (with multi-line support)
            max_text_width = int(width * self.MAX_TEXT_WIDTH_RATIO) - (self.EDGE_PADDING * 2)
            font, text_lines, text_width, text_height = self._calculate_font_size(
                title_text, max_text_width, temp_draw
            )

            # Calculate bar and text coordinates
            bar_height = text_height + (self.BAR_PADDING_VERTICAL * 2)

            if position == "top":
                bar_y = 0
                text_y = self.BAR_PADDING_VERTICAL + 20  # Slight offset from top edge
            else:  # bottom
                bar_y = height - bar_height - self.BOTTOM_PADDING  # Move bar up to create bottom gap
                text_y = bar_y + self.BAR_PADDING_VERTICAL  # Text within the bar

            # Draw gradient fade instead of solid bar (more elegant)
            bar_overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))

            # Calculate gradient zone (taller than text bar for smooth fade)
            gradient_height = bar_height + 200 + self.BOTTOM_PADDING  # Extra height for smooth fade including bottom padding

            if position == "bottom":
                gradient_start_y = height - gradient_height
                gradient_end_y = height
                # Draw gradient from transparent (top) to dark (bottom)
                for y in range(gradient_height):
                    # Calculate opacity: starts at 0, increases to BAR_OPACITY
                    progress = y / gradient_height
                    # Use ease-in curve for smoother transition
                    opacity = int(self.BAR_OPACITY * (progress ** 1.5))
                    bar_overlay.paste(
                        (*self.BAR_COLOR, opacity),
                        (0, gradient_start_y + y, width, gradient_start_y + y + 1)
                    )
            else:  # top
                gradient_start_y = 0
                gradient_end_y = gradient_height
                # Draw gradient from dark (top) to transparent (bottom)
                for y in range(gradient_height):
                    progress = y / gradient_height
                    # Reverse: starts opaque, fades to transparent
                    opacity = int(self.BAR_OPACITY * ((1 - progress) ** 1.5))
                    bar_overlay.paste(
                        (*self.BAR_COLOR, opacity),
                        (0, y, width, y + 1)
                    )

            image = Image.alpha_composite(image, bar_overlay)

            # Draw text with shadow (multi-line support)
            draw = ImageDraw.Draw(image)

            # Calculate line height for spacing
            sample_bbox = draw.textbbox((0, 0), "Ag", font=font)
            line_height = int((sample_bbox[3] - sample_bbox[1]) * 1.2)

            current_y = text_y
            for line in text_lines:
                # Calculate x position for this line (center each line)
                line_bbox = draw.textbbox((0, 0), line, font=font)
                line_width = line_bbox[2] - line_bbox[0]
                line_x = (width - line_width) // 2

                # Ensure minimum edge padding
                line_x = max(self.EDGE_PADDING, line_x)

                # Draw text outline/stroke for extra thickness (draw text multiple times offset)
                outline_color = self.SHADOW_COLOR
                stroke_width = 8  # Pixels of outline thickness for very bold look

                for dx in range(-stroke_width, stroke_width + 1):
                    for dy in range(-stroke_width, stroke_width + 1):
                        if dx != 0 or dy != 0:
                            draw.text(
                                (line_x + dx, current_y + dy),
                                line, font=font, fill=outline_color
                            )

                # Shadow (offset further)
                draw.text(
                    (line_x + self.SHADOW_OFFSET + 2, current_y + self.SHADOW_OFFSET + 2),
                    line, font=font, fill=self.SHADOW_COLOR
                )

                # Main text on top
                draw.text((line_x, current_y), line, font=font, fill=self.TEXT_COLOR)

                current_y += line_height

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
