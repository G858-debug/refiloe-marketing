"""Leonardo AI image generation for Refiloe marketing content.

This module provides image generation using Leonardo AI's Phoenix model,
with support for character consistency using reference images.

Features:
- Photorealistic image generation
- Character reference support for Refiloe consistency
- Quote graphic generation for text-focused content
- Automatic content type to prompt mapping
"""

import os
import time
import json
import requests
from typing import Any, Dict, Optional, List
from datetime import datetime, timezone

from utils.logger import log_info, log_error, log_warning, log_debug


LEONARDO_API_BASE = "https://cloud.leonardo.ai/api/rest/v1"

# Leonardo model IDs
PHOENIX_MODEL_ID = "6b645e3a-d64f-4341-a6d8-7a3690fbf042"
FLUX_DEV_MODEL_ID = "b2614463-296c-462a-9586-aafdb8f00e36"  # Flux Dev - from Leonardo docs

# Default model - use Flux Dev for LoRA/Element support
DEFAULT_MODEL_ID = FLUX_DEV_MODEL_ID

# Refiloe 2.0 LoRA configuration
DEFAULT_REFILOE_LORA_ID = 169703  # User-trained Refiloe 2.0 character
DEFAULT_LORA_WEIGHT = 1.00  # Recommended strength

# Default generation settings
# Leonardo AI supported dimensions (must be divisible by 8, ideally 64)
# Using 832x1024 for approximately 4:5 portrait ratio
DEFAULT_WIDTH = 832
DEFAULT_HEIGHT = 1024

# Alternative supported dimensions for reference:
# 1024x1024 (1:1 square)
# 832x1024 (~4:5 portrait)
# 1024x832 (~5:4 landscape)
# 768x1024 (3:4 portrait)
# 1152x896 (~4:3 landscape)

DEFAULT_NUM_IMAGES = 1


def _get_valid_leonardo_dimensions(width: int, height: int) -> tuple[int, int]:
    """Adjust dimensions to Leonardo-supported values.

    Leonardo requires dimensions divisible by 8, preferably 64.
    This function rounds to nearest valid dimensions.

    Args:
        width: Requested width
        height: Requested height

    Returns:
        Tuple of (valid_width, valid_height)
    """
    # Round to nearest multiple of 64 for best results
    valid_width = round(width / 64) * 64
    valid_height = round(height / 64) * 64

    # Ensure minimum dimensions
    valid_width = max(valid_width, 512)
    valid_height = max(valid_height, 512)

    # Ensure maximum dimensions (Leonardo limit)
    valid_width = min(valid_width, 1536)
    valid_height = min(valid_height, 1536)

    return valid_width, valid_height


# Character description for Refiloe (used when no reference image available)
REFILOE_CHARACTER_DESCRIPTION = """
A confident South African woman in her early 30s with deep brown skin and warm undertones.
She has a tightly coiled natural afro at medium length with a side part and subtle copper highlights.
Dark brown almond-shaped eyes with subtle gold flecks, full well-defined eyebrows with a natural arch.
Warm, expressive smile showing upper teeth. She wears gold hoop earrings and a minimalist wrist cuff.
Upright, confident posture with relaxed shoulders.
"""

# Content type to prompt style mapping
CONTENT_TYPE_PROMPTS = {
    "workout": {
        "features_refiloe": True,
        "setting": "modern boutique gym with warm wood-paneled walls, chrome equipment, golden morning light through large windows",
        "outfit": "fitted coral athletic crop top, high-waisted burgundy leggings, delicate gold body chain",
        "pose": "confident stance, slight smile, engaging with camera",
        "mood": "energetic, motivating, professional",
    },
    "fitness": {
        "features_refiloe": True,
        "setting": "bright fitness studio with floor-to-ceiling mirrors, polished oak hardwood floors, ballet barre",
        "outfit": "electric blue racerback athletic top with mesh panel, matching sports bra, gold necklace",
        "pose": "dynamic instructor pose, welcoming gesture",
        "mood": "energetic, professional, approachable",
    },
    "professional": {
        "features_refiloe": True,
        "setting": "modern co-working space with beige linen sofa, brass floor lamp, floating wooden shelves with books",
        "outfit": "structured hot pink blazer over cream silk camisole, gold layered necklaces, statement gold drop earrings",
        "pose": "confident professional stance, warm smile",
        "mood": "sophisticated, trustworthy, approachable",
    },
    "business": {
        "features_refiloe": True,
        "setting": "executive office with mahogany desk, beige leather chair, city skyline through window",
        "outfit": "tailored emerald green power blazer with gold buttons, crisp white V-neck blouse, gold chain earrings",
        "pose": "authoritative yet approachable stance",
        "mood": "confident, professional, successful",
    },
    "motivational": {
        "features_refiloe": True,
        "setting": "bright inspiring space with large windows, morning golden light, motivational wall art in background, green plants",
        "outfit": "vibrant coral fitted athletic top, matching leggings, delicate gold layered necklaces, warm confident energy",
        "pose": "confident empowering stance, hands on hips or arms raised in victory pose, genuine radiant smile, looking at camera",
        "mood": "empowering, uplifting, energizing, you-can-do-this energy",
    },
    "educational": {
        "features_refiloe": True,
        "setting": "warm home office with light oak desk, beige chair, wooden shelves with books and succulents, fairy lights",
        "outfit": "cozy oversized mustard yellow knit cardigan over fitted white tank, delicate gold pendant necklace",
        "pose": "approachable teaching gesture, warm smile",
        "mood": "knowledgeable, friendly, helpful",
    },
    "community": {
        "features_refiloe": True,
        "setting": "trendy coffee shop with exposed cream brick, wooden communal table, Edison bulb lights, monstera plant",
        "outfit": "flowy fuchsia wrap blouse, layered gold chain necklaces, bamboo hoop earrings",
        "pose": "welcoming open gesture, genuine smile",
        "mood": "warm, inclusive, connected",
    },
    "relatable": {
        "features_refiloe": True,
        "setting": "cozy living room with plush beige sectional, textured throw pillows, knit blanket, fiddle leaf fig plant",
        "outfit": "oversized sage green hoodie slightly off shoulder, simple gold huggie earrings, messy topknot",
        "pose": "casual relaxed pose, authentic expression",
        "mood": "authentic, real, relatable",
    },
    "casual": {
        "features_refiloe": True,
        "setting": "outdoor café terrace with wrought iron bistro table, potted lavender, cream canvas umbrella, bougainvillea",
        "outfit": "vibrant yellow linen button-up shirt tied at waist, gold layered necklaces",
        "pose": "relaxed weekend vibe, natural smile",
        "mood": "carefree, happy, approachable",
    },
    "announcement": {
        "features_refiloe": True,
        "setting": "modern office or studio space with clean white walls, professional lighting, subtle brand elements",
        "outfit": "professional blazer in bold color (fuchsia or emerald), crisp blouse, statement earrings",
        "pose": "excited welcoming gesture, genuine smile, engaging with camera as if sharing good news",
        "mood": "exciting, celebratory, professional, newsworthy",
    },
    "outdoor": {
        "features_refiloe": True,
        "setting": "lush green park with mature trees, dappled sunlight, gravel jogging path, colorful flower beds",
        "outfit": "bright coral moisture-wicking tank top, sage green running vest, sporty gold smartwatch",
        "pose": "active outdoor stance, energetic expression",
        "mood": "fresh, energetic, adventurous",
    },
    "studio": {
        "features_refiloe": True,
        "setting": "bright group fitness studio with polished wood floors, wall mirrors, chrome ballet barre, motivational wall art",
        "outfit": "sleek black halter athletic crop top, high-waisted purple compression leggings, delicate gold body chain",
        "pose": "instructor ready stance, confident expression",
        "mood": "professional, energetic, inspiring",
    },
    "lifestyle": {
        "features_refiloe": True,
        "setting": "peaceful wellness corner with cream linen armchair, chunky knit throw, wooden side table with tea and candle, plants",
        "outfit": "soft lavender cashmere wrap sweater, matching loungewear pants, delicate gold pendant with gemstone",
        "pose": "calm, centered pose, serene smile",
        "mood": "balanced, peaceful, mindful",
    },
}


class LeonardoGenerationError(Exception):
    """Raised when Leonardo AI image generation fails."""


class LeonardoGenerator:
    """Generate images using Leonardo AI with character consistency."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        reference_image_id: Optional[str] = None,
    ):
        """Initialize Leonardo AI generator.

        Args:
            api_key: Leonardo AI API key. Defaults to LEONARDO_API_KEY env var.
            reference_image_id: Leonardo AI image ID for Refiloe reference.
                              Defaults to LEONARDO_REFILOE_REFERENCE_ID env var.
        """
        self.api_key = api_key or os.getenv("LEONARDO_API_KEY")
        if not self.api_key:
            raise ValueError("LEONARDO_API_KEY environment variable required")

        self.reference_image_id = reference_image_id or os.getenv("LEONARDO_REFILOE_REFERENCE_ID")
        self.model_id = os.getenv("LEONARDO_MODEL_ID", DEFAULT_MODEL_ID)

        # User-trained LoRA configuration for Refiloe character
        lora_id_str = os.getenv("LEONARDO_REFILOE_LORA_ID", str(DEFAULT_REFILOE_LORA_ID))
        self.refiloe_lora_id = int(lora_id_str) if lora_id_str else DEFAULT_REFILOE_LORA_ID
        self.lora_weight = float(os.getenv("LEONARDO_LORA_WEIGHT", str(DEFAULT_LORA_WEIGHT)))

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

        # Polling settings
        self.poll_interval = 5  # seconds
        self.poll_timeout = 120  # seconds

        model_name = "Flux Dev" if self.model_id == FLUX_DEV_MODEL_ID else "Phoenix" if self.model_id == PHOENIX_MODEL_ID else "Unknown"
        log_info(f"LeonardoGenerator initialized with model: {model_name} ({self.model_id})")
        log_info(f"Refiloe 2.0 LoRA configured: ID={self.refiloe_lora_id}, weight={self.lora_weight}")

    def generate_image(
        self,
        prompt: str,
        content_type: Optional[str] = None,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        num_images: int = DEFAULT_NUM_IMAGES,
        use_reference: bool = True,
    ) -> Dict[str, Any]:
        """Generate an image using Leonardo AI.

        Args:
            prompt: The image generation prompt.
            content_type: Optional content type for automatic prompt enhancement.
            width: Image width in pixels.
            height: Image height in pixels.
            num_images: Number of images to generate.
            use_reference: Whether to use Refiloe reference image.

        Returns:
            Dict containing:
                - image_url: URL of the generated image
                - generation_id: Leonardo generation ID
                - prompt: The prompt used
                - content_type: The content type
        """
        # Build enhanced prompt based on content type
        enhanced_prompt = self._build_prompt(prompt, content_type, use_reference)

        log_info(f"Starting Leonardo image generation for content_type: {content_type}")
        log_debug(f"Enhanced prompt: {enhanced_prompt[:200]}...")

        # Leonardo has a 1500 character limit for prompts
        MAX_PROMPT_LENGTH = 1450  # Leave some buffer
        if len(enhanced_prompt) > MAX_PROMPT_LENGTH:
            log_warning(f"Prompt too long ({len(enhanced_prompt)} chars), truncating to {MAX_PROMPT_LENGTH}")
            enhanced_prompt = enhanced_prompt[:MAX_PROMPT_LENGTH - 3] + "..."

        # Validate dimensions for Leonardo
        valid_width, valid_height = _get_valid_leonardo_dimensions(width, height)
        if valid_width != width or valid_height != height:
            log_info(f"Adjusted dimensions from {width}x{height} to {valid_width}x{valid_height} for Leonardo compatibility")

        # Build generation payload
        payload = {
            "modelId": self.model_id,
            "prompt": enhanced_prompt,
            "width": valid_width,
            "height": valid_height,
            "num_images": num_images,
            "public": False,
        }

        # Add Refiloe 2.0 user-trained Element for character consistency
        # Per Leonardo AI docs: userElements with userLoraId for user-trained LoRAs
        if use_reference and self.refiloe_lora_id and self._content_type_features_refiloe(content_type):
            payload["userElements"] = [{
                "userLoraId": self.refiloe_lora_id,
                "weight": self.lora_weight,
            }]
            log_info(f"Using Refiloe 2.0 Element (userLoraId: {self.refiloe_lora_id}) with weight {self.lora_weight}")

        # Create generation
        try:
            log_info(f"Leonardo API payload: {json.dumps(payload, indent=2)}")

            response = self.session.post(
                f"{LEONARDO_API_BASE}/generations",
                json=payload,
                timeout=30,
            )

            # Log full response for debugging
            if not response.ok:
                log_error(f"Leonardo API error status: {response.status_code}")
                log_error(f"Leonardo API error response: {response.text}")

            response.raise_for_status()
            generation_data = response.json()
            log_info(f"Leonardo API success response: {generation_data}")

        except requests.RequestException as e:
            log_error(f"Leonardo API request failed: {e}")
            # Try to get response body if available
            if hasattr(e, 'response') and e.response is not None:
                log_error(f"Leonardo error details: {e.response.text}")
            raise LeonardoGenerationError(f"Failed to start generation: {e}")

        generation_id = generation_data.get("sdGenerationJob", {}).get("generationId")
        if not generation_id:
            log_error(f"No generation ID in response: {generation_data}")
            raise LeonardoGenerationError("No generation ID returned")

        log_info(f"Generation started: {generation_id}")

        # Poll for completion
        image_url = self._poll_for_completion(generation_id)

        return {
            "image_url": image_url,
            "generation_id": generation_id,
            "prompt": enhanced_prompt,
            "content_type": content_type,
            "width": valid_width,
            "height": valid_height,
        }

    def generate_quote_graphic(
        self,
        quote_text: str,
        content_type: str = "motivational",
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> Dict[str, Any]:
        """Generate a quote graphic without Refiloe.

        Args:
            quote_text: The quote text to feature.
            content_type: Content type for styling.
            width: Image width.
            height: Image height.

        Returns:
            Dict with generated image details.
        """
        config = CONTENT_TYPE_PROMPTS.get(content_type, CONTENT_TYPE_PROMPTS["motivational"])

        prompt = f"""
        Professional social media quote graphic design.
        Background: {config.get('background', 'elegant gradient from deep purple to dark blue')}.

        The image should be a beautiful background design suitable for overlaying text.
        Style: Modern, clean, minimalist, professional.
        No text in the image - just the background design.
        High quality, social media ready, Instagram aesthetic.

        Mood: Inspiring, motivational, premium feel.
        Colors: Warm earthy tones with beige and gold accents.
        """

        return self.generate_image(
            prompt=prompt,
            content_type=content_type,
            width=width,
            height=height,
            use_reference=False,
        )

    def generate_carousel_cover(
        self,
        title: str,
        content_type: str = "educational",
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> Dict[str, Any]:
        """Generate a carousel cover slide with Refiloe.

        Args:
            title: The carousel title/topic.
            content_type: Content type for styling.
            width: Image width.
            height: Image height.

        Returns:
            Dict with generated image details.
        """
        config = CONTENT_TYPE_PROMPTS.get(content_type, CONTENT_TYPE_PROMPTS["educational"])

        if config.get("features_refiloe", True):
            prompt = f"""
            Professional social media carousel cover image.

            {REFILOE_CHARACTER_DESCRIPTION}

            Setting: {config.get('setting', 'modern professional space')}.
            Outfit: {config.get('outfit', 'professional attire')}.
            Pose: {config.get('pose', 'confident, engaging with camera')}.

            She appears ready to share valuable information about: {title}

            Style: High-quality photography, professional lighting, Instagram-ready.
            Mood: {config.get('mood', 'professional and approachable')}.

            Leave space at top or bottom for text overlay.
            Warm color palette with beige and earthy tones.
            """
        else:
            prompt = f"""
            Professional social media carousel cover design.
            Topic: {title}

            Modern, clean design suitable for educational content.
            Style: Premium, professional, engaging.
            Colors: Warm earthy tones with beige, coral, and gold accents.

            Leave prominent space for title text overlay.
            No text in the image itself.
            """

        return self.generate_image(
            prompt=prompt,
            content_type=content_type,
            width=width,
            height=height,
            use_reference=config.get("features_refiloe", True),
        )

    def _build_prompt(
        self,
        base_prompt: str,
        content_type: Optional[str],
        use_reference: bool,
    ) -> str:
        """Build an enhanced prompt based on content type.

        Args:
            base_prompt: The base prompt provided.
            content_type: Content type for enhancement.
            use_reference: Whether using reference image.

        Returns:
            Enhanced prompt string.
        """
        if not content_type or content_type not in CONTENT_TYPE_PROMPTS:
            return base_prompt

        config = CONTENT_TYPE_PROMPTS[content_type]

        # If it's a quote graphic style, return base prompt
        if config.get("style") == "quote_graphic":
            return base_prompt

        # Build character prompt
        if config.get("features_refiloe", True):
            enhanced = f"""
            Professional social media photo featuring Refiloe.

            {REFILOE_CHARACTER_DESCRIPTION}

            Setting: {config.get('setting', 'professional setting')}.
            Outfit: {config.get('outfit', 'professional attire')}.
            Pose: {config.get('pose', 'confident stance')}.
            Mood: {config.get('mood', 'professional and approachable')}.

            Additional context: {base_prompt}

            Style: High-quality professional photography, natural lighting,
            Instagram-ready, warm color palette with beige and earthy tones.
            4:5 portrait aspect ratio optimized for mobile viewing.
            """
            return enhanced

        return base_prompt

    def _content_type_features_refiloe(self, content_type: Optional[str]) -> bool:
        """Check if content type should feature Refiloe.

        Args:
            content_type: The content type to check.

        Returns:
            True if content type should feature Refiloe.
        """
        if not content_type:
            return True  # Default to featuring Refiloe

        config = CONTENT_TYPE_PROMPTS.get(content_type, {})
        return config.get("features_refiloe", True)

    def _poll_for_completion(self, generation_id: str) -> str:
        """Poll Leonardo API until generation completes.

        Args:
            generation_id: The generation ID to poll.

        Returns:
            URL of the generated image.

        Raises:
            LeonardoGenerationError: If generation fails or times out.
        """
        start_time = time.time()

        while time.time() - start_time < self.poll_timeout:
            try:
                response = self.session.get(
                    f"{LEONARDO_API_BASE}/generations/{generation_id}",
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                log_warning(f"Poll request failed: {e}, retrying...")
                time.sleep(self.poll_interval)
                continue

            generation = data.get("generations_by_pk", {})
            status = generation.get("status")

            if status == "COMPLETE":
                images = generation.get("generated_images", [])
                if images:
                    image_url = images[0].get("url")
                    log_info(f"Generation complete: {image_url}")
                    return image_url
                else:
                    raise LeonardoGenerationError("Generation complete but no images returned")

            elif status == "FAILED":
                raise LeonardoGenerationError(f"Generation failed: {generation}")

            log_debug(f"Generation status: {status}, waiting...")
            time.sleep(self.poll_interval)

        raise LeonardoGenerationError(f"Generation timed out after {self.poll_timeout}s")


# Convenience function for quick generation
def generate_content_image(
    content_type: str,
    caption: str = "",
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> Dict[str, Any]:
    """Generate an image for content based on content type.

    Args:
        content_type: The content type (motivational, educational, etc.)
        caption: Optional caption text for context.
        width: Image width.
        height: Image height.

    Returns:
        Dict with generated image details.
    """
    generator = LeonardoGenerator()

    config = CONTENT_TYPE_PROMPTS.get(content_type, {})

    if config.get("style") == "quote_graphic":
        return generator.generate_quote_graphic(
            quote_text=caption,
            content_type=content_type,
            width=width,
            height=height,
        )
    else:
        return generator.generate_image(
            prompt=caption,
            content_type=content_type,
            width=width,
            height=height,
        )
