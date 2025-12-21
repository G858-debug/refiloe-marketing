"""Text Card Generator - Creates single-slide text images for social media using PIL"""
import os
import uuid
import random
from typing import Dict, List, Any, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import yaml
import requests
from io import BytesIO

from utils.logger import log_info, log_error, log_warning


class TextCardGenerator:
    """Generates single-slide text images for social media using PIL"""

    # Official Refiloe Brand Colors
    BACKGROUND_WHITE = "#FFFFFF"  # White - primary background
    BACKGROUND_CREAM = "#FFF8E8"  # Cream - alternative warm background
    BACKGROUND_BEIGE = "#F7EED3"  # Warm Beige - accent background
    ACCENT_COLOR = "#AAB396"  # Sage Green - primary accent
    TEXT_COLOR = "#674636"  # Dark Brown - primary text
    TEXT_WHITE = "#FFFFFF"  # White - for dark backgrounds

    # Avatar URL
    AVATAR_URL = "https://mqemiteirxwscxtamdtj.supabase.co/storage/v1/object/public/media/brand-assets/refiloe-avatar.png"
    AVATAR_SIZE = 100

    # Image dimensions (4:5 portrait ratio for mobile optimization)
    IMAGE_WIDTH = 1080
    IMAGE_HEIGHT = 1350
    PADDING = 60

    # Accent bar height
    ACCENT_BAR_HEIGHT = 20

    # Font sizes
    NAME_FONT_SIZE = 40
    TAGLINE_FONT_SIZE = 28
    CONTENT_FONT_SIZE = 64
    ATTRIBUTION_FONT_SIZE = 44
    HEADER_FONT_SIZE = 52
    SUBTITLE_FONT_SIZE = 40
    BULLET_FONT_SIZE = 48
    WATERMARK_SIZE = 32

    def __init__(self, config_path: str = 'social_media/config.yaml'):
        """Initialize with config and setup output directory.

        Args:
            config_path: Path to config.yaml file
        """
        self.config_path = config_path
        self.output_dir = Path("/tmp/text_cards")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        log_info(f"TextCardGenerator initialized. Output directory: {self.output_dir}")

    def generate_text_card(self, content_type: str, content: Dict[str, Any]) -> str:
        """Generate text card image and return file path.

        Args:
            content_type: One of 'quote', 'tip', 'educational', 'motivation'
            content: Dict with type-specific keys:
                - quote: {'quote': str, 'attribution': str}
                - tip: {'header': str, 'tip': str, 'subtitle': str}
                - educational: {'title': str, 'points': List[str]}
                - motivation: {'statement': str}

        Returns:
            str: Path to generated image file
        """
        content_type = content_type.lower()

        log_info(f"Generating {content_type} text card")

        try:
            # Validate content type
            valid_types = ['quote', 'tip', 'educational', 'motivation']
            if content_type not in valid_types:
                log_error(f"Unknown content type: {content_type}")
                raise ValueError(f"Unknown content type: {content_type}. Must be one of: {', '.join(valid_types)}")

            # Create unified layout for all types
            image = self._create_unified_layout(content_type, content)

            # Save image
            filename = f"text_card_{content_type}_{uuid.uuid4().hex[:8]}.png"
            filepath = self.output_dir / filename
            image.save(filepath, 'PNG', quality=95)

            log_info(f"Text card generated: {filepath}")
            return str(filepath)

        except Exception as e:
            log_error(f"Failed to generate text card: {str(e)}")
            raise

    def _draw_gradient_background(self) -> Image.Image:
        """Create dark purple gradient background.

        Returns:
            PIL.Image: Image with purple gradient background (#2D1B3D to #1A0F24)
        """
        # Create base image
        image = Image.new('RGB', (self.IMAGE_WIDTH, self.IMAGE_HEIGHT))
        draw = ImageDraw.Draw(image)

        # Define gradient colors
        top_color = self._hex_to_rgb("#2D1B3D")
        bottom_color = self._hex_to_rgb("#1A0F24")

        # Draw gradient line by line
        for y in range(self.IMAGE_HEIGHT):
            # Calculate interpolation ratio
            ratio = y / self.IMAGE_HEIGHT

            # Interpolate RGB values
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)

            # Draw horizontal line
            draw.line([(0, y), (self.IMAGE_WIDTH, y)], fill=(r, g, b))

        return image

    def _draw_blob_shapes(self, image: Image.Image) -> Image.Image:
        """Add organic blob/curved shapes around edges.

        Args:
            image: Base image to add blobs to

        Returns:
            PIL.Image: Image with decorative blob shapes
        """
        # Create overlay for blobs with transparency
        overlay = Image.new('RGBA', (self.IMAGE_WIDTH, self.IMAGE_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Define blob colors with transparency
        blob_colors = [
            self._hex_to_rgb("#8B6914") + (120,),  # Brown with transparency
            self._hex_to_rgb("#C4A574") + (100,),  # Tan with transparency
            self._hex_to_rgb("#D4B896") + (90,),   # Beige with transparency
        ]

        # Define blob positions and sizes (organic shapes in corners/edges)
        blobs = [
            # Top-left corner
            {'xy': [(-80, -80), (280, 280)], 'color': blob_colors[0]},
            # Top-right corner
            {'xy': [(self.IMAGE_WIDTH - 250, -100), (self.IMAGE_WIDTH + 100, 250)], 'color': blob_colors[1]},
            # Bottom-left corner
            {'xy': [(-100, self.IMAGE_HEIGHT - 300), (300, self.IMAGE_HEIGHT + 100)], 'color': blob_colors[2]},
            # Bottom-right corner
            {'xy': [(self.IMAGE_WIDTH - 320, self.IMAGE_HEIGHT - 280),
                   (self.IMAGE_WIDTH + 80, self.IMAGE_HEIGHT + 80)], 'color': blob_colors[0]},
            # Right side
            {'xy': [(self.IMAGE_WIDTH - 200, self.IMAGE_HEIGHT // 2 - 150),
                   (self.IMAGE_WIDTH + 50, self.IMAGE_HEIGHT // 2 + 150)], 'color': blob_colors[1]},
            # Left side
            {'xy': [(-120, self.IMAGE_HEIGHT // 2 - 100),
                   (180, self.IMAGE_HEIGHT // 2 + 200)], 'color': blob_colors[2]},
        ]

        # Draw blob shapes
        for blob in blobs:
            draw.ellipse(blob['xy'], fill=blob['color'])

        # Composite overlay onto image
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        image = Image.alpha_composite(image, overlay)
        return image.convert('RGB')

    def _draw_frame(self, image: Image.Image) -> Image.Image:
        """Draw white rectangular border/frame.

        Args:
            image: Base image to add frame to

        Returns:
            PIL.Image: Image with white frame
        """
        draw = ImageDraw.Draw(image)

        # Frame parameters
        frame_inset = 70  # Inset from edges
        frame_color = (255, 255, 255)  # White
        frame_width = 3  # Line thickness
        corner_radius = 15  # Slight rounded corners

        # Calculate frame coordinates
        x1 = frame_inset
        y1 = frame_inset
        x2 = self.IMAGE_WIDTH - frame_inset
        y2 = self.IMAGE_HEIGHT - frame_inset

        # Draw rounded rectangle frame
        draw.rounded_rectangle(
            [(x1, y1), (x2, y2)],
            radius=corner_radius,
            outline=frame_color,
            width=frame_width
        )

        return image

    def _draw_content(self, draw: ImageDraw.Draw, content: Dict[str, Any], content_type: str):
        """Draw unified text content layout for all content types.

        Args:
            draw: ImageDraw object
            content: Content dictionary
            content_type: Type of content (quote, tip, educational, motivation)
        """
        # White text color for all content
        text_color = (255, 255, 255)

        # Load fonts
        label_font = self._load_font(bold=True, size=32)
        main_font = self._load_font(bold=True, size=72)
        supporting_font = self._load_font(bold=False, size=48)
        small_font = self._load_font(bold=False, size=40)
        watermark_font = self._load_font(bold=True, size=36)

        # Frame boundaries
        frame_inset = 70
        content_padding = 100  # Extra padding inside frame
        max_width = self.IMAGE_WIDTH - (2 * frame_inset) - (2 * content_padding)

        # Starting Y position (inside frame)
        current_y = frame_inset + 80

        # 1. Content type label at top (uppercase, letter-spaced)
        label_map = {
            'quote': 'Q U O T E',
            'tip': 'P R O   T I P',
            'educational': 'E D U C A T I O N',
            'motivation': 'M O T I V A T I O N'
        }
        label_text = label_map.get(content_type, content_type.upper())

        bbox = draw.textbbox((0, 0), label_text, font=label_font)
        label_width = bbox[2] - bbox[0]
        label_x = (self.IMAGE_WIDTH - label_width) // 2
        draw.text((label_x, current_y), label_text, font=label_font, fill=text_color)

        current_y += 100

        # 2. Main content (large centered text)
        if content_type == 'quote':
            main_text = content.get('quote', '')
            supporting_text = f"— {content.get('attribution', 'Refiloe')}"
        elif content_type == 'tip':
            main_text = content.get('tip', '')
            supporting_text = content.get('subtitle', '')
        elif content_type == 'educational':
            main_text = content.get('title', '')
            supporting_text = None  # Will handle bullet points separately
        elif content_type == 'motivation':
            main_text = content.get('statement', '')
            supporting_text = None
        else:
            main_text = ''
            supporting_text = None

        # Wrap and draw main text
        wrapped_main = self._wrap_text(main_text, main_font, max_width)
        line_height = 85

        for line in wrapped_main:
            bbox = draw.textbbox((0, 0), line, font=main_font)
            text_width = bbox[2] - bbox[0]
            text_x = (self.IMAGE_WIDTH - text_width) // 2
            draw.text((text_x, current_y), line, font=main_font, fill=text_color)
            current_y += line_height

        current_y += 40

        # 3. Decorative horizontal line
        line_width = 200
        line_x = (self.IMAGE_WIDTH - line_width) // 2
        draw.line([(line_x, current_y), (line_x + line_width, current_y)],
                 fill=text_color, width=3)

        current_y += 60

        # 4. Supporting text (attribution, subtitle, or bullet points)
        if content_type == 'educational':
            # Handle bullet points
            points = content.get('points', [])
            for point in points[:4]:  # Limit to 4 points
                # Draw bullet circle
                bullet_x = frame_inset + content_padding
                bullet_radius = 8
                draw.ellipse(
                    [(bullet_x - bullet_radius, current_y + 20 - bullet_radius),
                     (bullet_x + bullet_radius, current_y + 20 + bullet_radius)],
                    fill=text_color
                )

                # Draw bullet text
                bullet_text_x = bullet_x + bullet_radius + 20
                wrapped_point = self._wrap_text(point, small_font, max_width - 50)
                for point_line in wrapped_point[:2]:  # Max 2 lines per bullet
                    draw.text((bullet_text_x, current_y), point_line,
                             font=small_font, fill=text_color)
                    current_y += 50

                current_y += 20  # Space between bullets
        elif supporting_text:
            # Draw attribution or subtitle (centered)
            bbox = draw.textbbox((0, 0), supporting_text, font=supporting_font)
            text_width = bbox[2] - bbox[0]
            text_x = (self.IMAGE_WIDTH - text_width) // 2
            draw.text((text_x, current_y), supporting_text,
                     font=supporting_font, fill=text_color)

        # 5. Bottom watermark "REFILOE"
        watermark_text = "REFILOE"
        bbox = draw.textbbox((0, 0), watermark_text, font=watermark_font)
        watermark_width = bbox[2] - bbox[0]
        watermark_x = (self.IMAGE_WIDTH - watermark_width) // 2
        watermark_y = self.IMAGE_HEIGHT - frame_inset - 60
        draw.text((watermark_x, watermark_y), watermark_text,
                 font=watermark_font, fill=text_color)

    def _create_unified_layout(self, content_type: str, content: Dict[str, Any]) -> Image.Image:
        """Create unified layout for all text card types with new design.

        Args:
            content_type: Type of content (quote, tip, educational, motivation)
            content: Content dictionary

        Returns:
            PIL.Image: Generated card with unified layout
        """
        # 1. Create gradient background
        image = self._draw_gradient_background()

        # 2. Add decorative blob shapes
        image = self._draw_blob_shapes(image)

        # 3. Add white frame
        image = self._draw_frame(image)

        # 4. Draw content
        draw = ImageDraw.Draw(image)
        self._draw_content(draw, content, content_type)

        return image

    def _load_font(self, bold: bool = False, size: int = 48) -> ImageFont.FreeTypeFont:
        """Load font with fallback. Use pattern from carousel_template_generator.py.

        Args:
            bold: Whether to use bold font
            size: Font size in points

        Returns:
            ImageFont.FreeTypeFont: Loaded font
        """
        # Try common font paths (including apt-installed fonts on Railway/Ubuntu)
        font_paths = [
            # DejaVu fonts (commonly available on Linux)
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            # Liberation fonts
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            # Ubuntu fonts
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf" if bold else "/usr/share/fonts/truetype/ubuntu/Ubuntu-Regular.ttf",
            # FreeFonts
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            # Noto fonts (very common)
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            # Alternative paths
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/TTF/DejaVuSans.ttf",
            # macOS
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            # Windows
            "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        ]

        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, size)
                return font
            except (OSError, IOError):
                continue

        # Fallback: Try Pillow's built-in default with size (Pillow 10.1+)
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            # Older Pillow version - load_default doesn't accept size
            log_warning(f"No TrueType fonts available, using default font (text will be small)")
            return ImageFont.load_default()

    def _wrap_text(self, text: str, font: ImageFont, max_width: int) -> List[str]:
        """Wrap text to fit within max_width.

        Args:
            text: Text to wrap
            font: Font to use for measurement
            max_width: Maximum width in pixels

        Returns:
            List[str]: List of wrapped lines
        """
        # Create a temporary draw object for text measurement
        temp_img = Image.new('RGB', (1, 1))
        draw = ImageDraw.Draw(temp_img)

        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]

            if text_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        return lines

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple.

        Args:
            hex_color: Hex color string (e.g., "#F5E6D3")

        Returns:
            Tuple[int, int, int]: RGB values
        """
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
