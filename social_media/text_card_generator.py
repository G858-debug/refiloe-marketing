"""Text Card Generator - Creates single-slide text images for social media using PIL"""
import os
import uuid
import random
from typing import Dict, List, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import yaml

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

    # Image dimensions (4:5 portrait ratio for mobile optimization)
    IMAGE_WIDTH = 1080
    IMAGE_HEIGHT = 1350
    PADDING = 60

    # Accent bar height
    ACCENT_BAR_HEIGHT = 20

    # Font sizes
    QUOTE_FONT_SIZE = 72
    QUOTE_ATTRIBUTION_SIZE = 48
    TIP_HEADER_SIZE = 56
    TIP_BODY_SIZE = 64
    TIP_SUBTITLE_SIZE = 48
    EDU_TITLE_SIZE = 80
    EDU_BULLET_SIZE = 52
    MOTIVATION_SIZE = 96
    WATERMARK_SIZE = 32

    def __init__(self, config_path: str = 'social_media/config.yaml'):
        """Initialize with config and setup output directory.

        Args:
            config_path: Path to config.yaml file
        """
        self.config_path = config_path
        self.output_dir = Path("/tmp/text_cards")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Background colors for random selection
        self.background_colors = [
            self.BACKGROUND_WHITE,
            self.BACKGROUND_CREAM,
            self.BACKGROUND_BEIGE
        ]

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
            # Create image based on content type
            if content_type == 'quote':
                image = self._create_quote_layout(
                    content.get('quote', ''),
                    content.get('attribution', '')
                )
            elif content_type == 'tip':
                image = self._create_tip_layout(
                    content.get('header', ''),
                    content.get('tip', ''),
                    content.get('subtitle')
                )
            elif content_type == 'educational':
                image = self._create_educational_layout(
                    content.get('title', ''),
                    content.get('points', [])
                )
            elif content_type == 'motivation':
                image = self._create_motivation_layout(
                    content.get('statement', '')
                )
            else:
                log_error(f"Unknown content type: {content_type}")
                raise ValueError(f"Unknown content type: {content_type}. Must be one of: quote, tip, educational, motivation")

            # Add watermark
            image = self._add_watermark(image)

            # Save image
            filename = f"text_card_{content_type}_{uuid.uuid4().hex[:8]}.png"
            filepath = self.output_dir / filename
            image.save(filepath, 'PNG', quality=95)

            log_info(f"Text card generated: {filepath}")
            return str(filepath)

        except Exception as e:
            log_error(f"Failed to generate text card: {str(e)}")
            raise

    def _create_quote_layout(self, quote: str, attribution: str) -> Image.Image:
        """Create quote card with decorative quotation marks.

        Args:
            quote: The quote text
            attribution: The attribution line (author/source)

        Returns:
            PIL.Image: Generated quote card
        """
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)

        text_color = self._hex_to_rgb(self.TEXT_COLOR)
        accent_color = self._hex_to_rgb(self.ACCENT_COLOR)

        # Load fonts
        quote_font = self._load_font(bold=False, size=self.QUOTE_FONT_SIZE)
        attribution_font = self._load_font(bold=False, size=self.QUOTE_ATTRIBUTION_SIZE)

        # Draw large decorative quotation marks
        quote_mark_font = self._load_font(bold=True, size=180)
        quote_mark_y = 180

        # Opening quote mark (top left area, but centered)
        quote_mark = '"'
        bbox = draw.textbbox((0, 0), quote_mark, font=quote_mark_font)
        mark_width = bbox[2] - bbox[0]
        mark_x = (self.IMAGE_WIDTH - mark_width) // 2
        draw.text((mark_x, quote_mark_y), quote_mark, font=quote_mark_font, fill=accent_color)

        # Main quote text (centered, wrapped)
        max_width = self.IMAGE_WIDTH - (2 * self.PADDING) - 80
        wrapped_quote = self._wrap_text(quote, quote_font, max_width)

        # Calculate starting Y position for quote text
        line_height = self.QUOTE_FONT_SIZE + 20
        total_quote_height = len(wrapped_quote) * line_height
        quote_start_y = quote_mark_y + 220

        # Draw quote lines centered
        current_y = quote_start_y
        for line in wrapped_quote:
            bbox = draw.textbbox((0, 0), line, font=quote_font)
            text_width = bbox[2] - bbox[0]
            x = (self.IMAGE_WIDTH - text_width) // 2
            draw.text((x, current_y), line, font=quote_font, fill=text_color)
            current_y += line_height

        # Attribution line (with em-dash)
        if attribution:
            attribution_text = f"— {attribution}"
            bbox = draw.textbbox((0, 0), attribution_text, font=attribution_font)
            attr_width = bbox[2] - bbox[0]
            attr_x = (self.IMAGE_WIDTH - attr_width) // 2
            attr_y = current_y + 40
            draw.text((attr_x, attr_y), attribution_text, font=attribution_font, fill=text_color)

        # Decorative accent line below attribution
        line_width = 300
        line_x = (self.IMAGE_WIDTH - line_width) // 2
        line_y = self.IMAGE_HEIGHT - 180
        draw.line([(line_x, line_y), (line_x + line_width, line_y)], fill=accent_color, width=6)

        return image

    def _create_tip_layout(self, header: str, tip: str, subtitle: str = None) -> Image.Image:
        """Create tip card with header badge.

        Args:
            header: Header text for the badge
            tip: Main tip text
            subtitle: Optional subtitle below the tip

        Returns:
            PIL.Image: Generated tip card
        """
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)

        text_color = self._hex_to_rgb(self.TEXT_COLOR)
        accent_color = self._hex_to_rgb(self.ACCENT_COLOR)
        white_color = self._hex_to_rgb(self.TEXT_WHITE)

        # Load fonts
        header_font = self._load_font(bold=True, size=self.TIP_HEADER_SIZE)
        tip_font = self._load_font(bold=False, size=self.TIP_BODY_SIZE)
        subtitle_font = self._load_font(bold=False, size=self.TIP_SUBTITLE_SIZE)

        # Header badge at top (sage green background, white text)
        badge_height = 120
        badge_y = 150
        draw.rectangle(
            [(self.PADDING, badge_y), (self.IMAGE_WIDTH - self.PADDING, badge_y + badge_height)],
            fill=accent_color
        )

        # Draw header text in badge (centered)
        bbox = draw.textbbox((0, 0), header, font=header_font)
        header_width = bbox[2] - bbox[0]
        header_x = (self.IMAGE_WIDTH - header_width) // 2
        header_y = badge_y + (badge_height - self.TIP_HEADER_SIZE) // 2 - 10
        draw.text((header_x, header_y), header, font=header_font, fill=white_color)

        # Main tip text (large, centered, wrapped)
        max_width = self.IMAGE_WIDTH - (2 * self.PADDING) - 40
        wrapped_tip = self._wrap_text(tip, tip_font, max_width)

        # Calculate starting position
        line_height = self.TIP_BODY_SIZE + 25
        tip_start_y = badge_y + badge_height + 120

        # Draw tip lines centered
        current_y = tip_start_y
        for line in wrapped_tip:
            bbox = draw.textbbox((0, 0), line, font=tip_font)
            text_width = bbox[2] - bbox[0]
            x = (self.IMAGE_WIDTH - text_width) // 2
            draw.text((x, current_y), line, font=tip_font, fill=text_color)
            current_y += line_height

        # Optional subtitle below
        if subtitle:
            subtitle_y = current_y + 50
            bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
            subtitle_width = bbox[2] - bbox[0]
            subtitle_x = (self.IMAGE_WIDTH - subtitle_width) // 2
            draw.text((subtitle_x, subtitle_y), subtitle, font=subtitle_font, fill=text_color)

        return image

    def _create_educational_layout(self, title: str, points: List[str]) -> Image.Image:
        """Create educational card with bullet points.

        Args:
            title: Title at the top
            points: List of 3-5 bullet points

        Returns:
            PIL.Image: Generated educational card
        """
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)

        text_color = self._hex_to_rgb(self.TEXT_COLOR)
        accent_color = self._hex_to_rgb(self.ACCENT_COLOR)

        # Load fonts
        title_font = self._load_font(bold=True, size=self.EDU_TITLE_SIZE)
        bullet_font = self._load_font(bold=False, size=self.EDU_BULLET_SIZE)

        # Title at top (bold, large, centered)
        max_width = self.IMAGE_WIDTH - (2 * self.PADDING)
        wrapped_title = self._wrap_text(title, title_font, max_width)[:2]  # Max 2 lines

        title_y = 150
        line_height = self.EDU_TITLE_SIZE + 15

        current_y = title_y
        for line in wrapped_title:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            text_width = bbox[2] - bbox[0]
            x = (self.IMAGE_WIDTH - text_width) // 2
            draw.text((x, current_y), line, font=title_font, fill=text_color)
            current_y += line_height

        # Bullet points with custom sage green circle bullets
        bullet_start_y = current_y + 100
        bullet_spacing = 90
        max_bullet_width = self.IMAGE_WIDTH - (2 * self.PADDING) - 80

        current_y = bullet_start_y
        circle_radius = 12
        circle_offset_x = self.PADDING + 40
        text_offset_x = circle_offset_x + circle_radius + 30

        # Draw up to 5 bullet points
        for point in points[:5]:
            # Draw sage green circle bullet
            draw.ellipse(
                [
                    (circle_offset_x - circle_radius, current_y + self.EDU_BULLET_SIZE // 2 - circle_radius),
                    (circle_offset_x + circle_radius, current_y + self.EDU_BULLET_SIZE // 2 + circle_radius)
                ],
                fill=accent_color
            )

            # Wrap and draw bullet text
            wrapped_point = self._wrap_text(point, bullet_font, max_bullet_width)
            point_line_height = self.EDU_BULLET_SIZE + 12

            for i, line in enumerate(wrapped_point[:3]):  # Max 3 lines per bullet
                draw.text((text_offset_x, current_y), line, font=bullet_font, fill=text_color)
                current_y += point_line_height

            current_y += bullet_spacing - (point_line_height * min(len(wrapped_point), 3))

        return image

    def _create_motivation_layout(self, statement: str) -> Image.Image:
        """Create motivation card with bold statement.

        Args:
            statement: Bold motivational statement

        Returns:
            PIL.Image: Generated motivation card
        """
        image = self._create_base_image()
        draw = ImageDraw.Draw(image)

        text_color = self._hex_to_rgb(self.TEXT_COLOR)
        accent_color = self._hex_to_rgb(self.ACCENT_COLOR)

        # Load font (extra large, bold)
        statement_font = self._load_font(bold=True, size=self.MOTIVATION_SIZE)

        # Wrap statement text
        max_width = self.IMAGE_WIDTH - (2 * self.PADDING) - 60
        wrapped_statement = self._wrap_text(statement, statement_font, max_width)

        # Calculate vertical centering
        line_height = self.MOTIVATION_SIZE + 25
        total_height = len(wrapped_statement) * line_height
        start_y = (self.IMAGE_HEIGHT - total_height) // 2

        # Draw statement lines centered
        current_y = start_y
        for line in wrapped_statement:
            bbox = draw.textbbox((0, 0), line, font=statement_font)
            text_width = bbox[2] - bbox[0]
            x = (self.IMAGE_WIDTH - text_width) // 2
            draw.text((x, current_y), line, font=statement_font, fill=text_color)
            current_y += line_height

        # Decorative elements (abstract shapes in sage green)
        # Top left corner accent
        draw.arc(
            [(40, 140), (240, 340)],
            start=0, end=90, fill=accent_color, width=8
        )

        # Bottom right corner accent
        draw.arc(
            [(self.IMAGE_WIDTH - 240, self.IMAGE_HEIGHT - 340),
             (self.IMAGE_WIDTH - 40, self.IMAGE_HEIGHT - 140)],
            start=180, end=270, fill=accent_color, width=8
        )

        # Decorative lines
        # Top right
        draw.line(
            [(self.IMAGE_WIDTH - 150, 180), (self.IMAGE_WIDTH - 60, 180)],
            fill=accent_color, width=6
        )
        draw.line(
            [(self.IMAGE_WIDTH - 150, 220), (self.IMAGE_WIDTH - 60, 220)],
            fill=accent_color, width=6
        )

        # Bottom left
        draw.line(
            [(60, self.IMAGE_HEIGHT - 180), (150, self.IMAGE_HEIGHT - 180)],
            fill=accent_color, width=6
        )
        draw.line(
            [(60, self.IMAGE_HEIGHT - 220), (150, self.IMAGE_HEIGHT - 220)],
            fill=accent_color, width=6
        )

        return image

    def _create_base_image(self, background_color: str = None) -> Image.Image:
        """Create base image with random background color and top accent bar.

        Args:
            background_color: Optional specific background color (hex string).
                            If None, randomly selects from brand backgrounds.

        Returns:
            PIL.Image: Base image with background and accent bar
        """
        # Select background color
        if background_color is None:
            background_color = random.choice(self.background_colors)

        bg_rgb = self._hex_to_rgb(background_color)
        accent_rgb = self._hex_to_rgb(self.ACCENT_COLOR)

        # Create base image
        image = Image.new('RGB', (self.IMAGE_WIDTH, self.IMAGE_HEIGHT), bg_rgb)
        draw = ImageDraw.Draw(image)

        # Add top accent bar (sage green)
        draw.rectangle(
            [(0, 0), (self.IMAGE_WIDTH, self.ACCENT_BAR_HEIGHT)],
            fill=accent_rgb
        )

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
