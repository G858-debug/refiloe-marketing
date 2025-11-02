"""Avatar mapping configuration and selection utilities."""

from __future__ import annotations

from typing import Optional

from utils.logger import log_debug, log_info, log_warning


AVATAR_REGISTRY = {
    "PROFESSIONAL_CLOSEUP": "110f75a397604454ba6f822c68f29949",
    "CASUAL_CLOSEUP": "e39d22ad46c34b5599dc939c63ba1d89",
    "FITNESS_FULLBODY": "3fa139effeb348a99b959065a2425363",
    "CONFIDENT_SWIMWEAR_FULLBODY": "5d511d22069d4a7d9d75ffd78d1a0bda",
    "SERIOUS_CLOSEUP": "efe8efb12f0a4bc8b961e22220fc974d",
    "WARMSMILE_CLOSEUP": "9648b4e9da9c444c877214312c5ad27c",
    "LAUGHING_CLOSEUP": "89c3da65880249e78e26070732b52f53",
    "THREEQUARTERS_CLOSEUP": "5637676d31d54946b7585b012a3ce182",
    "SUMMERCASUAL_THREEQUARTERBODY": "12e5e8c825e547a0a67ad0057288a4da",
    "GROUP": "89c3da65880249e78e26070732b52f53",
}


CONTENT_TYPE_MAPPING = {
    "educational": "WARMSMILE_CLOSEUP",
    "motivational": "CONFIDENT_SWIMWEAR_FULLBODY",
    "relatable": "LAUGHING_CLOSEUP",
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


DEFAULT_AVATAR_TYPE = "THREEQUARTERS_CLOSEUP"


def _detect_content_type(content_text: str) -> Optional[str]:
    """Infer the content type from the provided text using keyword matching."""
    if not content_text:
        log_debug("No content text provided for avatar detection.")
        return None

    normalized_text = content_text.lower()
    log_debug("Analyzing content text for keyword matches to determine avatar type.")

    for content_type, keywords in CONTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized_text:
                log_info(
                    "Keyword match detected for content type '%s' using keyword '%s'."
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
