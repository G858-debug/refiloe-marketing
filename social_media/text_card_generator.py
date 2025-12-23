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

    # Template URL
    TEMPLATE_URL = "https://mqemiteirxwscxtamdtj.supabase.co/storage/v1/object/public/media/brand-assets/text-card-template.png"

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
    CONTENT_FONT_SIZE = 54  # Main quote/tip/content text
    ATTRIBUTION_FONT_SIZE = 34  # Attribution and subtitle text
    BULLET_FONT_SIZE = 48  # For educational bullet points

    def __init__(self, config_path: str = 'social_media/config.yaml'):
        """Initialize with config and setup output directory.

        Args:
            config_path: Path to config.yaml file
        """
        self.config_path = config_path
        self.output_dir = Path("/tmp/text_cards")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Fetch and cache template
        log_info("Fetching base template from Supabase...")
        self.base_template = self._fetch_image(self.TEMPLATE_URL)

        if self.base_template:
            log_info(f"Base template loaded successfully ({self.base_template.size})")
        else:
            log_warning("Base template failed to load - will use fallback background")

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
            img = Image.open(BytesIO(response.content)).convert('RGBA')
            # Resize template to standard output dimensions
            img = img.resize((1080, 1350), Image.LANCZOS)
            return img
        except Exception as e:
            log_error(f"Failed to fetch image from {url}: {e}")
            return None

    def generate_text_card(self, content: Dict[str, Any], content_type: str) -> str:
        """Generate text card image and return file path.

        Args:
            content: Dict with type-specific keys:
                - quote: {'quote': str, 'attribution': str}
                - tip: {'header': str, 'tip': str, 'subtitle': str}
                - educational: {'title': str, 'points': List[str]}
                - motivation: {'statement': str}
                - comparison: {'topic': str, 'dont': str, 'do': str, 'why': str}
            content_type: One of 'quote', 'tip', 'educational', 'motivation', 'comparison'

        Returns:
            str: Path to generated image file
        """
        content_type = content_type.lower()

        log_info(f"Generating {content_type} text card with provided content")

        try:
            # Validate content type
            valid_types = ['quote', 'tip', 'educational', 'motivation', 'comparison']
            if content_type not in valid_types:
                log_error(f"Unknown content type: {content_type}")
                raise ValueError(f"Unknown content type: {content_type}. Must be one of: {', '.join(valid_types)}")

            # Create unified layout for all types using the provided content
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

    def _get_display_text(self, content: Dict[str, Any], content_type: str) -> Tuple[str, Optional[str]]:
        """Extract display text from content based on content type.

        Args:
            content: Content dictionary
            content_type: Type of content (quote, tip, educational, motivation)

        Returns:
            Tuple[str, Optional[str]]: (main_text, subtitle_text)
        """
        if content_type == 'quote':
            main_text = content.get('quote', '')
            subtitle = content.get('attribution', '')
            # Format attribution with em dash for quotes
            subtitle_text = f"— {subtitle}" if subtitle else None
        elif content_type == 'tip':
            main_text = content.get('tip', '')
            subtitle_text = content.get('subtitle', '')
        elif content_type == 'educational':
            main_text = content.get('title', '')
            # Educational content will handle points separately
            subtitle_text = None
        elif content_type == 'motivation':
            main_text = content.get('statement', '')
            subtitle_text = None
        elif content_type == 'comparison':
            # Comparison uses custom layout, return empty for standard flow
            main_text = ''
            subtitle_text = None
        else:
            main_text = ''
            subtitle_text = None

        return main_text, subtitle_text

    def _draw_centered_text(self, draw: ImageDraw.Draw, main_text: str, subtitle_text: Optional[str], content_area: Dict[str, int], content_type: str, content: Dict[str, Any]) -> None:
        """Draw centered text with word wrapping in content area.

        Args:
            draw: ImageDraw object
            main_text: Main content text
            subtitle_text: Optional subtitle/attribution text
            content_area: Dict with 'left', 'right', 'top', 'bottom' boundaries
            content_type: Type of content (for special handling like educational)
            content: Full content dict (for educational points)
        """
        # Handle comparison type with custom layout
        if content_type == 'comparison':
            self._draw_comparison_layout(draw, content, content_area)
            return

        # Load fonts
        main_font = self._load_font(bold=True, size=self.CONTENT_FONT_SIZE)
        subtitle_font = self._load_font(bold=False, size=self.ATTRIBUTION_FONT_SIZE)

        # Calculate content area width and centering
        content_width = content_area['right'] - content_area['left']
        center_x = content_area['center_x']

        # Max width for text wrapping (with margins for better centering)
        max_text_width = 780  # Content area width with padding

        # Wrap main text
        wrapped_main = self._wrap_text(main_text, main_font, max_text_width)

        # Calculate line heights
        main_line_height = int(self.CONTENT_FONT_SIZE * 1.3)  # 30% extra for line spacing
        subtitle_line_height = int(self.ATTRIBUTION_FONT_SIZE * 1.3)

        # Calculate total height needed
        total_height = len(wrapped_main) * main_line_height

        # Add subtitle height if present
        if subtitle_text:
            total_height += 40 + subtitle_line_height  # 40px gap between main and subtitle

        # For educational content, add bullet points
        if content_type == 'educational':
            points = content.get('points', [])
            bullet_font = self._load_font(bold=False, size=self.BULLET_FONT_SIZE)
            bullet_line_height = int(self.BULLET_FONT_SIZE * 1.2)

            # Add space for bullets (estimate 2 lines per bullet max, plus spacing)
            total_height += 60  # Gap before bullets
            for point in points[:4]:  # Limit to 4 points
                wrapped_point = self._wrap_text(point, bullet_font, max_text_width)
                num_lines = min(len(wrapped_point), 2)  # Max 2 lines per bullet
                total_height += num_lines * bullet_line_height + 20  # 20px between bullets

        # Calculate starting Y position to center vertically
        content_height = content_area['bottom'] - content_area['top']
        current_y = content_area['top'] + (content_height - total_height) // 2

        # Draw main text (centered horizontally)
        for line in wrapped_main:
            bbox = draw.textbbox((0, 0), line, font=main_font)
            line_width = bbox[2] - bbox[0]
            text_x = center_x - (line_width // 2)
            draw.text((text_x, current_y), line, font=main_font, fill=(255, 255, 255))
            current_y += main_line_height

        # Draw subtitle if present
        if subtitle_text:
            current_y += 40  # Gap between main text and subtitle
            bbox = draw.textbbox((0, 0), subtitle_text, font=subtitle_font)
            subtitle_width = bbox[2] - bbox[0]
            subtitle_x = center_x - (subtitle_width // 2)
            draw.text((subtitle_x, current_y), subtitle_text, font=subtitle_font, fill=(255, 255, 255))
            current_y += subtitle_line_height

        # Draw educational bullet points if applicable
        if content_type == 'educational':
            points = content.get('points', [])
            bullet_font = self._load_font(bold=False, size=self.BULLET_FONT_SIZE)
            bullet_line_height = int(self.BULLET_FONT_SIZE * 1.2)

            current_y += 60  # Gap before bullets

            for point in points[:4]:  # Limit to 4 points
                # Wrap the bullet point text
                max_bullet_width = 780  # Content width with margin
                wrapped_point = self._wrap_text(point, bullet_font, max_bullet_width)

                # For each line in the bullet point, center it horizontally
                for i, point_line in enumerate(wrapped_point[:2]):  # Max 2 lines per bullet
                    # Calculate text width
                    bbox = draw.textbbox((0, 0), point_line, font=bullet_font)
                    line_width = bbox[2] - bbox[0]

                    # Draw bullet circle on first line only
                    if i == 0:
                        bullet_radius = 6
                        bullet_spacing = 15  # Space between bullet and text
                        # Position bullet to the left of centered text
                        bullet_x = center_x - (line_width // 2) - bullet_spacing - bullet_radius
                        draw.ellipse(
                            [(bullet_x - bullet_radius, current_y + 20 - bullet_radius),
                             (bullet_x + bullet_radius, current_y + 20 + bullet_radius)],
                            fill=(255, 255, 255)
                        )

                    # Center the text horizontally
                    text_x = center_x - (line_width // 2)
                    draw.text((text_x, current_y), point_line,
                             font=bullet_font, fill=(255, 255, 255))
                    current_y += bullet_line_height

                current_y += 20  # Space between bullets

    def _draw_comparison_layout(
        self,
        draw: ImageDraw.Draw,
        content: Dict[str, Any],
        content_area: Dict[str, int]
    ) -> None:
        """Draw comparison (Do This, Not That) layout.

        Layout structure (within 880x770 content area):
        - Topic header (small, top)
        - DON'T section with ❌ icon
        - DO section with ✅ icon
        - WHY section at bottom

        Args:
            draw: ImageDraw object
            content: Content dict with 'topic', 'dont', 'do', 'why' keys
            content_area: Dict with layout boundaries
        """
        # Extract content
        topic = content.get('topic', 'COMPARISON')
        dont_text = content.get('dont', '')
        do_text = content.get('do', '')
        why_text = content.get('why', '')

        # Layout constants - designed to fit comfortably in content area
        center_x = content_area['center_x']
        content_left = content_area['left'] + 40  # Extra padding for comfort
        content_right = content_area['right'] - 40
        max_text_width = content_right - content_left - 80  # 700px for text

        # Font sizes - slightly smaller to ensure fit
        topic_font_size = 28
        label_font_size = 32
        content_font_size = 36
        why_font_size = 28

        # Load fonts
        topic_font = self._load_font(bold=True, size=topic_font_size)
        label_font = self._load_font(bold=True, size=label_font_size)
        content_font = self._load_font(bold=False, size=content_font_size)
        why_label_font = self._load_font(bold=True, size=why_font_size)
        why_font = self._load_font(bold=False, size=why_font_size)

        # Colors
        white = (255, 255, 255)
        red_tint = (255, 120, 120)  # Soft red for DON'T
        green_tint = (120, 255, 150)  # Soft green for DO
        muted_white = (200, 200, 200)  # For WHY section

        # Calculate line heights
        topic_line_height = int(topic_font_size * 1.3)
        label_line_height = int(label_font_size * 1.4)
        content_line_height = int(content_font_size * 1.35)
        why_line_height = int(why_font_size * 1.3)

        # Calculate vertical spacing
        section_gap = 45  # Gap between DON'T and DO sections
        why_gap = 40  # Gap before WHY section

        # Wrap text for each section
        wrapped_dont = self._wrap_text(dont_text, content_font, max_text_width)
        wrapped_do = self._wrap_text(do_text, content_font, max_text_width)
        wrapped_why = self._wrap_text(why_text, why_font, max_text_width)

        # Limit lines to prevent overflow
        wrapped_dont = wrapped_dont[:3]  # Max 3 lines for DON'T
        wrapped_do = wrapped_do[:3]  # Max 3 lines for DO
        wrapped_why = wrapped_why[:2]  # Max 2 lines for WHY

        # Calculate total height needed
        topic_height = topic_line_height + 25  # Topic + gap
        dont_height = label_line_height + (len(wrapped_dont) * content_line_height) + 15
        do_height = label_line_height + (len(wrapped_do) * content_line_height) + 15
        why_height = why_line_height + (len(wrapped_why) * why_line_height)

        total_height = topic_height + dont_height + section_gap + do_height + why_gap + why_height

        # Calculate starting Y to center vertically
        available_height = content_area['bottom'] - content_area['top']
        start_y = content_area['top'] + (available_height - total_height) // 2
        current_y = start_y

        # Draw topic header (small, centered, uppercase)
        topic_upper = topic.upper()
        bbox = draw.textbbox((0, 0), topic_upper, font=topic_font)
        topic_width = bbox[2] - bbox[0]
        topic_x = center_x - (topic_width // 2)
        draw.text((topic_x, current_y), topic_upper, font=topic_font, fill=muted_white)
        current_y += topic_height

        # Draw DON'T section
        # Label with emoji
        dont_label = "❌  DON'T"
        bbox = draw.textbbox((0, 0), dont_label, font=label_font)
        label_width = bbox[2] - bbox[0]
        label_x = center_x - (label_width // 2)
        draw.text((label_x, current_y), dont_label, font=label_font, fill=red_tint)
        current_y += label_line_height

        # DON'T content text (centered)
        for line in wrapped_dont:
            bbox = draw.textbbox((0, 0), line, font=content_font)
            line_width = bbox[2] - bbox[0]
            text_x = center_x - (line_width // 2)
            draw.text((text_x, current_y), line, font=content_font, fill=white)
            current_y += content_line_height

        current_y += section_gap

        # Draw DO section
        # Label with emoji
        do_label = "✅  DO"
        bbox = draw.textbbox((0, 0), do_label, font=label_font)
        label_width = bbox[2] - bbox[0]
        label_x = center_x - (label_width // 2)
        draw.text((label_x, current_y), do_label, font=label_font, fill=green_tint)
        current_y += label_line_height

        # DO content text (centered)
        for line in wrapped_do:
            bbox = draw.textbbox((0, 0), line, font=content_font)
            line_width = bbox[2] - bbox[0]
            text_x = center_x - (line_width // 2)
            draw.text((text_x, current_y), line, font=content_font, fill=white)
            current_y += content_line_height

        current_y += why_gap

        # Draw WHY section
        # Draw horizontal divider line
        divider_width = 200
        divider_y = current_y - 15
        draw.line(
            [(center_x - divider_width // 2, divider_y),
             (center_x + divider_width // 2, divider_y)],
            fill=muted_white,
            width=1
        )

        # WHY label
        why_label_text = "WHY"
        bbox = draw.textbbox((0, 0), why_label_text, font=why_label_font)
        label_width = bbox[2] - bbox[0]
        label_x = center_x - (label_width // 2)
        draw.text((label_x, current_y), why_label_text, font=why_label_font, fill=muted_white)
        current_y += why_line_height

        # WHY content (centered, muted)
        for line in wrapped_why:
            bbox = draw.textbbox((0, 0), line, font=why_font)
            line_width = bbox[2] - bbox[0]
            text_x = center_x - (line_width // 2)
            draw.text((text_x, current_y), line, font=why_font, fill=muted_white)
            current_y += why_line_height

    def _create_unified_layout(self, content_type: str, content: Dict[str, Any]) -> Image.Image:
        """Create text card using pre-designed template.

        The template already contains:
        - Avatar image (circular, centered)
        - "Refiloe" name
        - "Personal assistant | trainer" tagline
        - Decorative frame and styling
        - "REFILOE" watermark at bottom

        This method only needs to overlay the content text.

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

        # Define content area (inside frame, below template header)
        # The template has avatar/name/tagline at top, so content starts lower
        content_area = {
            'left': 100,
            'right': 980,
            'top': 380,      # Below avatar/name section
            'bottom': 1150,  # Above bottom frame
            'center_x': 540  # Horizontal center (1080/2)
        }

        # Get text to display based on content type
        main_text, subtitle_text = self._get_display_text(content, content_type)

        # Draw centered text
        self._draw_centered_text(draw, main_text, subtitle_text, content_area, content_type, content)

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
