"""Avatar mapping configuration and selection utilities.

This module provides a comprehensive system for selecting appropriate avatars
and looks (outfits/environments) for Refiloe, an AI fitness assistant targeting
South African personal trainers.

Avatar Selection System
-----------------------
The system uses the PHOTO_AVATAR_REGISTRY to map content types to specific
HeyGen photo avatar IDs. Each content type has an associated avatar that
provides the appropriate visual style for the content.

Look Selection System
---------------------
The look selection system maps content types to appropriate visual styles
(outfits and environments). Looks define what Refiloe wears and where
she appears, making content more contextually appropriate.

Content Type Detection
----------------------
Content types are detected via:
- Explicit `content_type` parameter
- Keyword matching in content text using CONTENT_KEYWORDS and LOOK_KEYWORDS

Supported Content Types
-----------------------
- educational: Tips, tutorials, how-to guides
- motivational: Inspiring transformation stories, goal-setting
- relatable: Real struggles, authentic moments
- professional: Business strategies, client acquisition
- community: Trainer networking, community building
- fitness: Workouts, exercises, technique demonstrations
- announcement: News, updates, launches
- casual: Weekend vibes, relaxed content
- workout: Gym sessions, active training
- business: Professional/corporate content
- lifestyle: Daily life, wellness content

Usage
-----
>>> from social_media.config.avatar_mapping import (
...     get_photo_avatar_for_content,
...     select_dynamic_look,
...     get_avatar_and_look_for_content,
... )
>>> avatar_id = get_photo_avatar_for_content("Check out these workout tips!")
>>> look_info = select_dynamic_look("Transform your body with this workout!")
>>> avatar_id, look_info = get_avatar_and_look_for_content("Hit the gym today!")
"""

from __future__ import annotations

from typing import Optional, TypedDict

from utils.logger import log_debug, log_info, log_warning


class LookInfo(TypedDict, total=False):
    """Type definition for look selection return value.

    Attributes:
        look_id: Database ID of the look (if exists in database).
        look_description: Human-readable description of the look for generation.
        content_type: The detected or provided content type.
        environment: The setting/background for the look.
        outfit: Description of the outfit/attire.
        photo_avatar_id: HeyGen photo avatar ID for this look.
    """

    look_id: Optional[str]
    look_description: str
    content_type: str
    environment: str
    outfit: str
    photo_avatar_id: Optional[str]


PHOTO_AVATAR_REGISTRY = {
    "workout": "96c419d3058444069ab8e28308fdc834",
    "fitness": "291df9103e744984be41715e649ae8e6",
    "professional": "64a1ca313daf488698bebb282aa87dae",
    "business": "331e5ac30c914d5abeb2853be17a8532",
    "motivational": "d0c9ad8674ef49b79f618dd5303e50df",
    "educational": "55bdbaaa7ded40458bfc0e498ff24ae6",
    "community": "6a7f86c8c60544d497ae63695af00425",
    "relatable": "b6bb73219ff54f5eb2934b3047bf028f",
    "casual": "a33ab8bbeff5499a96ae613e5497247c",
    "announcement": "e4fc74c588ba45ec9eb49020bd95417d",
    "outdoor": "79938b6165b649b9b724d1af99a3b4b5",
    "studio": "4a5842d1f4de4d0ab4d0cb832b71a1d3",
    "lifestyle": "4c621fd3eae84def9dfcc5f25bd83c93",
}

DEFAULT_PHOTO_AVATAR_ID = "55bdbaaa7ded40458bfc0e498ff24ae6"  # educational as default


CONTENT_KEYWORDS = {
    "educational": ["tips", "how to", "guide", "learn", "tutorial"],
    "motivational": ["transform", "success", "achieve", "goals", "inspire"],
    "relatable": ["struggle", "reality", "truth", "relate", "understand"],
    "professional": ["business", "revenue", "clients", "growth", "strategy"],
    "community": ["together", "community", "trainer", "share", "connect"],
    "fitness": ["workout", "exercise", "training", "form", "technique"],
    "announcement": ["update", "important", "announce", "news", "launch"],
    "casual": ["weekend", "friday", "relax", "fun", "enjoy"],
}


# Extended keywords for look-specific content detection
LOOK_KEYWORDS = {
    "workout": [
        "gym",
        "sweat",
        "reps",
        "sets",
        "weights",
        "cardio",
        "hiit",
        "circuit",
        "strength",
        "lift",
    ],
    "business": [
        "revenue",
        "pricing",
        "packages",
        "marketing",
        "branding",
        "sales",
        "profit",
        "investment",
    ],
    "lifestyle": [
        "morning routine",
        "daily",
        "wellness",
        "self-care",
        "balance",
        "healthy eating",
        "meal prep",
    ],
    "outdoor": [
        "outdoor",
        "park",
        "nature",
        "sunshine",
        "fresh air",
        "bootcamp",
        "trail",
    ],
    "studio": [
        "studio",
        "class",
        "group fitness",
        "pilates",
        "yoga",
        "spin",
        "dance",
    ],
}


# Maps content types to specific look configurations for Refiloe.
# Each look defines the outfit and environment appropriate for the content.
CONTENT_TO_LOOK: dict[str, dict[str, str]] = {
    # Fitness and workout content - athletic/gym looks
    "workout": {
        "look_description": "Athletic gym look with sports bra and leggings",
        "outfit": "Black sports bra, high-waisted purple leggings, white trainers",
        "environment": "Modern gym with equipment in background",
    },
    "fitness": {
        "look_description": "Dynamic fitness instructor look",
        "outfit": "Fitted tank top, compression shorts, cross-training shoes",
        "environment": "Bright fitness studio with mirrors",
    },
    # Professional and business content
    "professional": {
        "look_description": "Smart business casual for professional settings",
        "outfit": "Fitted blazer over athletic top, smart trousers",
        "environment": "Modern office or co-working space",
    },
    "business": {
        "look_description": "Corporate professional look",
        "outfit": "Tailored blazer, white blouse, fitted slacks",
        "environment": "Professional office with neutral background",
    },
    # Motivational and inspiring content
    "motivational": {
        "look_description": "Confident, energetic athleisure look",
        "outfit": "Bold coloured matching set, statement sneakers",
        "environment": "Inspirational backdrop with city skyline or open space",
    },
    # Educational and tutorial content
    "educational": {
        "look_description": "Approachable instructor look",
        "outfit": "Comfortable branded hoodie, joggers",
        "environment": "Clean, well-lit studio or home gym setup",
    },
    # Community and connection content
    "community": {
        "look_description": "Friendly, relatable casual look",
        "outfit": "Comfortable t-shirt, fitted jeans or joggers",
        "environment": "Warm, inviting space like a coffee shop or lounge",
    },
    # Relatable everyday content
    "relatable": {
        "look_description": "Authentic everyday look",
        "outfit": "Casual loungewear, oversized hoodie or sweater",
        "environment": "Home setting, living room or kitchen",
    },
    # Casual and weekend content
    "casual": {
        "look_description": "Relaxed weekend vibe",
        "outfit": "Sundress or casual summer outfit, sandals",
        "environment": "Outdoor café or park setting with natural light",
    },
    # Announcements and important updates
    "announcement": {
        "look_description": "Polished, attention-grabbing look",
        "outfit": "Smart casual with statement piece, solid colours",
        "environment": "Clean, professional backdrop with brand colours",
    },
    # Outdoor/nature content
    "outdoor": {
        "look_description": "Outdoor fitness instructor look",
        "outfit": "Moisture-wicking top, running shorts or capris, trail shoes",
        "environment": "Park, trail, or outdoor bootcamp setting",
    },
    # Studio class content
    "studio": {
        "look_description": "Group fitness instructor look",
        "outfit": "Coordinated workout set, supportive sports bra, studio shoes",
        "environment": "Bright fitness studio with wood floors",
    },
    # Lifestyle and wellness content
    "lifestyle": {
        "look_description": "Wellness-focused athleisure look",
        "outfit": "Comfortable yoga pants, soft crop top or fitted tee",
        "environment": "Peaceful home or wellness space with plants",
    },
}


# Default look configuration when no content type matches
DEFAULT_LOOK: dict[str, str] = {
    "look_description": "Versatile fitness professional look",
    "outfit": "Modern athleisure matching set in neutral tones",
    "environment": "Contemporary, clean fitness or lifestyle setting",
}


def _detect_look_type(content_text: str) -> Optional[str]:
    """Detect the best look type from content text using keyword analysis.

    This function performs a more nuanced analysis than _detect_content_type()
    by checking both primary content keywords and look-specific keywords,
    with scoring to determine the best match when multiple types are detected.

    Args:
        content_text: The text content to analyze.

    Returns:
        The best matching look type string, or None if no match found.
    """
    if not content_text:
        return None

    normalized_text = content_text.lower()
    scores: dict[str, int] = {}

    # Score based on primary content keywords
    for content_type, keywords in CONTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized_text:
                scores[content_type] = scores.get(content_type, 0) + 1

    # Score based on look-specific keywords
    for look_type, keywords in LOOK_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized_text:
                scores[look_type] = scores.get(look_type, 0) + 1

    if not scores:
        return None

    # Return the type with highest score
    return max(scores, key=lambda k: scores[k])


def select_dynamic_look(
    content_text: str,
    content_type: Optional[str] = None,
    look_id: Optional[str] = None,
) -> LookInfo:
    """Select the appropriate look (outfit/environment) for content.

    This function determines the best visual look for Refiloe based on the
    content being created. It analyzes the content text and/or uses an
    explicit content type to return appropriate outfit and environment
    configurations.

    The look selection system supports the following content types:
    - workout: Gym/athletic looks for exercise content
    - fitness: Fitness instructor looks for training demos
    - professional: Business casual for professional content
    - business: Corporate looks for business topics
    - motivational: Energetic, confident looks for inspiring content
    - educational: Approachable instructor looks for tutorials
    - community: Friendly casual looks for connection content
    - relatable: Authentic everyday looks for real-life content
    - casual: Relaxed weekend looks for laid-back content
    - announcement: Polished looks for important updates
    - outdoor: Outdoor fitness looks for nature content
    - studio: Group fitness looks for class content
    - lifestyle: Wellness-focused looks for daily life content

    Args:
        content_text: The content text to analyze for look selection.
            Used to detect content type if not explicitly provided.
        content_type: Optional explicit content type. If provided, takes
            precedence over content text analysis. Valid values include
            any key from CONTENT_TO_LOOK dictionary.
        look_id: Optional database look ID. If provided, it will be
            included in the return value for database lookup purposes.

    Returns:
        A LookInfo dictionary containing:
        - look_id: Database ID if provided, otherwise None
        - look_description: Human-readable description of the look
        - content_type: The determined content type
        - environment: Setting/background description
        - outfit: Outfit/attire description

    Examples:
        >>> select_dynamic_look("Check out this gym workout!")
        {'look_id': None, 'look_description': 'Athletic gym look...',
         'content_type': 'workout', 'environment': 'Modern gym...',
         'outfit': 'Black sports bra...'}

        >>> select_dynamic_look("", content_type="professional")
        {'look_id': None, 'look_description': 'Smart business casual...',
         'content_type': 'professional', ...}

    Note:
        If no content type can be determined, a default versatile fitness
        professional look is returned. This ensures the function always
        returns valid look configuration.
    """
    log_debug(
        "Starting look selection with content_type='%s' and content length=%d."
        % (content_type, len(content_text) if content_text else 0)
    )

    # Determine the content type to use
    determined_type: Optional[str] = None

    if content_type:
        determined_type = content_type
        log_debug("Using explicit content type: '%s'." % content_type)
    elif content_text:
        determined_type = _detect_look_type(content_text)
        if determined_type:
            log_debug("Detected look type from content: '%s'." % determined_type)
        else:
            log_debug("No look type detected from content text.")

    # Get look configuration
    if determined_type and determined_type in CONTENT_TO_LOOK:
        look_config = CONTENT_TO_LOOK[determined_type]
        log_info(
            "Selected look for content type '%s': %s"
            % (determined_type, look_config.get("look_description", "N/A"))
        )
    else:
        look_config = DEFAULT_LOOK
        determined_type = "default"
        log_info(
            "No specific look found. Using default look: %s"
            % look_config.get("look_description", "N/A")
        )

    # Build and return LookInfo
    result: LookInfo = {
        "look_id": look_id,
        "look_description": look_config["look_description"],
        "content_type": determined_type,
        "environment": look_config["environment"],
        "outfit": look_config["outfit"],
        "photo_avatar_id": PHOTO_AVATAR_REGISTRY.get(determined_type, DEFAULT_PHOTO_AVATAR_ID),
    }

    return result


def get_photo_avatar_for_content(
    content_text: str = "",
    content_type: Optional[str] = None,
) -> str:
    """Get the appropriate photo avatar ID for content.

    Args:
        content_text: The content text to analyze for type detection.
        content_type: Optional explicit content type.

    Returns:
        The HeyGen photo avatar ID for the content type.
    """
    if content_type and content_type in PHOTO_AVATAR_REGISTRY:
        log_info(f"Using explicit content type '{content_type}' for photo avatar selection")
        return PHOTO_AVATAR_REGISTRY[content_type]

    if content_text:
        detected_type = _detect_look_type(content_text)
        if detected_type and detected_type in PHOTO_AVATAR_REGISTRY:
            log_info(f"Detected content type '{detected_type}' from text for photo avatar")
            return PHOTO_AVATAR_REGISTRY[detected_type]

    log_info(f"Using default photo avatar ID")
    return DEFAULT_PHOTO_AVATAR_ID


def get_photo_avatar_for_content_with_db(
    content_text: str = "",
    content_type: Optional[str] = None,
    supabase_client=None,
) -> str:
    """Get the appropriate photo avatar ID for content with database lookup and fallback.

    This function attempts to retrieve the photo avatar ID from the database first,
    then falls back to the registry-based lookup if database lookup fails.

    Args:
        content_text: The content text to analyze for type detection.
        content_type: Optional explicit content type.
        supabase_client: Supabase client instance for database queries.

    Returns:
        The HeyGen photo avatar ID for the content type.
    """
    # Determine the content type to look up
    lookup_type = content_type
    if not lookup_type and content_text:
        lookup_type = _detect_look_type(content_text)

    # Try database lookup first if we have both a client and content type
    if supabase_client and lookup_type:
        try:
            log_debug(f"Attempting database lookup for content type '{lookup_type}'")
            result = (
                supabase_client.table("photo_avatar_looks")
                .select("photo_avatar_id")
                .eq("content_type", lookup_type)
                .eq("is_active", True)
                .execute()
            )

            if result.data and len(result.data) > 0:
                db_avatar_id = result.data[0].get("photo_avatar_id")
                if db_avatar_id:
                    log_info(f"Found photo avatar '{db_avatar_id}' in database for content type '{lookup_type}'")
                    return db_avatar_id
            else:
                log_debug(f"No database entry found for content type '{lookup_type}', falling back to registry")
        except Exception as exc:
            log_warning(f"Database lookup failed for content type '{lookup_type}': {exc}, falling back to registry")

    # Fallback to registry-based lookup
    log_debug("Using registry-based photo avatar lookup")
    return get_photo_avatar_for_content(content_text=content_text, content_type=content_type)


def get_avatar_and_look_for_content(
    content_text: str,
    content_type: Optional[str] = None,
    look_id: Optional[str] = None,
) -> tuple[str, LookInfo]:
    """Get both avatar ID and look configuration for content."""
    # Use new photo avatar function
    avatar_id = get_photo_avatar_for_content(
        content_text=content_text,
        content_type=content_type,
    )

    look_info = select_dynamic_look(
        content_text=content_text,
        content_type=content_type,
        look_id=look_id,
    )

    log_info(f"Combined selection - Avatar: '{avatar_id}', Look: '{look_info.get('look_description', 'N/A')}'")

    return avatar_id, look_info
