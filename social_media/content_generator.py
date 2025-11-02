"""Enhanced Content Generator with avatar-aware metadata.

This module extends the legacy :class:`ContentGenerator` to layer in
content-type detection, avatar selection hints, and richer metadata that can
be consumed by downstream video generation components. The implementation
remains backwards compatible with existing callers that rely on
``generate_single_post`` and related helpers, while exposing a new
``generate_post`` entry-point and lightweight preview utilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from utils.logger import log_info, log_warning

try:  # pragma: no cover - allow absolute or package-relative import
    from content_generator import ContentGenerator as _LegacyContentGenerator  # type: ignore
except ImportError:  # pragma: no cover - defensive fallback
    from ..content_generator import ContentGenerator as _LegacyContentGenerator  # type: ignore


@dataclass
class _ClassificationResult:
    """Represents the outcome of lightweight content classification."""

    label: str
    confidence: float
    matched_keywords: List[str]
    fallback_reason: Optional[str] = None

    def as_metadata(self) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "content_type": self.label,
            "confidence": round(self.confidence, 3),
        }
        if self.matched_keywords:
            metadata["matched_keywords"] = self.matched_keywords
        if self.fallback_reason:
            metadata["fallback_reason"] = self.fallback_reason
        return metadata


class ContentGenerator(_LegacyContentGenerator):
    """Avatar-aware content generator.

    The class extends the legacy implementation with:

    * Post-generation content classification (educational, motivational, etc.).
    * Avatar hint resolution for workout and success-story narratives.
    * Prompt template augmentation that nudges Claude to consider avatar framing.
    * Test-friendly preview utilities to inspect avatar choices without video
      generation side-effects.
    """

    # Keyword heuristics for simple in-memory classification. The lists are
    # intentionally short and interpretable so that product managers can refine
    # them without re-training any model.
    _CONTENT_TYPE_KEYWORDS: Dict[str, List[str]] = {
        "educational": [
            "step-by-step",
            "framework",
            "tip",
            "how to",
            "tutorial",
            "guide",
            "lesson",
            "checklist",
            "system",
        ],
        "motivational": [
            "you got this",
            "keep going",
            "mindset",
            "motivation",
            "proud",
            "believe",
            "commit",
            "push",
            "grind",
        ],
        "success_story": [
            "before and after",
            "transformation",
            "client win",
            "success story",
            "celebrate",
            "testimonial",
            "journey",
            "results",
        ],
        "workout": [
            "reps",
            "sets",
            "warm-up",
            "cool-down",
            "tempo",
            "form",
            "rep scheme",
            "superset",
            "exercise",
            "workout",
            "full-body",
        ],
    }

    # Theme-driven defaults provide a stable fallback when keyword coverage is
    # low (e.g. short captions).
    _THEME_DEFAULTS: Dict[str, str] = {
        "admin_hacks": "educational",
        "client_management_tips": "educational",
        "relatable_trainer_life": "motivational",
        "engagement_questions": "motivational",
        "client_success_stories": "success_story",
        "workout_breakdowns": "workout",
    }

    # Avatar hints keyed by classified content type.
    _AVATAR_HINTS: Dict[str, str] = {
        "workout": "FITNESS_FULLBODY",
        "success_story": "CONFIDENT_SWIMWEAR_FULLBODY",
    }

    def generate_post(
        self,
        theme: str,
        format_type: str,
        *,
        hook_type: Optional[str] = None,
        emergency_mode: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate content and enrich it with avatar-aware metadata.

        Args:
            theme: Configured content theme (e.g. ``admin_hacks``).
            format_type: Post format (e.g. ``single_image_with_caption``).
            hook_type: Optional hook override.
            emergency_mode: Reduce latency/creativity trade-offs.
            metadata: Additional metadata to merge into the post payload.

        Returns:
            Dict[str, Any]: Generated post payload with enriched metadata.
        """

        post = super().generate_single_post(
            theme,
            format_type,
            hook_type=hook_type,
            emergency_mode=emergency_mode,
        )

        if not post:
            log_warning(
                "generate_post returned empty payload | theme=%s format=%s",
                theme,
                format_type,
            )
            return {}

        combined_text = self._collect_text_fragments(post)
        classification = self._classify_content_type(
            theme=theme,
            content_text=combined_text,
            metadata=metadata,
        )

        avatar_hint = self._resolve_avatar_hint(classification.label, combined_text)

        log_info(
            "Content classification | theme=%s format=%s label=%s confidence=%.2f matches=%s fallback=%s",
            theme,
            format_type,
            classification.label,
            classification.confidence,
            classification.matched_keywords,
            classification.fallback_reason,
        )

        if avatar_hint:
            log_info(
                "Avatar hint resolved | label=%s hint=%s",
                classification.label,
                avatar_hint,
            )

        post_metadata: Dict[str, Any] = post.setdefault("metadata", {})
        post_metadata.update(classification.as_metadata())

        if metadata:
            post_metadata.update(metadata)

        if avatar_hint:
            avatar_hints = post_metadata.setdefault("avatar_hints", [])
            if avatar_hint not in avatar_hints:
                avatar_hints.append(avatar_hint)

        video_meta = post_metadata.setdefault("video_generation", {})
        video_meta.setdefault("content_type", classification.label)
        if avatar_hint:
            video_meta.setdefault("avatar_hint", avatar_hint)

        post["content_type"] = classification.label
        if avatar_hint:
            post["avatar_hint"] = avatar_hint

        post["video_pipeline_context"] = {
            "content_type": classification.label,
            "confidence": classification.confidence,
            "avatar_hint": avatar_hint,
        }

        return post

    # ------------------------------------------------------------------
    # Prompt augmentation
    # ------------------------------------------------------------------
    def create_claude_prompt(
        self,
        theme: str,
        format_type: str,
        hook_type: Optional[str] = None,
        emergency_mode: bool = False,
    ) -> str:
        """Inject avatar presentation guidance into the legacy prompt."""

        base_prompt = super().create_claude_prompt(
            theme,
            format_type,
            hook_type=hook_type,
            emergency_mode=emergency_mode,
        )

        avatar_guidance = (
            "\nAVATAR PRESENTATION NOTES:\n"
            "- Generate educational content suitable for close-up delivery.\n"
            "- Create motivational content with full-body demonstration potential.\n"
        )

        if avatar_guidance not in base_prompt:
            return f"{base_prompt}{avatar_guidance}"
        return base_prompt

    # ------------------------------------------------------------------
    # Preview utilities
    # ------------------------------------------------------------------
    def preview_avatar_selection(
        self,
        content_text: str,
        *,
        theme: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return the avatar hint that would be selected for supplied text."""

        classification = self._classify_content_type(
            theme=theme or "",
            content_text=content_text,
            metadata=None,
        )
        avatar_hint = self._resolve_avatar_hint(classification.label, content_text)

        log_info(
            "Avatar preview | theme=%s label=%s confidence=%.2f hint=%s",
            theme,
            classification.label,
            classification.confidence,
            avatar_hint,
        )

        return {
            "content_type": classification.label,
            "confidence": classification.confidence,
            "avatar_hint": avatar_hint,
            "matched_keywords": classification.matched_keywords,
            "fallback_reason": classification.fallback_reason,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _collect_text_fragments(self, post: Dict[str, Any]) -> str:
        """Aggregate text fragments for keyword analysis."""

        fragments: List[str] = []

        primary_content = post.get("content")
        if isinstance(primary_content, str):
            fragments.append(primary_content)

        if isinstance(post.get("title"), str):
            fragments.append(post["title"])

        caption = post.get("caption")
        if isinstance(caption, dict):
            for key in ("title", "content", "summary"):
                value = caption.get(key)
                if isinstance(value, str):
                    fragments.append(value)

            key_points = caption.get("key_points") or caption.get("carousel_slides")
            if isinstance(key_points, list):
                fragments.extend(str(item) for item in key_points)

        key_points = post.get("key_points")
        if isinstance(key_points, list):
            fragments.extend(str(item) for item in key_points)

        engagement_hook = post.get("engagement_hook")
        if isinstance(engagement_hook, str):
            fragments.append(engagement_hook)

        variations = post.get("all_variations")
        if isinstance(variations, list):
            for variation in variations:
                if isinstance(variation, dict):
                    content = variation.get("content")
                    if isinstance(content, str):
                        fragments.append(content)

        return " \n".join(fragment.strip() for fragment in fragments if fragment)

    def _classify_content_type(
        self,
        *,
        theme: str,
        content_text: str,
        metadata: Optional[Dict[str, Any]],
    ) -> _ClassificationResult:
        """Infer content type using keyword heuristics with fallbacks."""

        override_type: Optional[str] = None
        if metadata:
            override_type = metadata.get("content_type") or metadata.get("preferred_content_type")
        if override_type:
            return _ClassificationResult(
                label=str(override_type),
                confidence=1.0,
                matched_keywords=[],
                fallback_reason="metadata_override",
            )

        text_lower = (content_text or "").lower()
        best_label = None
        best_score = 0.0
        best_matches: List[str] = []

        for label, keywords in self._CONTENT_TYPE_KEYWORDS.items():
            matches = [kw for kw in keywords if kw in text_lower]
            if not matches:
                continue

            # Score favours both the variety and density of matches.
            coverage = len(set(matches)) / len(keywords)
            density = min(1.0, len(matches) / max(len(text_lower.split()), 1) * 25)
            score = coverage * 0.7 + density * 0.3

            if score > best_score:
                best_label = label
                best_score = score
                best_matches = sorted(set(matches))

        if best_label:
            confidence = min(1.0, 0.35 + best_score)
            return _ClassificationResult(
                label=best_label,
                confidence=confidence,
                matched_keywords=best_matches,
            )

        fallback_label = self._THEME_DEFAULTS.get(theme) or "informational"
        return _ClassificationResult(
            label=fallback_label,
            confidence=0.25,
            matched_keywords=[],
            fallback_reason=f"theme_default:{theme or 'unknown'}",
        )

    def _resolve_avatar_hint(
        self,
        content_type: str,
        content_text: str,
    ) -> Optional[str]:
        """Map content type (and secondary signals) to avatar hints."""

        hint = self._AVATAR_HINTS.get(content_type)
        if hint:
            return hint

        # Secondary heuristic: workout-style language inside motivational copy.
        if content_type == "motivational":
            text_lower = content_text.lower()
            workout_tokens = {"reps", "sets", "lift", "barbell", "dumbbell", "kettlebell"}
            if any(token in text_lower for token in workout_tokens):
                return self._AVATAR_HINTS.get("workout")

        return None


__all__ = ["ContentGenerator"]
