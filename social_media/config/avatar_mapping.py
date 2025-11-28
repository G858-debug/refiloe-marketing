"""Avatar mapping configuration and selection utilities.

This module provides a comprehensive system for selecting appropriate avatars
and looks (outfits/environments) for Refiloe, an AI fitness assistant targeting
South African personal trainers.

Avatar Selection System
-----------------------
The system works in two layers:

1. **Avatar Selection**: Maps content types to specific avatar poses/shots
   (e.g., closeup, fullbody, three-quarter view). Each avatar has a unique
   HeyGen avatar ID stored in AVATAR_REGISTRY.

2. **Look Selection**: Maps content types to appropriate visual styles
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
...     get_avatar_for_content,
...     select_dynamic_look,
... )
>>> avatar_id = get_avatar_for_content("Check out these workout tips!")
>>> look_info = select_dynamic_look("Transform your body with this workout!")
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
    """

    look_id: Optional[str]
    look_description: str
    content_type: str
    environment: str
    outfit: str


AVATAR_REGISTRY = {
    "PROFESSIONAL_CLOSEUP": "110f75a397604454ba6f822c68f29949",
    "CASUAL_CLOSEUP": "e39d22ad46c34b5599dc939c63ba1d89",
    "FITNESS_FULLBODY": "3fa139effeb348a99b959065a2425363",
    "CONFIDENT_SWIMWEAR_FULLBODY": "5d511d22069d4a7d9d75ffd78d1a0bda",
    "SERIOUS_CLOSEUP": "efe8efb12f0a4bc8b961e22220fc974d",
    "WARMSMILE_CLOSEUP": "9648b4e9da9c444c877214312c5ad27c",
    "THREEQUARTERS_CLOSEUP": "5637676d31d54946b7585b012a3ce182",
    "SUMMERCASUAL_THREEQUARTERBODY": "12e5e8c825e547a0a67ad0057288a4da",
    "GROUP": "89c3da65880249e78e26070732b52f53",
}


CONTENT_TYPE_MAPPING = {
    "educational": "WARMSMILE_CLOSEUP",
    "motivational": "CONFIDENT_SWIMWEAR_FULLBODY",
    "relatable": "WARMSMILE_CLOSEUP",
    "professional": "PROFESSIONAL_CLOSEUP",
    "community": "CASUAL_CLOSEUP",
    "fitness": "FITNESS_FULLBODY",
    "announcement": "SERIOUS_CLOSEUP",
    "casual": "SUMMERCASUAL_THREEQUARTERBODY",
    "default": "THREEQUARTERS_CLOSEUP",
}


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


DEFAULT_AVATAR_TYPE = "THREEQUARTERS_CLOSEUP"


def _detect_content_type(content_text: str) -> Optional[str]:
    """Infer the content type from the provided text using keyword matching.

    This function analyzes content text to determine the most appropriate
    content type by searching for predefined keywords. It checks both
    CONTENT_KEYWORDS and LOOK_KEYWORDS dictionaries.

    Args:
        content_text: The text content to analyze for type detection.

    Returns:
        The detected content type string (e.g., 'fitness', 'motivational'),
        or None if no keywords match.

    Note:
        Priority is given to CONTENT_KEYWORDS matches over LOOK_KEYWORDS.
        The first keyword match found determines the content type.
    """
    if not content_text:
        log_debug("No content text provided for avatar detection.")
        return None

    normalized_text = content_text.lower()
    log_debug("Analyzing content text for keyword matches to determine avatar type.")

    # First check primary content keywords
    for content_type, keywords in CONTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized_text:
                log_info(
                    "Keyword match detected for content type '%s' using keyword '%s'."
                    % (content_type, keyword)
                )
                return content_type

    # Then check extended look-specific keywords
    for content_type, keywords in LOOK_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized_text:
                log_info(
                    "Look keyword match detected for content type '%s' using keyword '%s'."
                    % (content_type, keyword)
                )
                return content_type

    log_debug("No keyword matches found for provided content text.")
    return None


def _resolve_avatar_type(content_type: str) -> str:
    """Resolve the avatar type from a provided content type or avatar key."""
    if content_type in AVATAR_REGISTRY:
        log_debug(
            "Content type '%s' recognized as direct avatar key." % content_type
        )
        return content_type

    mapped_avatar = CONTENT_TYPE_MAPPING.get(content_type)
    if mapped_avatar:
        log_debug(
            "Content type '%s' mapped to avatar key '%s'."
            % (content_type, mapped_avatar)
        )
        return mapped_avatar

    log_warning(
        "Content type '%s' not recognized. Falling back to default avatar type."
        % content_type
    )
    return DEFAULT_AVATAR_TYPE


def get_avatar_for_content(content_text: str, content_type: Optional[str] = None) -> str:
    """Determine the appropriate avatar ID for the given content."""
    log_debug(
        "Starting avatar selection with content_type='%s' and content length=%d."
        % (content_type, len(content_text) if content_text else 0)
    )

    inferred_type = content_type or _detect_content_type(content_text)
    if inferred_type:
        avatar_type = _resolve_avatar_type(inferred_type)
    else:
        log_debug("No explicit or inferred content type. Using default avatar type.")
        avatar_type = DEFAULT_AVATAR_TYPE

    avatar_id = AVATAR_REGISTRY.get(avatar_type, AVATAR_REGISTRY[DEFAULT_AVATAR_TYPE])

    log_info(
        "Selected avatar type '%s' with ID '%s' for content."
        % (avatar_type, avatar_id)
    )

    return avatar_id


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
    }

    return result


def get_avatar_and_look_for_content(
    content_text: str,
    content_type: Optional[str] = None,
    look_id: Optional[str] = None,
) -> tuple[str, LookInfo]:
    """Get both avatar ID and look configuration for content.

    This is a convenience function that combines avatar and look selection
    into a single call, ensuring consistent content type detection for both.

    Args:
        content_text: The content text to analyze.
        content_type: Optional explicit content type.
        look_id: Optional database look ID for look configuration.

    Returns:
        A tuple containing:
        - avatar_id: The HeyGen avatar ID string
        - look_info: The LookInfo dictionary with look configuration

    Example:
        >>> avatar_id, look_info = get_avatar_and_look_for_content(
        ...     "Time to hit the gym for leg day!"
        ... )
        >>> print(f"Avatar: {avatar_id}")
        >>> print(f"Look: {look_info['look_description']}")
    """
    avatar_id = get_avatar_for_content(content_text, content_type)
    look_info = select_dynamic_look(content_text, content_type, look_id)

    log_info(
        "Combined selection - Avatar: '%s', Look: '%s'"
        % (avatar_id, look_info.get("look_description", "N/A"))
    )

    return avatar_id, look_info
