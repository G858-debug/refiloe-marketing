"""Avatar selector for HeyGen video generation.

This module provides intelligent avatar selection based on content themes and text analysis.
It maps content themes to specific avatar IDs from environment variables with fallback logic.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Any

from utils.logger import log_debug, log_info, log_warning


class AvatarSelector:
    """Intelligent avatar selection based on content themes and text analysis."""

    # Map content themes to environment variable names
    THEME_TO_ENV_VAR: Dict[str, str] = {
        "professional": "HEYGEN_AVATAR_PROFESSIONAL_CLOSEUP",
        "casual": "HEYGEN_AVATAR_CASUAL_CLOSEUP",
        "friendly": "HEYGEN_AVATAR_CASUAL_CLOSEUP",
        "fitness": "HEYGEN_AVATAR_FITNESS_FULLBODY",
        "fitness_demo": "HEYGEN_AVATAR_FITNESS_FULLBODY",
        "workout": "HEYGEN_AVATAR_FITNESS_FULLBODY",
        "success": "HEYGEN_AVATAR_WARMSMILE_CLOSEUP",
        "success_story": "HEYGEN_AVATAR_WARMSMILE_CLOSEUP",
        "testimonial": "HEYGEN_AVATAR_WARMSMILE_CLOSEUP",
        "educational": "HEYGEN_AVATAR_PROFESSIONAL_CLOSEUP",
        "motivational": "HEYGEN_AVATAR_WARMSMILE_CLOSEUP",
        "community": "HEYGEN_AVATAR_CASUAL_CLOSEUP",
        "announcement": "HEYGEN_AVATAR_PROFESSIONAL_CLOSEUP",
    }

    # Keywords that help identify content themes from text
    THEME_KEYWORDS: Dict[str, List[str]] = {
        "professional": ["business", "revenue", "clients", "growth", "strategy", "professional", "expert"],
        "casual": ["weekend", "friday", "relax", "fun", "enjoy", "chat", "friendly"],
        "fitness": ["workout", "exercise", "training", "form", "technique", "fitness", "gym", "strength"],
        "success": ["transform", "success", "achieve", "goals", "inspire", "testimonial", "story", "results"],
        "educational": ["tips", "how to", "guide", "learn", "tutorial", "teach", "explain"],
        "motivational": ["motivation", "inspire", "push", "believe", "overcome", "challenge"],
        "community": ["together", "community", "trainer", "share", "connect", "support"],
        "announcement": ["update", "important", "announce", "news", "launch", "new"],
    }

    def __init__(self, default_avatar_env: str = "HEYGEN_AVATAR_DEFAULT"):
        """Initialize the avatar selector.

        Args:
            default_avatar_env: Environment variable name for the default/fallback avatar.
        """
        self.default_avatar_env = default_avatar_env
        self._cache: Dict[str, Optional[str]] = {}
        log_info("AvatarSelector initialized with default env var: %s" % default_avatar_env)

    def select_avatar(
        self,
        content_theme: Optional[str] = None,
        content_text: Optional[str] = None,
        avatar_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Select the most appropriate avatar ID based on content theme and text.

        This method uses a multi-tier selection strategy:
        1. If avatar_override is provided, use it directly
        2. If content_theme is provided, map it to an avatar
        3. If content_text is provided, analyze it for theme keywords
        4. Fall back to the default avatar

        Args:
            content_theme: Optional explicit content theme (e.g., "professional", "casual", "fitness")
            content_text: Optional content text to analyze for theme detection
            avatar_override: Optional explicit avatar ID to use (bypasses selection logic)

        Returns:
            Dict containing:
                - avatar_id: The selected avatar ID
                - reason: Why this avatar was selected
                - source: Source of the selection (override, theme, keyword, default)
                - theme: Detected or provided theme (if applicable)
        """
        # Handle explicit override
        if avatar_override:
            log_info("Using avatar override: %s" % avatar_override)
            return {
                "avatar_id": avatar_override,
                "reason": "explicit_override",
                "source": "override",
                "theme": content_theme,
            }

        # Try theme-based selection
        if content_theme:
            avatar_id = self._get_avatar_by_theme(content_theme)
            if avatar_id:
                log_info("Selected avatar for theme '%s': %s" % (content_theme, avatar_id))
                return {
                    "avatar_id": avatar_id,
                    "reason": "theme_mapping",
                    "source": "theme",
                    "theme": content_theme,
                }

        # Try content analysis
        if content_text:
            detected_theme = self._detect_theme_from_text(content_text)
            if detected_theme:
                avatar_id = self._get_avatar_by_theme(detected_theme)
                if avatar_id:
                    log_info(
                        "Selected avatar for detected theme '%s': %s"
                        % (detected_theme, avatar_id)
                    )
                    return {
                        "avatar_id": avatar_id,
                        "reason": "keyword_detection",
                        "source": "content_analysis",
                        "theme": detected_theme,
                        "content_excerpt": content_text[:100] if content_text else None,
                    }

        # Fall back to default avatar
        default_avatar = self._get_default_avatar()
        log_info("Using default avatar: %s" % default_avatar)
        return {
            "avatar_id": default_avatar,
            "reason": "no_match_found",
            "source": "default",
            "theme": None,
        }

    def _get_avatar_by_theme(self, theme: str) -> Optional[str]:
        """Get avatar ID for a specific theme from environment variables.

        Args:
            theme: Content theme (e.g., "professional", "casual")

        Returns:
            Avatar ID if found in environment, None otherwise
        """
        if not theme:
            return None

        # Normalize theme to lowercase for matching
        normalized_theme = theme.lower().strip()

        # Check cache first
        if normalized_theme in self._cache:
            return self._cache[normalized_theme]

        # Look up environment variable name for this theme
        env_var_name = self.THEME_TO_ENV_VAR.get(normalized_theme)
        if not env_var_name:
            log_debug("No environment variable mapping for theme: %s" % theme)
            self._cache[normalized_theme] = None
            return None

        # Get avatar ID from environment
        avatar_id = os.getenv(env_var_name)
        if avatar_id:
            log_debug("Found avatar ID '%s' for theme '%s' from %s" % (avatar_id, theme, env_var_name))
            self._cache[normalized_theme] = avatar_id
            return avatar_id

        log_debug("Environment variable '%s' not set for theme '%s'" % (env_var_name, theme))
        self._cache[normalized_theme] = None
        return None

    def _detect_theme_from_text(self, text: str) -> Optional[str]:
        """Detect content theme by analyzing text for keywords.

        Args:
            text: Content text to analyze

        Returns:
            Detected theme name, or None if no clear match
        """
        if not text:
            return None

        normalized_text = text.lower()

        # Count keyword matches for each theme
        theme_scores: Dict[str, int] = {}

        for theme, keywords in self.THEME_KEYWORDS.items():
            matches = sum(1 for keyword in keywords if keyword in normalized_text)
            if matches > 0:
                theme_scores[theme] = matches

        # Return theme with most keyword matches
        if theme_scores:
            best_theme = max(theme_scores.items(), key=lambda x: x[1])
            log_debug(
                "Detected theme '%s' with %d keyword matches"
                % (best_theme[0], best_theme[1])
            )
            return best_theme[0]

        log_debug("No theme detected from content text")
        return None

    def _get_default_avatar(self) -> str:
        """Get the default/fallback avatar ID.

        Returns:
            Default avatar ID from environment variable

        Raises:
            ValueError: If default avatar environment variable is not set
        """
        default_avatar = os.getenv(self.default_avatar_env)
        if not default_avatar:
            error_msg = (
                "Default avatar environment variable '%s' is not set"
                % self.default_avatar_env
            )
            log_error(error_msg)
            raise ValueError(error_msg)
        return default_avatar

    def get_available_themes(self) -> List[str]:
        """Get list of all available content themes.

        Returns:
            List of theme names that can be used for avatar selection
        """
        return sorted(set(self.THEME_TO_ENV_VAR.keys()))

    def get_theme_info(self, theme: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific theme.

        Args:
            theme: Theme name to query

        Returns:
            Dict with theme info (env_var, keywords, avatar_id) or None if theme not found
        """
        normalized_theme = theme.lower().strip()

        env_var = self.THEME_TO_ENV_VAR.get(normalized_theme)
        if not env_var:
            return None

        avatar_id = os.getenv(env_var)
        keywords = self.THEME_KEYWORDS.get(normalized_theme, [])

        return {
            "theme": normalized_theme,
            "env_var": env_var,
            "avatar_id": avatar_id,
            "avatar_configured": avatar_id is not None,
            "keywords": keywords,
        }


# Convenience function for backward compatibility
def select_avatar_for_content(
    content_theme: Optional[str] = None,
    content_text: Optional[str] = None,
    avatar_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Select an avatar for content (functional API).

    This is a convenience function that creates an AvatarSelector instance
    and calls select_avatar(). For repeated calls, consider creating a
    single AvatarSelector instance instead.

    Args:
        content_theme: Optional explicit content theme
        content_text: Optional content text to analyze
        avatar_override: Optional explicit avatar ID

    Returns:
        Avatar selection result dict
    """
    selector = AvatarSelector()
    return selector.select_avatar(
        content_theme=content_theme,
        content_text=content_text,
        avatar_override=avatar_override,
    )


# Module-level error for logging
from utils.logger import log_error  # noqa: E402
