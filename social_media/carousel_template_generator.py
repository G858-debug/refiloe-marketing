"""Carousel Template Generator - Creates branded Facebook carousel templates for Refiloe"""
import os
import uuid
import textwrap
from typing import Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import yaml
from pathlib import Path

from utils.logger import log_info, log_error, log_warning, log_debug

try:
    from .leonardo_generator import LeonardoGenerator, LeonardoGenerationError
    LEONARDO_AVAILABLE = True
except ImportError:
    LEONARDO_AVAILABLE = False


class CarouselTemplateGenerator:
    """Generates branded Facebook carousel templates for Refiloe"""

    # Official Refiloe Brand Colors
    BACKGROUND_COLOR = "#FFFFFF"  # White - primary background (clean, modern)
    BACKGROUND_CREAM = "#FFF8E8"  # Cream - alternative warm background
    BACKGROUND_BEIGE = "#F7EED3"  # Warm Beige - accent background
    ACCENT_COLOR = "#AAB396"  # Sage Green - primary accent
    TEXT_COLOR = "#674636"  # Dark Brown - primary text (warmer than black)
    TEXT_WHITE = "#FFFFFF"  # White - for dark/colored backgrounds

    # Slide dimensions (4:5 portrait ratio for mobile optimization)
    SLIDE_WIDTH = 1080
    SLIDE_HEIGHT = 1350
    PADDING = 60

    # Font sizes (large for mobile - slides are 1080x1350)
    TITLE_FONT_SIZE = 96
    BODY_FONT_SIZE = 56
    SLIDE_NUMBER_FONT_SIZE = 36
    CTA_FONT_SIZE = 80
    SUBTEXT_FONT_SIZE = 52

    # Avatar dimensions
    AVATAR_SIZE = (400, 400)
    ICON_SIZE = (200, 200)

    def __init__(self, config_path: str):
        """Initialize with config path and load branding from config.yaml

        Args:
            config_path: Path to config.yaml file
        """
        self.config = self._load_config(config_path)
        self.output_dir = Path("/tmp/carousel_slides")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load fonts
        self._title_font = self._load_font(bold=True, size=self.TITLE_FONT_SIZE)
        self._body_font = self._load_font(bold=False, size=self.BODY_FONT_SIZE)
        self._slide_number_font = self._load_font(bold=False, size=self.SLIDE_NUMBER_FONT_SIZE)
        self._cta_font = self._load_font(bold=True, size=self.CTA_FONT_SIZE)
        self._subtext_font = self._load_font(bold=False, size=self.SUBTEXT_FONT_SIZE)

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file

        Args:
            config_path: Path to config.yaml file

        Returns:
            Dict: Configuration dictionary
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except Exception as e:
            raise ValueError(f"Failed to load config from {config_path}: {str(e)}")

    def _load_font(self, bold: bool = False, size: int = 32) -> ImageFont.FreeTypeFont:
        """Load font with specified style and size

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
            # Use a workaround: create scaled bitmap font simulation
            log_warning(f"No TrueType fonts available, using default font (text will be small)")
            return ImageFont.load_default()

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple

        Args:
            hex_color: Hex color string (e.g., "#F5E6D3")

        Returns:
            Tuple[int, int, int]: RGB values
        """
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _create_base_template(self) -> Image.Image:
        """Create base slide template with background color

        Returns:
            PIL.Image: Base template image
        """
        bg_color = self._hex_to_rgb(self.BACKGROUND_COLOR)
        return Image.new('RGB', (self.SLIDE_WIDTH, self.SLIDE_HEIGHT), bg_color)

    def _add_avatar(self, image: Image.Image, avatar_path: str) -> Image.Image:
        """Add avatar image to slide (centered at top)

        Args:
            image: Base image to add avatar to
            avatar_path: Path to avatar image file

        Returns:
            PIL.Image: Image with avatar added
        """
        try:
            avatar = Image.open(avatar_path)
            avatar = avatar.convert('RGBA')
            avatar = avatar.resize(self.AVATAR_SIZE, Image.Resampling.LANCZOS)

            # Create circular mask for avatar
            mask = Image.new('L', self.AVATAR_SIZE, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, self.AVATAR_SIZE[0], self.AVATAR_SIZE[1]), fill=255)

            # Calculate center position
            x = (self.SLIDE_WIDTH - self.AVATAR_SIZE[0]) // 2
            y = self.PADDING + 40  # Top padding plus some extra space

            # Paste avatar with mask
            image.paste(avatar, (x, y), mask)

        except Exception as e:
            # If avatar fails to load, draw a placeholder circle
            draw = ImageDraw.Draw(image)
            x = (self.SLIDE_WIDTH - self.AVATAR_SIZE[0]) // 2
            y = self.PADDING + 40
            text_color = self._hex_to_rgb(self.TEXT_COLOR)
            draw.ellipse(
                (x, y, x + self.AVATAR_SIZE[0], y + self.AVATAR_SIZE[1]),
                outline=text_color,
                width=3
            )

        return image

    def _add_title(self, image: Image.Image, title: str, y_position: int) -> Image.Image:
        """Add title text to slide (centered, max 2 lines)

        Args:
            image: Image to add title to
            title: Title text
            y_position: Y coordinate for title

        Returns:
            PIL.Image: Image with title added
        """
        draw = ImageDraw.Draw(image)
        text_color = self._hex_to_rgb(self.TEXT_COLOR)

        # Calculate max width for text (accounting for padding)
        max_width = self.SLIDE_WIDTH - (2 * self.PADDING)

        # Wrap text to fit within max width (max 2 lines)
        wrapped_lines = self._wrap_text(title, self._title_font, max_width)[:2]

        # Draw each line centered
        current_y = y_position
        line_height = self.TITLE_FONT_SIZE + 10

        for line in wrapped_lines:
            bbox = draw.textbbox((0, 0), line, font=self._title_font)
            text_width = bbox[2] - bbox[0]
            x = (self.SLIDE_WIDTH - text_width) // 2
            draw.text((x, current_y), line, font=self._title_font, fill=text_color)
            current_y += line_height

        return image

    def _add_bullet_points(self, image: Image.Image, bullets: List[str], start_y: int) -> Image.Image:
        """Add bullet points to slide

        Args:
            image: Image to add bullets to
            bullets: List of bullet point strings (3-5 bullets)
            start_y: Y coordinate to start bullets

        Returns:
            PIL.Image: Image with bullet points added
        """
        draw = ImageDraw.Draw(image)
        text_color = self._hex_to_rgb(self.TEXT_COLOR)
        accent_color = self._hex_to_rgb(self.ACCENT_COLOR)

        max_width = self.SLIDE_WIDTH - (2 * self.PADDING) - 40  # Extra indent for bullet
        bullet_char = "\u2022"  # Unicode bullet character
        line_height = self.BODY_FONT_SIZE + 40

        current_y = start_y

        for bullet in bullets[:5]:  # Max 5 bullets
            # Wrap the bullet text
            wrapped = self._wrap_text(bullet, self._body_font, max_width)

            for i, line in enumerate(wrapped):
                x = self.PADDING
                if i == 0:
                    # First line gets colored bullet point
                    draw.text((x, current_y), bullet_char, font=self._body_font, fill=accent_color)
                    draw.text((x + 30, current_y), line, font=self._body_font, fill=text_color)
                else:
                    # Continuation lines are indented
                    draw.text((x + 30, current_y), line, font=self._body_font, fill=text_color)
                current_y += line_height

            current_y += 10  # Extra spacing between bullets

        return image

    def _add_slide_number(self, image: Image.Image, current: int, total: int) -> Image.Image:
        """Add slide number to bottom right corner

        Args:
            image: Image to add slide number to
            current: Current slide number
            total: Total number of slides

        Returns:
            PIL.Image: Image with slide number added
        """
        draw = ImageDraw.Draw(image)
        text_color = self._hex_to_rgb(self.TEXT_COLOR)

        slide_text = f"{current}/{total}"
        bbox = draw.textbbox((0, 0), slide_text, font=self._slide_number_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = self.SLIDE_WIDTH - self.PADDING - text_width
        y = self.SLIDE_HEIGHT - self.PADDING - text_height

        draw.text((x, y), slide_text, font=self._slide_number_font, fill=text_color)

        return image

    def _add_slide_number_white(self, image: Image.Image, current: int, total: int) -> Image.Image:
        """Add slide number in white to bottom right corner

        Args:
            image: Image to add slide number to
            current: Current slide number
            total: Total number of slides

        Returns:
            PIL.Image: Image with slide number added
        """
        draw = ImageDraw.Draw(image)
        text_color = (255, 255, 255)  # White

        slide_text = f"{current}/{total}"
        bbox = draw.textbbox((0, 0), slide_text, font=self._slide_number_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = self.SLIDE_WIDTH - self.PADDING - text_width
        y = self.SLIDE_HEIGHT - self.PADDING - text_height

        draw.text((x, y), slide_text, font=self._slide_number_font, fill=text_color)

        return image

    def _add_cta_section(self, image: Image.Image, headline: str, cta_text: str, subtext: str, use_white_text: bool = False) -> Image.Image:
        """Add CTA section to slide

        Args:
            image: Image to add CTA to
            headline: Main headline text (48pt, centered)
            cta_text: Call-to-action text (bold, 40pt)
            subtext: Supporting text below CTA (28pt)
            use_white_text: Whether to use white text for contrast

        Returns:
            PIL.Image: Image with CTA section added
        """
        draw = ImageDraw.Draw(image)

        # Choose text color based on background
        if use_white_text:
            text_color = (255, 255, 255)  # White
            secondary_color = (255, 255, 255, 200)  # Slightly transparent white
        else:
            text_color = self._hex_to_rgb(self.TEXT_COLOR)
            secondary_color = text_color

        # Center content vertically
        total_height = self.TITLE_FONT_SIZE + 40 + self.CTA_FONT_SIZE + 30 + self.SUBTEXT_FONT_SIZE
        start_y = (self.SLIDE_HEIGHT - total_height) // 2

        # Draw headline (centered)
        if headline:
            max_width = self.SLIDE_WIDTH - (2 * self.PADDING)
            wrapped = self._wrap_text(headline, self._title_font, max_width)[:2]
            current_y = start_y
            for line in wrapped:
                bbox = draw.textbbox((0, 0), line, font=self._title_font)
                text_width = bbox[2] - bbox[0]
                x = (self.SLIDE_WIDTH - text_width) // 2
                draw.text((x, current_y), line, font=self._title_font, fill=text_color)
                current_y += self.TITLE_FONT_SIZE + 10
            start_y = current_y + 30

        # Draw CTA text (centered, larger)
        if cta_text:
            bbox = draw.textbbox((0, 0), cta_text, font=self._cta_font)
            text_width = bbox[2] - bbox[0]
            x = (self.SLIDE_WIDTH - text_width) // 2
            draw.text((x, start_y), cta_text, font=self._cta_font, fill=text_color)
            start_y += self.CTA_FONT_SIZE + 30

        # Draw subtext (centered)
        if subtext:
            bbox = draw.textbbox((0, 0), subtext, font=self._subtext_font)
            text_width = bbox[2] - bbox[0]
            x = (self.SLIDE_WIDTH - text_width) // 2
            draw.text((x, start_y), subtext, font=self._subtext_font, fill=text_color)

        return image

    def _add_step_header(self, image: Image.Image, step_title: str) -> Image.Image:
        """Add step number/title to top of content slide

        Args:
            image: Image to add header to
            step_title: Step title (e.g., "Step 1: Setup")

        Returns:
            PIL.Image: Image with step header added
        """
        draw = ImageDraw.Draw(image)
        text_color = self._hex_to_rgb(self.TEXT_COLOR)
        accent_color = self._hex_to_rgb(self.ACCENT_COLOR)

        y = self.PADDING + 40

        # Check if title has step format (e.g., "Step 1: Setup")
        if step_title.startswith('Step '):
            parts = step_title.split(':', 1)
            step_num = parts[0]  # "Step 1"
            step_rest = parts[1].strip() if len(parts) > 1 else ""

            # Calculate widths for centering
            full_text = step_title
            full_bbox = draw.textbbox((0, 0), full_text, font=self._title_font)
            full_width = full_bbox[2] - full_bbox[0]
            start_x = (self.SLIDE_WIDTH - full_width) // 2

            # Draw step number in accent color
            draw.text((start_x, y), step_num + ":", font=self._title_font, fill=accent_color)

            # Draw rest of title in normal color if present
            if step_rest:
                step_num_bbox = draw.textbbox((0, 0), step_num + ": ", font=self._title_font)
                step_num_width = step_num_bbox[2] - step_num_bbox[0]
                draw.text((start_x + step_num_width, y), step_rest, font=self._title_font, fill=text_color)
        else:
            # No step format, just center the title
            bbox = draw.textbbox((0, 0), step_title, font=self._title_font)
            text_width = bbox[2] - bbox[0]
            x = (self.SLIDE_WIDTH - text_width) // 2
            draw.text((x, y), step_title, font=self._title_font, fill=text_color)

        return image

    def _add_icon(self, image: Image.Image, icon_path: str) -> Image.Image:
        """Add optional small icon at bottom center of slide

        Args:
            image: Image to add icon to
            icon_path: Path to icon image file

        Returns:
            PIL.Image: Image with icon added
        """
        try:
            icon = Image.open(icon_path)
            icon = icon.convert('RGBA')
            icon = icon.resize(self.ICON_SIZE, Image.Resampling.LANCZOS)

            # Calculate center bottom position
            x = (self.SLIDE_WIDTH - self.ICON_SIZE[0]) // 2
            y = self.SLIDE_HEIGHT - self.PADDING - self.ICON_SIZE[1] - 50

            # Create a copy to avoid modifying original
            result = image.copy()
            result.paste(icon, (x, y), icon if icon.mode == 'RGBA' else None)
            return result

        except Exception:
            # If icon fails to load, return original image
            return image

    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        """Wrap text to fit within max width

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

    def _generate_leonardo_cover(
        self,
        title: str,
        content_type: str = "educational",
    ) -> Optional[str]:
        """Generate a cover slide image using Leonardo AI.

        Args:
            title: The carousel title.
            content_type: Content type for styling.

        Returns:
            URL of generated image, or None if generation fails.
        """
        if not LEONARDO_AVAILABLE:
            log_warning("Leonardo AI not available for carousel cover, using local fallback")
            return None

        log_info(f"🎨 Generating Leonardo carousel cover for title: '{title[:50]}...' (content_type: {content_type})")

        try:
            leonardo = LeonardoGenerator()
            result = leonardo.generate_carousel_cover(
                title=title,
                content_type=content_type,
                width=1080,
                height=1350,
            )

            image_url = result.get("image_url")
            if image_url:
                log_info(f"✅ Leonardo carousel cover generated: {image_url}")
                return image_url
            else:
                log_warning("Leonardo returned no image URL for carousel cover")
                return None

        except LeonardoGenerationError as e:
            log_warning(f"Leonardo carousel cover generation failed: {e}, using local fallback")
            return None
        except Exception as e:
            log_warning(f"Unexpected error generating Leonardo carousel cover: {e}, using local fallback")
            return None

    def _create_cover_slide(self, data: Dict, slide_number: int, total_slides: int) -> Image.Image:
        """Create a COVER slide

        Args:
            data: Slide data with 'avatar_path' and 'title'
            slide_number: Current slide number
            total_slides: Total number of slides

        Returns:
            PIL.Image: Generated cover slide
        """
        image = self._create_base_template()

        # Add avatar at top
        avatar_path = data.get('avatar_path', '')
        if avatar_path:
            image = self._add_avatar(image, avatar_path)

        # Calculate title position (below avatar)
        title_y = self.PADDING + 40 + self.AVATAR_SIZE[1] + 60
        image = self._add_title(image, data.get('title', ''), title_y)

        # Add slide number
        image = self._add_slide_number(image, slide_number, total_slides)

        return image

    def _create_content_slide(self, data: Dict, slide_number: int, total_slides: int) -> Image.Image:
        """Create a CONTENT slide with large, readable text

        Args:
            data: Slide data with 'step_title', 'bullets', and optional 'icon_path'
            slide_number: Current slide number
            total_slides: Total number of slides

        Returns:
            PIL.Image: Generated content slide
        """
        image = self._create_base_template()
        draw = ImageDraw.Draw(image)

        accent_color = self._hex_to_rgb(self.ACCENT_COLOR)
        cream_color = self._hex_to_rgb(self.BACKGROUND_CREAM)
        text_color = self._hex_to_rgb(self.TEXT_COLOR)

        # Load LARGE fonts directly (not using cached fonts)
        large_title_font = self._load_font(bold=True, size=100)
        large_body_font = self._load_font(bold=False, size=64)

        # Thick accent bar at top
        draw.rectangle([(0, 0), (self.SLIDE_WIDTH, 24)], fill=accent_color)

        # Header banner background (cream colored box for step title)
        header_top = 80
        header_height = 180
        draw.rectangle(
            [(0, header_top), (self.SLIDE_WIDTH, header_top + header_height)],
            fill=cream_color
        )

        # Step title - LARGE and centered in the header banner
        step_title = data.get('step_title', f'Step {slide_number - 1}')

        # Draw step title centered in header banner
        title_y = header_top + (header_height - 100) // 2
        bbox = draw.textbbox((0, 0), step_title, font=large_title_font)
        text_width = bbox[2] - bbox[0]
        title_x = (self.SLIDE_WIDTH - text_width) // 2
        draw.text((title_x, title_y), step_title, font=large_title_font, fill=text_color)

        # Bullet points - LARGE and prominent
        bullets = data.get('bullets', [])
        bullet_start_y = header_top + header_height + 100

        max_width = self.SLIDE_WIDTH - (2 * self.PADDING) - 80
        line_height = 64 + 50  # Font size + spacing

        current_y = bullet_start_y

        for idx, bullet in enumerate(bullets[:3]):  # Max 3 bullets for readability
            # Clean the bullet text - remove non-ASCII and special characters
            clean_bullet = ''.join(char for char in bullet if ord(char) < 128 and ord(char) >= 32)
            clean_bullet = clean_bullet.strip()
            if not clean_bullet:
                clean_bullet = "Tip"

            # Wrap the bullet text
            wrapped = self._wrap_text(clean_bullet, large_body_font, max_width)

            for i, line in enumerate(wrapped[:2]):  # Max 2 lines per bullet
                x = self.PADDING + 30
                if i == 0:
                    # Draw number instead of bullet for visual variety
                    number_text = f"{idx + 1}."
                    draw.text((x, current_y), number_text, font=large_body_font, fill=accent_color)
                    draw.text((x + 60, current_y), line, font=large_body_font, fill=text_color)
                else:
                    # Continuation lines are indented
                    draw.text((x + 60, current_y), line, font=large_body_font, fill=text_color)
                current_y += line_height

            current_y += 30  # Extra spacing between bullets

        # Decorative accent line near bottom
        bottom_y = self.SLIDE_HEIGHT - 140
        line_width = 350
        line_x = (self.SLIDE_WIDTH - line_width) // 2
        draw.line([(line_x, bottom_y), (line_x + line_width, bottom_y)],
                  fill=accent_color, width=8)

        # Slide number
        slide_font = self._load_font(bold=False, size=40)
        slide_text = f"{slide_number}/{total_slides}"
        bbox = draw.textbbox((0, 0), slide_text, font=slide_font)
        text_width = bbox[2] - bbox[0]
        x = self.SLIDE_WIDTH - self.PADDING - text_width
        y = self.SLIDE_HEIGHT - self.PADDING - 40
        draw.text((x, y), slide_text, font=slide_font, fill=text_color)

        return image

    def _create_cta_slide(self, data: Dict, slide_number: int, total_slides: int) -> Image.Image:
        """Create a CTA (call-to-action) slide with large text

        Args:
            data: Slide data with 'headline', 'cta_text', and 'subtext'
            slide_number: Current slide number
            total_slides: Total number of slides

        Returns:
            PIL.Image: Generated CTA slide
        """
        # Create base with accent color background
        accent_color = self._hex_to_rgb(self.ACCENT_COLOR)
        image = Image.new('RGB', (self.SLIDE_WIDTH, self.SLIDE_HEIGHT), accent_color)
        draw = ImageDraw.Draw(image)

        # Load LARGE fonts for CTA
        headline_font = self._load_font(bold=True, size=90)
        cta_font = self._load_font(bold=True, size=72)
        subtext_font = self._load_font(bold=False, size=52)
        slide_font = self._load_font(bold=False, size=40)

        text_color = (255, 255, 255)  # White text on sage background

        # Add decorative circles (subtle branding)
        circle_color = self._hex_to_rgb(self.BACKGROUND_BEIGE)
        # Large circle
        draw.ellipse([(self.SLIDE_WIDTH//2 - 350, self.SLIDE_HEIGHT//2 - 350),
                      (self.SLIDE_WIDTH//2 + 350, self.SLIDE_HEIGHT//2 + 350)],
                     outline=circle_color, width=3)
        # Medium circle
        draw.ellipse([(self.SLIDE_WIDTH//2 - 250, self.SLIDE_HEIGHT//2 - 250),
                      (self.SLIDE_WIDTH//2 + 250, self.SLIDE_HEIGHT//2 + 250)],
                     outline=circle_color, width=2)

        # Get text content
        headline = data.get('headline', 'Ready to Save Time?')
        cta_text = data.get('cta_text', 'Follow for more tips!')
        subtext = data.get('subtext', 'Save this post for later')

        # Calculate vertical centering
        total_text_height = 90 + 60 + 72 + 50 + 52  # headline + gap + cta + gap + subtext
        start_y = (self.SLIDE_HEIGHT - total_text_height) // 2

        # Draw headline (centered)
        max_width = self.SLIDE_WIDTH - (2 * self.PADDING)
        wrapped = self._wrap_text(headline, headline_font, max_width)[:2]
        current_y = start_y
        for line in wrapped:
            bbox = draw.textbbox((0, 0), line, font=headline_font)
            text_width = bbox[2] - bbox[0]
            x = (self.SLIDE_WIDTH - text_width) // 2
            draw.text((x, current_y), line, font=headline_font, fill=text_color)
            current_y += 100

        current_y += 40  # Gap

        # Draw CTA text (centered)
        bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
        text_width = bbox[2] - bbox[0]
        x = (self.SLIDE_WIDTH - text_width) // 2
        draw.text((x, current_y), cta_text, font=cta_font, fill=text_color)
        current_y += 72 + 50  # Font height + gap

        # Draw subtext (centered)
        bbox = draw.textbbox((0, 0), subtext, font=subtext_font)
        text_width = bbox[2] - bbox[0]
        x = (self.SLIDE_WIDTH - text_width) // 2
        draw.text((x, current_y), subtext, font=subtext_font, fill=text_color)

        # Add slide number (white on sage)
        slide_text = f"{slide_number}/{total_slides}"
        bbox = draw.textbbox((0, 0), slide_text, font=slide_font)
        text_width = bbox[2] - bbox[0]
        x = self.SLIDE_WIDTH - self.PADDING - text_width
        y = self.SLIDE_HEIGHT - self.PADDING - 40
        draw.text((x, y), slide_text, font=slide_font, fill=text_color)

        return image

    def create_carousel(self, carousel_data: Dict) -> List[str]:
        """Generate a complete carousel from carousel data

        Args:
            carousel_data: Dictionary containing carousel configuration:
                {
                    'slides': [
                        {
                            'type': 'COVER',
                            'avatar_path': '/path/to/avatar.png',
                            'title': 'Your Title Here'
                        },
                        {
                            'type': 'CONTENT',
                            'step_title': 'Step 1: Setup',
                            'bullets': ['Point 1', 'Point 2', 'Point 3'],
                            'icon_path': '/path/to/icon.png'  # optional
                        },
                        {
                            'type': 'CTA',
                            'headline': 'Ready to Start?',
                            'cta_text': 'Join Now!',
                            'subtext': 'Limited time offer'
                        }
                    ]
                }

        Returns:
            List[str]: List of file paths to generated slide images
        """
        slides = carousel_data.get('slides', [])
        if not slides:
            raise ValueError("Carousel data must contain at least one slide")

        total_slides = len(slides)
        generated_paths = []

        # Generate unique carousel ID for file naming
        carousel_id = uuid.uuid4().hex[:8]

        for i, slide_data in enumerate(slides):
            slide_number = i + 1
            slide_type = slide_data.get('type', '').upper()

            # Create slide based on type
            if slide_type == 'COVER':
                # Try Leonardo AI first for cover
                leonardo_cover_url = self._generate_leonardo_cover(
                    title=slide_data.get('text', slide_data.get('title', '')),
                    content_type=carousel_data.get('content_type', 'educational'),
                )

                if leonardo_cover_url:
                    # Download and save Leonardo image
                    import requests
                    from io import BytesIO

                    try:
                        response = requests.get(leonardo_cover_url, timeout=30)
                        response.raise_for_status()
                        image = Image.open(BytesIO(response.content))

                        filename = f"carousel_{carousel_id}_slide_{slide_number:02d}.png"
                        filepath = self.output_dir / filename
                        image.save(filepath, 'PNG', quality=95)
                        generated_paths.append(str(filepath))
                        log_info(f"Leonardo cover saved: {filepath}")
                        continue  # Skip local generation
                    except Exception as e:
                        log_warning(f"Failed to download Leonardo cover: {e}, using local fallback")

                # Fallback to local cover generation
                image = self._create_cover_slide(slide_data, slide_number, total_slides)
            elif slide_type == 'CONTENT':
                image = self._create_content_slide(slide_data, slide_number, total_slides)
            elif slide_type == 'CTA':
                image = self._create_cta_slide(slide_data, slide_number, total_slides)
            else:
                # Default to content slide for unknown types
                image = self._create_content_slide(slide_data, slide_number, total_slides)

            # Save slide
            filename = f"carousel_{carousel_id}_slide_{slide_number:02d}.png"
            filepath = self.output_dir / filename
            image.save(filepath, 'PNG', quality=95)
            generated_paths.append(str(filepath))

        return generated_paths
