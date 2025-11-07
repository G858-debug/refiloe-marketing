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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import pytz

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

    # South African public holidays (month, day) - for cultural relevance
    _SA_PUBLIC_HOLIDAYS: Dict[str, tuple] = {
        "New Year's Day": (1, 1),
        "Human Rights Day": (3, 21),
        "Good Friday": None,  # Moveable - Easter-based
        "Family Day": None,  # Moveable - Easter Monday
        "Freedom Day": (4, 27),
        "Workers' Day": (5, 1),
        "Youth Day": (6, 16),
        "National Women's Day": (8, 9),
        "Heritage Day": (9, 24),
        "Day of Reconciliation": (12, 16),
        "Christmas Day": (12, 25),
        "Day of Goodwill": (12, 26),
    }

    # South African seasons (Southern Hemisphere)
    _SA_SEASONS: Dict[str, Dict[str, Any]] = {
        "Summer": {
            "months": [12, 1, 2],
            "description": "Hot summer weather, outdoor training season",
            "keywords": ["beach body", "outdoor workouts", "hydration", "summer fitness"],
        },
        "Autumn": {
            "months": [3, 4, 5],
            "description": "Mild autumn weather, perfect for building routines",
            "keywords": ["routine building", "consistent training", "autumn goals"],
        },
        "Winter": {
            "months": [6, 7, 8],
            "description": "Cool winter months, indoor training focus",
            "keywords": ["indoor workouts", "winter fitness", "staying active", "off-season gains"],
        },
        "Spring": {
            "months": [9, 10, 11],
            "description": "Spring renewal, preparation for summer",
            "keywords": ["spring fitness", "renewal", "pre-summer prep", "outdoor return"],
        },
    }

    # Optimal posting times for South African audience (in 24-hour format)
    _SA_OPTIMAL_POSTING_TIMES: Dict[str, tuple] = {
        "morning": (5, 30, 7, 0),  # 5:30-7:00 AM (pre-work)
        "lunch": (12, 0, 13, 0),   # 12:00-1:00 PM
        "evening": (17, 0, 19, 0), # 5:00-7:00 PM (post-work)
        "night": (20, 0, 21, 0),   # 8:00-9:00 PM (leisure time)
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

        # Add SA-specific context to post metadata
        sa_season = self._get_current_sa_season()
        sa_holidays = self._get_upcoming_sa_holidays(days_ahead=14)
        sa_posting_time = self._get_sa_optimal_posting_time()

        post_metadata["sa_context"] = {
            "season": sa_season["name"],
            "season_description": sa_season["description"],
            "season_keywords": sa_season["keywords"],
            "upcoming_holidays": [
                {"name": h["name"], "days_until": h["days_until"]}
                for h in sa_holidays[:3]
            ],
            "optimal_posting_time": sa_posting_time,
            "currency_format": "Rand (R)",
        }

        log_info(
            "SA context added | season=%s holidays=%d posting_time=%s",
            sa_season["name"],
            len(sa_holidays),
            sa_posting_time["slot"],
        )

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
        """Inject avatar presentation guidance and SA-specific context into the legacy prompt."""

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

        # Add SA-specific context enrichment
        enriched_prompt = self._enrich_with_sa_context(base_prompt)

        if avatar_guidance not in enriched_prompt:
            return f"{enriched_prompt}{avatar_guidance}"
        return enriched_prompt

    # ------------------------------------------------------------------
    # SA-specific public utilities
    # ------------------------------------------------------------------
    def get_sa_context_info(self) -> Dict[str, Any]:
        """Get comprehensive South African context information.

        Returns:
            Dict[str, Any]: SA context including season, holidays, and posting times.
        """
        season = self._get_current_sa_season()
        holidays = self._get_upcoming_sa_holidays(days_ahead=30)
        posting_time = self._get_sa_optimal_posting_time()

        return {
            "season": season,
            "upcoming_holidays": holidays,
            "optimal_posting_time": posting_time,
            "all_posting_times": {
                slot: {
                    "start": f"{times[0]:02d}:{times[1]:02d}",
                    "end": f"{times[2]:02d}:{times[3]:02d}",
                }
                for slot, times in self._SA_OPTIMAL_POSTING_TIMES.items()
            },
        }

    def format_currency(self, amount: float, include_decimals: bool = True) -> str:
        """Public wrapper for Rand currency formatting.

        Args:
            amount: The amount to format.
            include_decimals: Whether to include decimal places (default: True).

        Returns:
            str: Formatted currency string in Rand (e.g., "R1,250.00").
        """
        return self._format_rand(amount, include_decimals)

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

    # ------------------------------------------------------------------
    # South African context helpers
    # ------------------------------------------------------------------
    def _get_current_sa_season(self) -> Dict[str, Any]:
        """Get the current South African season based on the current month.

        Returns:
            Dict[str, Any]: Season information with description and keywords.
        """
        sa_tz = pytz.timezone("Africa/Johannesburg")
        current_month = datetime.now(sa_tz).month

        for season_name, season_info in self._SA_SEASONS.items():
            if current_month in season_info["months"]:
                return {"name": season_name, **season_info}

        # Fallback to Summer
        return {"name": "Summer", **self._SA_SEASONS["Summer"]}

    def _get_upcoming_sa_holidays(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Get upcoming South African public holidays within the specified timeframe.

        Args:
            days_ahead: Number of days to look ahead (default: 30).

        Returns:
            List[Dict[str, Any]]: List of upcoming holidays with dates and names.
        """
        sa_tz = pytz.timezone("Africa/Johannesburg")
        today = datetime.now(sa_tz)
        current_year = today.year
        upcoming = []

        for holiday_name, date_tuple in self._SA_PUBLIC_HOLIDAYS.items():
            if date_tuple is None:
                # Skip moveable holidays (Easter-based)
                continue

            month, day = date_tuple
            # Check this year's date
            holiday_date = datetime(current_year, month, day, tzinfo=sa_tz)

            # If holiday has passed this year, check next year
            if holiday_date < today:
                holiday_date = datetime(current_year + 1, month, day, tzinfo=sa_tz)

            days_until = (holiday_date - today).days

            if 0 <= days_until <= days_ahead:
                upcoming.append({
                    "name": holiday_name,
                    "date": holiday_date,
                    "days_until": days_until,
                })

        # Sort by date
        upcoming.sort(key=lambda x: x["days_until"])
        return upcoming

    @staticmethod
    def _format_rand(amount: float, include_decimals: bool = True) -> str:
        """Format a currency amount as South African Rand.

        Args:
            amount: The amount to format.
            include_decimals: Whether to include decimal places (default: True).

        Returns:
            str: Formatted currency string (e.g., "R1,250.00" or "R1,250").
        """
        if include_decimals:
            return f"R{amount:,.2f}"
        else:
            return f"R{amount:,.0f}"

    def _get_sa_optimal_posting_time(
        self, preference: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get an optimal posting time for South African audience.

        Args:
            preference: Preferred time slot ("morning", "lunch", "evening", "night").
                       If None, selects based on current time or randomly.

        Returns:
            Dict[str, Any]: Posting time information with time range and description.
        """
        sa_tz = pytz.timezone("Africa/Johannesburg")
        current_hour = datetime.now(sa_tz).hour

        # If no preference, select based on current time or next optimal slot
        if preference is None:
            if 5 <= current_hour < 7:
                preference = "morning"
            elif 12 <= current_hour < 13:
                preference = "lunch"
            elif 17 <= current_hour < 19:
                preference = "evening"
            elif 20 <= current_hour < 21:
                preference = "night"
            else:
                # Default to next optimal time
                if current_hour < 5:
                    preference = "morning"
                elif current_hour < 12:
                    preference = "lunch"
                elif current_hour < 17:
                    preference = "evening"
                else:
                    preference = "night"

        time_slot = self._SA_OPTIMAL_POSTING_TIMES.get(preference, self._SA_OPTIMAL_POSTING_TIMES["evening"])
        start_hour, start_min, end_hour, end_min = time_slot

        return {
            "slot": preference,
            "start": f"{start_hour:02d}:{start_min:02d}",
            "end": f"{end_hour:02d}:{end_min:02d}",
            "description": {
                "morning": "Pre-work engagement - trainers planning their day",
                "lunch": "Midday break - quick tips and motivation",
                "evening": "Post-work wind-down - peak engagement time",
                "night": "Leisure browsing - in-depth content consumption",
            }.get(preference, "Optimal posting time"),
        }

    def _enrich_with_sa_context(self, base_context: str) -> str:
        """Enrich content prompt with South African cultural context.

        Args:
            base_context: The base prompt or context to enrich.

        Returns:
            str: Enriched context with SA-specific references.
        """
        season = self._get_current_sa_season()
        upcoming_holidays = self._get_upcoming_sa_holidays(days_ahead=14)

        sa_context = "\n\nSOUTH AFRICAN CONTEXT:\n"
        sa_context += f"- Current Season: {season['name']} - {season['description']}\n"
        sa_context += f"- Seasonal Focus: {', '.join(season['keywords'])}\n"

        if upcoming_holidays:
            sa_context += f"- Upcoming Holidays ({len(upcoming_holidays)}): "
            holiday_names = [
                f"{h['name']} ({h['days_until']} days)"
                for h in upcoming_holidays[:3]
            ]
            sa_context += ", ".join(holiday_names) + "\n"

        sa_context += "\nCURRENCY FORMATTING:\n"
        sa_context += "- Always use Rand (R) for pricing examples (e.g., R500, R1,200, R15,000)\n"
        sa_context += "- Examples: 'R500 consultation fee', 'R1,500 monthly package'\n"

        sa_context += "\nOPTIMAL POSTING TIMES (SAST - South African Standard Time):\n"
        sa_context += "- Morning (5:30-7:00 AM): Pre-work engagement\n"
        sa_context += "- Lunch (12:00-1:00 PM): Midday motivation\n"
        sa_context += "- Evening (5:00-7:00 PM): Peak engagement\n"
        sa_context += "- Night (8:00-9:00 PM): In-depth content\n"

        return base_context + sa_context


__all__ = ["ContentGenerator"]
