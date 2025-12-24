"""Leonardo AI image generation for Refiloe marketing content.

This module provides image generation using Leonardo AI's Nano Banana Pro (Gemini Image 2),
with support for character consistency using reference images.

Features:
- Photorealistic image generation with Nano Banana Pro
- Character reference support for Refiloe consistency via image references
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


LEONARDO_API_BASE = "https://cloud.leonardo.ai/api/rest/v2"

# Default model - use Nano Banana Pro (Gemini Image 2)
DEFAULT_MODEL_ID = "gemini-image-2"

# Default generation settings
# Nano Banana Pro requires specific supported dimensions
# Using 928x1152 for 4:5 portrait ratio (perfect for Instagram/social media)
# These are the closest valid Nano Banana Pro dimensions to the 4:5 aspect ratio
DEFAULT_WIDTH = 928
DEFAULT_HEIGHT = 1152

# Alternative supported Nano Banana Pro dimensions for reference:
# 1024x1024 (1:1 square)
# 928x1152 (4:5 portrait) - recommended for social media
# 1152x928 (~5:4 landscape)
# 768x1024 (3:4 portrait)
# 1152x896 (~4:3 landscape)

DEFAULT_NUM_IMAGES = 1

# Fixed seed for consistent image generation
LEONARDO_FIXED_SEED = 2114384218


def _get_valid_leonardo_dimensions(width: int, height: int) -> tuple[int, int]:
    """Adjust dimensions to Nano Banana Pro supported values.

    Nano Banana Pro only accepts specific dimension values.
    This function finds the closest valid dimensions.

    Args:
        width: Requested width
        height: Requested height

    Returns:
        Tuple of (valid_width, valid_height)
    """
    # Nano Banana Pro specific supported dimensions (from Leonardo documentation)
    VALID_WIDTHS = [768, 848, 896, 928, 1024, 1152, 1200, 1264, 1376, 1536, 1584, 1696, 1792, 1856]
    VALID_HEIGHTS = [672, 768, 848, 896, 928, 1024, 1152, 1200, 1264, 1344, 1376, 1536, 1696, 1792, 1856]

    # Find closest valid width
    valid_width = min(VALID_WIDTHS, key=lambda x: abs(x - width))

    # Find closest valid height
    valid_height = min(VALID_HEIGHTS, key=lambda x: abs(x - height))

    return valid_width, valid_height


# Refiloe character description for consistent image generation
REFILOE_CHARACTER_DESCRIPTION = """
If the character is wearing a sports top, it will have the word REFILOE in small font, just the same as image 1
Face Consistency: Keep the person's facial features and braided hair exactly the same as Image 1, but
- very very large breasts
- very large butt
- thick thighs
"""

# Base character description - appended to all Refiloe generations
REFILOE_BASE_DESCRIPTION = """

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
    """Generate images using Leonardo AI Nano Banana Pro with character consistency via reference images."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        supabase_client = None,
    ):
        """Initialize Leonardo AI generator.

        Args:
            api_key: Leonardo AI API key. Defaults to LEONARDO_API_KEY env var.
            supabase_client: Optional Supabase client for reference image management.
        """
        self.api_key = api_key or os.getenv("LEONARDO_API_KEY")
        if not self.api_key:
            raise ValueError("LEONARDO_API_KEY environment variable required")

        self.model_id = os.getenv("LEONARDO_MODEL_ID", DEFAULT_MODEL_ID)
        self.supabase_client = supabase_client

        # Initialize reference manager if supabase client provided
        self.reference_manager = None
        if supabase_client:
            from social_media.leonardo_reference_manager import LeonardoReferenceManager
            self.reference_manager = LeonardoReferenceManager(supabase_client, self.api_key)
            log_info("Leonardo reference manager initialized")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

        # Polling settings
        self.poll_interval = 5  # seconds
        self.poll_timeout = 120  # seconds

        log_info(f"LeonardoGenerator initialized with model: {self.model_id}")

    def generate_image(
        self,
        prompt: str,
        content_type: Optional[str] = None,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        num_images: int = DEFAULT_NUM_IMAGES,
        use_reference: bool = True,
    ) -> Dict[str, Any]:
        """Generate an image using Leonardo AI Nano Banana Pro.

        Args:
            prompt: The image generation prompt.
            content_type: Optional content type for automatic prompt enhancement.
            width: Image width in pixels.
            height: Image height in pixels.
            num_images: Number of images to generate.
            use_reference: Whether to use Refiloe reference images.

        Returns:
            Dict containing:
                - image_url: URL of the generated image
                - generation_id: Leonardo generation ID
                - prompt: The prompt used
                - content_type: The content type
        """
        # Build enhanced prompt based on content type
        enhanced_prompt = self._build_prompt(prompt, content_type, use_reference)

        log_info(f"Starting Nano Banana Pro image generation for content_type: {content_type}")
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

        # Build V2 API payload for Nano Banana Pro
        log_info(f"Using fixed seed: {LEONARDO_FIXED_SEED}")
        payload = {
            "model": self.model_id,
            "parameters": {
                "width": valid_width,
                "height": valid_height,
                "prompt": enhanced_prompt,
                "quantity": num_images,
                "prompt_enhance": "OFF",
                "seed": LEONARDO_FIXED_SEED,
            },
            "public": False
        }

        # Add reference image for character consistency
        config = CONTENT_TYPE_PROMPTS.get(content_type, {})
        if use_reference and config.get("features_refiloe", True):
            reference_id = None

            if self.reference_manager:
                reference_id = self.reference_manager.get_leonardo_id()

            if reference_id:
                payload["parameters"]["guidances"] = {
                    "image_reference": [
                        {
                            "image": {
                                "id": reference_id,
                                "type": "UPLOADED"
                            },
                            "strength": "MID"
                        }
                    ]
                }
                log_info(f"Using reference image: {reference_id}")
            else:
                log_warning("No reference image available - generating without character reference")

        # Create generation
        try:
            log_info(f"Leonardo V2 API payload: {json.dumps(payload, indent=2)}")

            response = self.session.post(
                f"{LEONARDO_API_BASE}/generations",
                json=payload,
                timeout=30,
            )

            # Log full response for debugging
            if not response.ok:
                log_error(f"Leonardo V2 API error status: {response.status_code}")
                log_error(f"Leonardo V2 API error response: {response.text}")

            response.raise_for_status()
            generation_data = response.json()
            log_info(f"Leonardo V2 API success response: {generation_data}")

            # Handle case where API returns a list instead of dict (error response)
            if isinstance(generation_data, list):
                log_error(f"Leonardo V2 API returned list response: {generation_data}")
                # Extract error information from the list if available
                if generation_data and isinstance(generation_data[0], dict):
                    error_msg = generation_data[0].get("message", "Unknown error")
                    error_code = generation_data[0].get("code", "N/A")
                    raise LeonardoGenerationError(f"API error [{error_code}]: {error_msg}")
                else:
                    raise LeonardoGenerationError(f"API returned unexpected list response: {generation_data}")

        except requests.RequestException as e:
            log_error(f"Leonardo V2 API request failed: {e}")
            # Try to get response body if available
            if hasattr(e, 'response') and e.response is not None:
                log_error(f"Leonardo error details: {e.response.text}")
            raise LeonardoGenerationError(f"Failed to start generation: {e}")

        # V2 API returns generation ID in nested structure
        generation_id = generation_data.get("generate", {}).get("generationId")
        if not generation_id:
            log_error(f"Missing 'generate.generationId' in V2 response. Full response: {generation_data}")
            raise LeonardoGenerationError("No generation ID found in response - expected 'generate.generationId' field")

        log_info(f"Generation started: {generation_id}")

        # Poll for completion
        try:
            image_url = self._poll_for_completion(generation_id)
        except LeonardoGenerationError as e:
            # Check if we used references and should retry without them
            if use_reference and "guidances" in payload.get("parameters", {}):
                log_warning(f"⚠️ Generation failed with reference images: {e}")
                log_warning("⚠️ Retrying WITHOUT reference images...")

                # Invalidate the cached reference ID since it might be bad
                if self.reference_manager:
                    self.reference_manager.invalidate_cached_id()

                # Remove guidances and retry
                del payload["parameters"]["guidances"]

                try:
                    retry_response = self.session.post(
                        f"{LEONARDO_API_BASE}/generations",
                        json=payload,
                        timeout=30,
                    )
                    retry_response.raise_for_status()
                    retry_data = retry_response.json()

                    retry_generation_id = retry_data.get("generate", {}).get("generationId")
                    if not retry_generation_id:
                        raise LeonardoGenerationError("Retry failed - no generation ID")

                    log_info(f"Retry generation started: {retry_generation_id}")
                    image_url = self._poll_for_completion(retry_generation_id)
                    log_info(f"✅ Retry successful (without references): {image_url}")

                except Exception as retry_error:
                    log_error(f"❌ Retry without references also failed: {retry_error}")
                    raise LeonardoGenerationError(f"Generation failed even without references: {retry_error}")
            else:
                # No references were used, just re-raise the original error
                raise

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
            {REFILOE_BASE_DESCRIPTION}

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
            {REFILOE_BASE_DESCRIPTION}

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


    def _poll_for_completion(self, generation_id: str) -> str:
        """Poll Leonardo V1 API until generation completes.

        Note: V1 endpoint is used for polling even when using V2 for generation.
        The V2 API doesn't have a generations status endpoint.

        Args:
            generation_id: The generation ID to poll.

        Returns:
            URL of the generated image.

        Raises:
            LeonardoGenerationError: If generation fails or times out.
        """
        start_time = time.time()
        # Use V1 endpoint for polling (V2 doesn't have a generations status endpoint)
        poll_url = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"

        while time.time() - start_time < self.poll_timeout:
            try:
                response = self.session.get(
                    poll_url,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                log_warning(f"Poll request failed: {e}, retrying...")
                time.sleep(self.poll_interval)
                continue

            # V1 API response structure: {"generations_by_pk": {"generated_images": [...], "status": "..."}}
            generation_data = data.get("generations_by_pk", {})
            status = generation_data.get("status")

            if status == "COMPLETE":
                images = generation_data.get("generated_images", [])
                if images:
                    image_url = images[0].get("url")
                    log_info(f"Generation complete: {image_url}")
                    return image_url
                else:
                    raise LeonardoGenerationError("Generation complete but no images returned")

            elif status == "FAILED":
                # Extract more details about why it failed
                gen_data = data.get("generations_by_pk", {})
                prompt_mods = gen_data.get("prompt_moderations", [])

                failure_info = {
                    "status": status,
                    "model": gen_data.get("sdVersion"),
                    "prompt_moderations": prompt_mods,
                }

                if prompt_mods:
                    log_error(f"Content moderation triggered: {prompt_mods}")

                raise LeonardoGenerationError(f"Generation FAILED: {failure_info}")

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
