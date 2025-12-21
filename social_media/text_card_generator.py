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

    # Template URLs
    TEMPLATE_URL = "https://mqemiteirxwscxtamdtj.supabase.co/storage/v1/object/public/media/brand-assets/text-card-template.png"
    AVATAR_URL = "https://mqemiteirxwscxtamdtj.supabase.co/storage/v1/object/public/media/brand-assets/refiloe-avatar.png"

    # Official Refiloe Brand Colors
    BACKGROUND_WHITE = "#FFFFFF"  # White - primary background
    BACKGROUND_CREAM = "#FFF8E8"  # Cream - alternative warm background
    BACKGROUND_BEIGE = "#F7EED3"  # Warm Beige - accent background
    ACCENT_COLOR = "#AAB396"  # Sage Green - primary accent
    TEXT_COLOR = "#674636"  # Dark Brown - primary text
    TEXT_WHITE = "#FFFFFF"  # White - for dark backgrounds

    # Avatar size
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

        # Fetch and cache template and avatar
        log_info("Fetching base template and avatar from Supabase...")
        self.base_template = self._fetch_image(self.TEMPLATE_URL)
        self.avatar = self._fetch_image(self.AVATAR_URL)

        if self.base_template:
            log_info(f"Base template loaded successfully ({self.base_template.size})")
        else:
            log_warning("Base template failed to load - will use fallback background")

        if self.avatar:
            log_info(f"Avatar loaded successfully ({self.avatar.size})")
        else:
            log_warning("Avatar failed to load - will skip avatar overlay")

        log_info(f"TextCardGenerator initialized. Output directory: {self.output_dir}")

    def _fetch_image(self, url: str) -> Optional[Image.Image]:
        """Fetch image from URL and return PIL Image object.

        Args:
            url: URL of the image to fetch

        Returns:
            PIL.Image or None: Image object if successful, None if failed
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert('RGBA')
        except Exception as e:
            log_error(f"Failed to fetch image from {url}: {e}")
            return None

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

    def _create_unified_layout(self, content_type: str, content: Dict[str, Any]) -> Image.Image:
        """Create text card using pre-designed template.

        Args:
            content_type: Type of content (quote, tip, educational, motivation)
            content: Content dictionary

        Returns:
            PIL.Image: Generated card with template and overlaid content
        """
        # Start with copy of base template (don't modify cached original)
        if self.base_template:
            img = self.base_template.copy()
        else:
            # Fallback: create plain background if template fetch failed
            log_warning("Using fallback background - template not available")
            img = Image.new('RGBA', (self.IMAGE_WIDTH, self.IMAGE_HEIGHT), '#2D1B3D')

        draw = ImageDraw.Draw(img)

        # Frame boundaries (matching template design)
        frame_inset = 70
        content_start_y = frame_inset + 120  # Start position for content

        # Add avatar (centered, near top inside frame)
        if self.avatar:
            avatar_size = self.AVATAR_SIZE
            avatar_resized = self.avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

            # Create circular mask
            mask = Image.new('L', (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

            # Center horizontally, position near top
            avatar_x = (self.IMAGE_WIDTH - avatar_size) // 2
            avatar_y = content_start_y
            img.paste(avatar_resized, (avatar_x, avatar_y), mask)

            current_y = avatar_y + avatar_size + 20
        else:
            current_y = content_start_y

        # Draw name "Refiloe"
        name_font = self._load_font(bold=True, size=self.NAME_FONT_SIZE)
        name_text = "Refiloe"
        bbox = draw.textbbox((0, 0), name_text, font=name_font)
        name_width = bbox[2] - bbox[0]
        name_x = (self.IMAGE_WIDTH - name_width) // 2
        draw.text((name_x, current_y), name_text, font=name_font, fill=(255, 255, 255))
        current_y += 50

        # Draw tagline "Personal assistant | trainer"
        tagline_font = self._load_font(bold=False, size=self.TAGLINE_FONT_SIZE)
        tagline_text = "Personal assistant | trainer"
        bbox = draw.textbbox((0, 0), tagline_text, font=tagline_font)
        tagline_width = bbox[2] - bbox[0]
        tagline_x = (self.IMAGE_WIDTH - tagline_width) // 2
        draw.text((tagline_x, current_y), tagline_text, font=tagline_font, fill=(255, 255, 255))
        current_y += 80

        # Decorative line
        line_width = 200
        line_x = (self.IMAGE_WIDTH - line_width) // 2
        draw.line([(line_x, current_y), (line_x + line_width, current_y)],
                 fill=(255, 255, 255), width=3)
        current_y += 60

        # Draw main content (centered vertically in remaining space)
        max_width = self.IMAGE_WIDTH - (2 * frame_inset) - 140

        # Extract main text based on content type
        if content_type == 'quote':
            main_text = content.get('quote', '')
            attribution = content.get('attribution', '')
        elif content_type == 'tip':
            main_text = content.get('tip', '')
            attribution = content.get('subtitle', '')
        elif content_type == 'educational':
            main_text = content.get('title', '')
            attribution = None
        elif content_type == 'motivation':
            main_text = content.get('statement', '')
            attribution = None
        else:
            main_text = ''
            attribution = None

        # Draw main content text
        content_font = self._load_font(bold=True, size=self.CONTENT_FONT_SIZE)
        wrapped_lines = self._wrap_text(main_text, content_font, max_width)

        line_height = 75
        for line in wrapped_lines:
            bbox = draw.textbbox((0, 0), line, font=content_font)
            text_width = bbox[2] - bbox[0]
            text_x = (self.IMAGE_WIDTH - text_width) // 2
            draw.text((text_x, current_y), line, font=content_font, fill=(255, 255, 255))
            current_y += line_height

        current_y += 40

        # Draw attribution/subtitle if present
        if attribution:
            attr_font = self._load_font(bold=False, size=self.ATTRIBUTION_FONT_SIZE)
            attr_text = f"— {attribution}" if content_type == 'quote' else attribution
            bbox = draw.textbbox((0, 0), attr_text, font=attr_font)
            attr_width = bbox[2] - bbox[0]
            attr_x = (self.IMAGE_WIDTH - attr_width) // 2
            draw.text((attr_x, current_y), attr_text, font=attr_font, fill=(255, 255, 255))
            current_y += 60

        # Handle educational bullet points
        if content_type == 'educational':
            points = content.get('points', [])
            bullet_font = self._load_font(bold=False, size=self.BULLET_FONT_SIZE)
            bullet_padding = frame_inset + 100

            for point in points[:4]:  # Limit to 4 points
                # Draw bullet circle
                bullet_radius = 6
                bullet_x = bullet_padding
                draw.ellipse(
                    [(bullet_x - bullet_radius, current_y + 20 - bullet_radius),
                     (bullet_x + bullet_radius, current_y + 20 + bullet_radius)],
                    fill=(255, 255, 255)
                )

                # Draw bullet text
                text_x = bullet_x + bullet_radius + 15
                wrapped_point = self._wrap_text(point, bullet_font, max_width - 80)
                for point_line in wrapped_point[:2]:  # Max 2 lines per bullet
                    draw.text((text_x, current_y), point_line,
                             font=bullet_font, fill=(255, 255, 255))
                    current_y += 55

                current_y += 15  # Space between bullets

        # Bottom watermark "REFILOE"
        watermark_font = self._load_font(bold=True, size=self.WATERMARK_SIZE)
        watermark_text = "REFILOE"
        bbox = draw.textbbox((0, 0), watermark_text, font=watermark_font)
        watermark_width = bbox[2] - bbox[0]
        watermark_x = (self.IMAGE_WIDTH - watermark_width) // 2
        watermark_y = self.IMAGE_HEIGHT - frame_inset - 50
        draw.text((watermark_x, watermark_y), watermark_text,
                 font=watermark_font, fill=(255, 255, 255))

        return img.convert('RGB')

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
