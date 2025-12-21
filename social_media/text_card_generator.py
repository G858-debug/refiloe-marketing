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
    AVATAR_SIZE = 80

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

        # Fetch and cache avatar
        self.avatar = self._fetch_avatar()

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

    def _fetch_avatar(self) -> Optional[Image.Image]:
        """Fetch avatar from URL and return as PIL Image.

        Returns:
            PIL.Image or None: Avatar image or None if fetch fails
        """
        try:
            log_info(f"Fetching avatar from {self.AVATAR_URL}")
            response = requests.get(self.AVATAR_URL, timeout=10)
            response.raise_for_status()

            avatar = Image.open(BytesIO(response.content))
            log_info("Avatar fetched successfully")
            return avatar
        except Exception as e:
            log_warning(f"Failed to fetch avatar: {str(e)}. Cards will be generated without avatar.")
            return None

    def _create_circular_avatar(self, size: int = None) -> Optional[Image.Image]:
        """Create circular avatar with sage green border.

        Args:
            size: Avatar size (defaults to AVATAR_SIZE)

        Returns:
            PIL.Image or None: Circular avatar with border or None if avatar not available
        """
        if self.avatar is None:
            return None

        size = size or self.AVATAR_SIZE

        try:
            # Resize avatar to desired size
            avatar = self.avatar.copy()
            avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)

            # Create circular mask
            mask = Image.new('L', (size, size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, size, size), fill=255)

            # Create output image with transparency
            output = Image.new('RGBA', (size, size), (0, 0, 0, 0))

            # Convert avatar to RGBA if needed
            if avatar.mode != 'RGBA':
                avatar = avatar.convert('RGBA')

            # Composite avatar with mask
            output.paste(avatar, (0, 0), mask)

            # Add sage green border (draw a ring)
            border_draw = ImageDraw.Draw(output)
            border_color = self._hex_to_rgb(self.ACCENT_COLOR) + (255,)  # Add alpha
            border_width = 3
            border_draw.ellipse(
                [(0, 0), (size - 1, size - 1)],
                outline=border_color,
                width=border_width
            )

            return output
        except Exception as e:
            log_warning(f"Failed to create circular avatar: {str(e)}")
            return None

    def _add_geometric_pattern(self, image: Image.Image) -> Image.Image:
        """Add subtle geometric pattern overlay to background.

        Args:
            image: Base image to add pattern to

        Returns:
            PIL.Image: Image with pattern overlay
        """
        # Create a semi-transparent overlay
        overlay = Image.new('RGBA', (self.IMAGE_WIDTH, self.IMAGE_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Pattern color: warm beige with low opacity
        pattern_color = self._hex_to_rgb(self.BACKGROUND_BEIGE) + (25,)  # Very subtle opacity

        # Draw soft circles in a subtle pattern
        circle_size = 80
        spacing = 200

        for y in range(-circle_size, self.IMAGE_HEIGHT + circle_size, spacing):
            for x in range(-circle_size, self.IMAGE_WIDTH + circle_size, spacing):
                # Offset every other row
                offset_x = spacing // 2 if (y // spacing) % 2 == 1 else 0
                draw.ellipse(
                    [(x + offset_x, y), (x + offset_x + circle_size, y + circle_size)],
                    fill=pattern_color
                )

        # Composite overlay onto image
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        image = Image.alpha_composite(image, overlay)
        return image.convert('RGB')

    def _create_unified_layout(self, content_type: str, content: Dict[str, Any]) -> Image.Image:
        """Create unified layout for all text card types.

        Args:
            content_type: Type of content (quote, tip, educational, motivation)
            content: Content dictionary

        Returns:
            PIL.Image: Generated card with unified layout
        """
        # Create base image with cream background
        image = Image.new('RGB', (self.IMAGE_WIDTH, self.IMAGE_HEIGHT), self._hex_to_rgb(self.BACKGROUND_CREAM))

        # Add geometric pattern
        image = self._add_geometric_pattern(image)

        draw = ImageDraw.Draw(image)

        text_color = self._hex_to_rgb(self.TEXT_COLOR)
        accent_color = self._hex_to_rgb(self.ACCENT_COLOR)

        # Load fonts
        name_font = self._load_font(bold=True, size=self.NAME_FONT_SIZE)
        tagline_font = self._load_font(bold=False, size=self.TAGLINE_FONT_SIZE)
        content_font = self._load_font(bold=False, size=self.CONTENT_FONT_SIZE)
        attribution_font = self._load_font(bold=False, size=self.ATTRIBUTION_FONT_SIZE)
        header_font = self._load_font(bold=True, size=self.HEADER_FONT_SIZE)
        subtitle_font = self._load_font(bold=False, size=self.SUBTITLE_FONT_SIZE)
        bullet_font = self._load_font(bold=False, size=self.BULLET_FONT_SIZE)

        # Add avatar and brand header
        current_y = self.PADDING

        # Avatar (top left)
        avatar_x = self.PADDING
        avatar_y = current_y

        circular_avatar = self._create_circular_avatar()
        if circular_avatar:
            image.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)

        # Brand name and tagline (next to avatar)
        name_x = avatar_x + self.AVATAR_SIZE + 20
        name_y = avatar_y + 10

        draw.text((name_x, name_y), "Refiloe", font=name_font, fill=text_color)

        tagline_y = name_y + self.NAME_FONT_SIZE + 5
        tagline_color = tuple(min(255, c + 40) for c in text_color)  # Lighter shade
        draw.text((name_x, tagline_y), "AI Fitness Coach", font=tagline_font, fill=tagline_color)

        # Content area starts below header
        content_start_y = avatar_y + self.AVATAR_SIZE + 80

        # Render content based on type
        if content_type == 'quote':
            self._render_quote_content(
                draw, content.get('quote', ''), content.get('attribution', ''),
                content_font, attribution_font, text_color, accent_color, content_start_y
            )
        elif content_type == 'tip':
            self._render_tip_content(
                draw, content.get('header', ''), content.get('tip', ''), content.get('subtitle'),
                header_font, content_font, subtitle_font, text_color, accent_color, content_start_y
            )
        elif content_type == 'educational':
            self._render_educational_content(
                draw, content.get('title', ''), content.get('points', []),
                header_font, bullet_font, text_color, accent_color, content_start_y
            )
        elif content_type == 'motivation':
            self._render_motivation_content(
                draw, content.get('statement', ''),
                content_font, text_color, accent_color, content_start_y
            )

        # Add watermark
        image = self._add_watermark(image)

        return image

    def _render_quote_content(self, draw: ImageDraw.Draw, quote: str, attribution: str,
                              content_font: ImageFont, attribution_font: ImageFont,
                              text_color: Tuple[int, int, int], accent_color: Tuple[int, int, int],
                              start_y: int):
        """Render quote content with decorative elements."""
        # Decorative quote marks in sage green
        quote_mark_font = self._load_font(bold=True, size=120)
        quote_mark = '"'
        bbox = draw.textbbox((0, 0), quote_mark, font=quote_mark_font)
        mark_width = bbox[2] - bbox[0]
        mark_x = (self.IMAGE_WIDTH - mark_width) // 2
        draw.text((mark_x, start_y), quote_mark, font=quote_mark_font, fill=accent_color)

        # Quote text (centered, wrapped)
        max_width = self.IMAGE_WIDTH - (2 * self.PADDING) - 40
        wrapped_quote = self._wrap_text(quote, content_font, max_width)

        line_height = self.CONTENT_FONT_SIZE + 20
        quote_y = start_y + 150

        for line in wrapped_quote:
            bbox = draw.textbbox((0, 0), line, font=content_font)
            text_width = bbox[2] - bbox[0]
            x = (self.IMAGE_WIDTH - text_width) // 2
            draw.text((x, quote_y), line, font=content_font, fill=text_color)
            quote_y += line_height

        # Attribution (— Refiloe)
        attribution_text = f"— {attribution if attribution else 'Refiloe'}"
        bbox = draw.textbbox((0, 0), attribution_text, font=attribution_font)
        attr_width = bbox[2] - bbox[0]
        attr_x = (self.IMAGE_WIDTH - attr_width) // 2
        attr_y = quote_y + 40
        draw.text((attr_x, attr_y), attribution_text, font=attribution_font, fill=text_color)

        # Decorative accent line
        line_width = 200
        line_x = (self.IMAGE_WIDTH - line_width) // 2
        line_y = attr_y + 60
        draw.line([(line_x, line_y), (line_x + line_width, line_y)], fill=accent_color, width=4)

    def _render_tip_content(self, draw: ImageDraw.Draw, header: str, tip: str, subtitle: Optional[str],
                            header_font: ImageFont, content_font: ImageFont, subtitle_font: ImageFont,
                            text_color: Tuple[int, int, int], accent_color: Tuple[int, int, int],
                            start_y: int):
        """Render tip content with header badge."""
        # Header badge (sage green background)
        badge_padding = 20
        bbox = draw.textbbox((0, 0), header, font=header_font)
        badge_width = bbox[2] - bbox[0] + (badge_padding * 2)
        badge_height = self.HEADER_FONT_SIZE + 30
        badge_x = (self.IMAGE_WIDTH - badge_width) // 2
        badge_y = start_y

        draw.rounded_rectangle(
            [(badge_x, badge_y), (badge_x + badge_width, badge_y + badge_height)],
            radius=15,
            fill=accent_color
        )

        # Header text in white
        header_x = badge_x + badge_padding
        header_y = badge_y + 15
        draw.text((header_x, header_y), header, font=header_font, fill=self._hex_to_rgb(self.TEXT_WHITE))

        # Tip text (centered)
        max_width = self.IMAGE_WIDTH - (2 * self.PADDING) - 40
        wrapped_tip = self._wrap_text(tip, content_font, max_width)

        line_height = self.CONTENT_FONT_SIZE + 20
        tip_y = badge_y + badge_height + 60

        for line in wrapped_tip:
            bbox = draw.textbbox((0, 0), line, font=content_font)
            text_width = bbox[2] - bbox[0]
            x = (self.IMAGE_WIDTH - text_width) // 2
            draw.text((x, tip_y), line, font=content_font, fill=text_color)
            tip_y += line_height

        # Optional subtitle
        if subtitle:
            subtitle_y = tip_y + 40
            bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
            subtitle_width = bbox[2] - bbox[0]
            subtitle_x = (self.IMAGE_WIDTH - subtitle_width) // 2
            draw.text((subtitle_x, subtitle_y), subtitle, font=subtitle_font, fill=text_color)

    def _render_educational_content(self, draw: ImageDraw.Draw, title: str, points: List[str],
                                     header_font: ImageFont, bullet_font: ImageFont,
                                     text_color: Tuple[int, int, int], accent_color: Tuple[int, int, int],
                                     start_y: int):
        """Render educational content with bullet points."""
        # Title (centered, bold)
        max_width = self.IMAGE_WIDTH - (2 * self.PADDING)
        wrapped_title = self._wrap_text(title, header_font, max_width)[:2]

        title_y = start_y
        line_height = self.HEADER_FONT_SIZE + 15

        for line in wrapped_title:
            bbox = draw.textbbox((0, 0), line, font=header_font)
            text_width = bbox[2] - bbox[0]
            x = (self.IMAGE_WIDTH - text_width) // 2
            draw.text((x, title_y), line, font=header_font, fill=text_color)
            title_y += line_height

        # Bullet points
        bullet_y = title_y + 60
        bullet_spacing = 70
        max_bullet_width = self.IMAGE_WIDTH - (2 * self.PADDING) - 60

        circle_radius = 10
        circle_offset_x = self.PADDING + 30
        text_offset_x = circle_offset_x + circle_radius + 25

        for point in points[:5]:
            # Sage green circle bullet
            draw.ellipse(
                [
                    (circle_offset_x - circle_radius, bullet_y + self.BULLET_FONT_SIZE // 2 - circle_radius),
                    (circle_offset_x + circle_radius, bullet_y + self.BULLET_FONT_SIZE // 2 + circle_radius)
                ],
                fill=accent_color
            )

            # Bullet text
            wrapped_point = self._wrap_text(point, bullet_font, max_bullet_width)
            point_line_height = self.BULLET_FONT_SIZE + 10

            for line in wrapped_point[:2]:  # Max 2 lines per bullet
                draw.text((text_offset_x, bullet_y), line, font=bullet_font, fill=text_color)
                bullet_y += point_line_height

            bullet_y += bullet_spacing - (point_line_height * min(len(wrapped_point), 2))

    def _render_motivation_content(self, draw: ImageDraw.Draw, statement: str,
                                    content_font: ImageFont,
                                    text_color: Tuple[int, int, int], accent_color: Tuple[int, int, int],
                                    start_y: int):
        """Render motivational statement prominently."""
        # Use larger, bold font for motivation
        motivation_font = self._load_font(bold=True, size=80)

        # Wrap statement
        max_width = self.IMAGE_WIDTH - (2 * self.PADDING) - 40
        wrapped_statement = self._wrap_text(statement, motivation_font, max_width)

        # Center vertically in remaining space
        line_height = 85 + 20
        total_height = len(wrapped_statement) * line_height
        statement_y = start_y + (self.IMAGE_HEIGHT - start_y - 150 - total_height) // 2

        for line in wrapped_statement:
            bbox = draw.textbbox((0, 0), line, font=motivation_font)
            text_width = bbox[2] - bbox[0]
            x = (self.IMAGE_WIDTH - text_width) // 2
            draw.text((x, statement_y), line, font=motivation_font, fill=text_color)
            statement_y += line_height

        # Decorative accent lines (minimal)
        line_width = 150
        line_x = (self.IMAGE_WIDTH - line_width) // 2
        line_y = statement_y + 40
        draw.line([(line_x, line_y), (line_x + line_width, line_y)], fill=accent_color, width=4)

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

    def _add_watermark(self, image: Image.Image) -> Image.Image:
        """Add subtle REFILOE watermark in bottom right corner.

        Args:
            image: Image to add watermark to

        Returns:
            PIL.Image: Image with watermark added
        """
        draw = ImageDraw.Draw(image)

        # Use subtle color for watermark
        watermark_color = self._hex_to_rgb(self.ACCENT_COLOR)
        # Make it more subtle by adjusting opacity (through a lighter shade)
        watermark_color = tuple(min(255, c + 60) for c in watermark_color)

        # Load small font
        watermark_font = self._load_font(bold=False, size=self.WATERMARK_SIZE)

        # Watermark text
        watermark_text = "REFILOE"

        # Position in bottom right corner
        bbox = draw.textbbox((0, 0), watermark_text, font=watermark_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = self.IMAGE_WIDTH - self.PADDING - text_width
        y = self.IMAGE_HEIGHT - self.PADDING - text_height - 10

        draw.text((x, y), watermark_text, font=watermark_font, fill=watermark_color)

        return image

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple.

        Args:
            hex_color: Hex color string (e.g., "#F5E6D3")

        Returns:
            Tuple[int, int, int]: RGB values
        """
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
