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

    # Brand colors
    BACKGROUND_COLOR = "#F5E6D3"  # Beige
    TEXT_COLOR = "#8B7355"  # Dark brown

    # Slide dimensions
    SLIDE_WIDTH = 1080
    SLIDE_HEIGHT = 1080
    PADDING = 60

    # Font sizes
    TITLE_FONT_SIZE = 48
    BODY_FONT_SIZE = 32
    SLIDE_NUMBER_FONT_SIZE = 24
    CTA_FONT_SIZE = 40
    SUBTEXT_FONT_SIZE = 28

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
        """Load Arial font with specified style and size

        Args:
            bold: Whether to use bold font
            size: Font size in points

        Returns:
            ImageFont.FreeTypeFont: Loaded font
        """
        # Try common font paths
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "Arial Bold.ttf" if bold else "Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        ]

        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, size)
            except (OSError, IOError):
                continue

        # Fallback to default font
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

        max_width = self.SLIDE_WIDTH - (2 * self.PADDING) - 40  # Extra indent for bullet
        bullet_char = "\u2022"  # Unicode bullet character
        line_height = self.BODY_FONT_SIZE + 20

        current_y = start_y

        for bullet in bullets[:5]:  # Max 5 bullets
            # Wrap the bullet text
            wrapped = self._wrap_text(bullet, self._body_font, max_width)

            for i, line in enumerate(wrapped):
                x = self.PADDING
                if i == 0:
                    # First line gets bullet point
                    draw.text((x, current_y), bullet_char, font=self._body_font, fill=text_color)
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

    def _add_cta_section(self, image: Image.Image, headline: str, cta_text: str, subtext: str) -> Image.Image:
        """Add CTA section to slide (headline, CTA text, subtext)

        Args:
            image: Image to add CTA to
            headline: Main headline text (48pt, centered)
            cta_text: Call-to-action text (bold, 40pt)
            subtext: Supporting text below CTA (28pt)

        Returns:
            PIL.Image: Image with CTA section added
        """
        draw = ImageDraw.Draw(image)
        text_color = self._hex_to_rgb(self.TEXT_COLOR)

        max_width = self.SLIDE_WIDTH - (2 * self.PADDING)
        vertical_center = self.SLIDE_HEIGHT // 2

        # Draw headline at top area
        headline_y = self.PADDING + 100
        headline_lines = self._wrap_text(headline, self._title_font, max_width)[:2]
        current_y = headline_y

        for line in headline_lines:
            bbox = draw.textbbox((0, 0), line, font=self._title_font)
            text_width = bbox[2] - bbox[0]
            x = (self.SLIDE_WIDTH - text_width) // 2
            draw.text((x, current_y), line, font=self._title_font, fill=text_color)
            current_y += self.TITLE_FONT_SIZE + 10

        # Draw CTA text in the middle (bold, larger)
        cta_y = vertical_center - 20
        cta_lines = self._wrap_text(cta_text, self._cta_font, max_width)[:2]

        for line in cta_lines:
            bbox = draw.textbbox((0, 0), line, font=self._cta_font)
            text_width = bbox[2] - bbox[0]
            x = (self.SLIDE_WIDTH - text_width) // 2
            draw.text((x, cta_y), line, font=self._cta_font, fill=text_color)
            cta_y += self.CTA_FONT_SIZE + 10

        # Draw subtext below CTA
        subtext_y = cta_y + 40
        subtext_lines = self._wrap_text(subtext, self._subtext_font, max_width)[:3]

        for line in subtext_lines:
            bbox = draw.textbbox((0, 0), line, font=self._subtext_font)
            text_width = bbox[2] - bbox[0]
            x = (self.SLIDE_WIDTH - text_width) // 2
            draw.text((x, subtext_y), line, font=self._subtext_font, fill=text_color)
            subtext_y += self.SUBTEXT_FONT_SIZE + 8

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

        max_width = self.SLIDE_WIDTH - (2 * self.PADDING)
        wrapped = self._wrap_text(step_title, self._title_font, max_width)[:1]

        y = self.PADDING + 40
        for line in wrapped:
            bbox = draw.textbbox((0, 0), line, font=self._title_font)
            text_width = bbox[2] - bbox[0]
            x = (self.SLIDE_WIDTH - text_width) // 2
            draw.text((x, y), line, font=self._title_font, fill=text_color)

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
            log_warning("Leonardo AI not available, using local cover generation")
            return None

        try:
            leonardo = LeonardoGenerator()
            result = leonardo.generate_carousel_cover(
                title=title,
                content_type=content_type,
                width=1080,
                height=1350,
            )
            return result.get("image_url")
        except Exception as e:
            log_warning(f"Leonardo cover generation failed: {e}, using local fallback")
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
        """Create a CONTENT slide

        Args:
            data: Slide data with 'step_title', 'bullets', and optional 'icon_path'
            slide_number: Current slide number
            total_slides: Total number of slides

        Returns:
            PIL.Image: Generated content slide
        """
        image = self._create_base_template()

        # Add step header at top
        step_title = data.get('step_title', f'Step {slide_number - 1}')
        image = self._add_step_header(image, step_title)

        # Add bullet points
        bullets = data.get('bullets', [])
        bullet_start_y = self.PADDING + 140
        image = self._add_bullet_points(image, bullets, bullet_start_y)

        # Add optional icon
        icon_path = data.get('icon_path', '')
        if icon_path:
            image = self._add_icon(image, icon_path)

        # Add slide number
        image = self._add_slide_number(image, slide_number, total_slides)

        return image

    def _create_cta_slide(self, data: Dict, slide_number: int, total_slides: int) -> Image.Image:
        """Create a CTA (call-to-action) slide

        Args:
            data: Slide data with 'headline', 'cta_text', and 'subtext'
            slide_number: Current slide number
            total_slides: Total number of slides

        Returns:
            PIL.Image: Generated CTA slide
        """
        image = self._create_base_template()

        # Add CTA section
        image = self._add_cta_section(
            image,
            headline=data.get('headline', ''),
            cta_text=data.get('cta_text', ''),
            subtext=data.get('subtext', '')
        )

        # Add slide number
        image = self._add_slide_number(image, slide_number, total_slides)

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
