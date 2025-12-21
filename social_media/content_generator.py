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
from utils.text_helpers import filter_banned_words

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

        # Determine media type for the content
        media_type = self.determine_content_media_type(
            content_text=combined_text,
            theme=theme,
            metadata=metadata,
        )

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
        post_metadata["media_type"] = media_type

        if metadata:
            post_metadata.update(metadata)

        if avatar_hint:
            avatar_hints = post_metadata.setdefault("avatar_hints", [])
            if avatar_hint not in avatar_hints:
                avatar_hints.append(avatar_hint)

        video_meta = post_metadata.setdefault("video_generation", {})
        video_meta.setdefault("content_type", classification.label)
        video_meta.setdefault("media_type", media_type)
        if avatar_hint:
            video_meta.setdefault("avatar_hint", avatar_hint)

        post["content_type"] = classification.label
        post["media_type"] = media_type
        if avatar_hint:
            post["avatar_hint"] = avatar_hint

        post["video_pipeline_context"] = {
            "content_type": classification.label,
            "confidence": classification.confidence,
            "avatar_hint": avatar_hint,
            "media_type": media_type,
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
    # Carousel content generation
    # ------------------------------------------------------------------
    def generate_carousel_content(
        self,
        topic: str,
        num_slides: int = 5,
    ) -> Dict[str, Any]:
        """Generate structured carousel content for educational/how-to posts.

        Creates a complete carousel structure with cover slide, content slides,
        and CTA slide optimized for personal trainers about admin automation.

        Args:
            topic: The main topic for the carousel (e.g., "Client Onboarding").
            num_slides: Total number of slides (default 5, minimum 3).

        Returns:
            Dict[str, Any]: Structured carousel content with cover, content_slides,
                           cta_slide, caption, and hashtags.
        """
        import json
        import re

        log_info(
            "Generating carousel content | topic=%s num_slides=%d",
            topic,
            num_slides,
        )

        # Ensure minimum slides
        num_slides = max(3, num_slides)
        num_content_slides = num_slides - 2  # Exclude cover and CTA

        # Build the carousel-specific prompt
        prompt = self._build_carousel_prompt(topic, num_content_slides)

        # Call Claude API
        response = self._call_claude_with_retry(prompt)

        if not response:
            log_warning("Failed to get carousel content from Claude API")
            return {}

        # Parse and validate the response
        carousel_data = self._parse_carousel_response(response, topic, num_content_slides)

        if carousel_data:
            log_info(
                "Successfully generated carousel content | topic=%s slides=%d",
                topic,
                num_slides,
            )
        else:
            log_warning("Failed to parse carousel response | topic=%s", topic)

        return carousel_data

    def _build_carousel_prompt(self, topic: str, num_content_slides: int) -> str:
        """Build the Claude prompt for carousel content generation.

        Args:
            topic: The carousel topic.
            num_content_slides: Number of content slides (excluding cover and CTA).

        Returns:
            str: Formatted prompt for Claude.
        """
        # Get AI influencer settings
        ai_settings = self.config.get("ai_influencer_settings", {})
        personality = ai_settings.get("personality_traits", [])

        prompt = f"""You are {ai_settings.get('name', 'Refiloe')}, creating educational carousel content for personal trainers about admin automation.

TOPIC: {topic}

TARGET AUDIENCE: Personal trainers who want to automate their admin tasks and save time.

CAROUSEL STRUCTURE:
You need to create content for a {num_content_slides + 2}-slide carousel:
1. COVER SLIDE: Attention-grabbing title
2. CONTENT SLIDES: {num_content_slides} educational steps
3. CTA SLIDE: Call-to-action to drive engagement

CHARACTER LIMITS (STRICT - content MUST fit within these limits):
- Cover title: Maximum 60 characters
- Content slide title: Maximum 40 characters
- Content slide bullets: Maximum 80 characters each, 3-5 bullets per slide
- CTA headline: Maximum 50 characters
- CTA text: Maximum 30 characters
- CTA subtext: Maximum 60 characters

CONTENT STYLE:
- Educational, how-to format
- Practical, actionable steps
- Focus on admin automation for trainers
- South African context where relevant (use Rand for pricing)
- Personality: {', '.join(personality)}

CAPTION REQUIREMENTS:
- 150-250 words
- Hook in first line
- Summarize the carousel value
- Include a question or CTA at the end

OUTPUT FORMAT (JSON):
{{
    "cover": {{
        "title": "How to Automate Client Onboarding"
    }},
    "content_slides": [
        {{
            "step_number": 1,
            "title": "Set Up Your System",
            "bullets": [
                "Create your WhatsApp Business account",
                "Set up automated greeting messages",
                "Configure payment integration"
            ]
        }}
    ],
    "cta_slide": {{
        "headline": "Ready to Save Time?",
        "cta_text": "Try Refiloe Free",
        "subtext": "Join 300+ SA trainers automating their admin"
    }},
    "caption": "Full Instagram caption for the carousel post...",
    "hashtags": ["#personaltrainer", "#fitnessadmin", "#trainertools"]
}}

IMPORTANT:
- Generate exactly {num_content_slides} content slides
- Each content slide must have step_number (1 to {num_content_slides})
- All text MUST respect character limits
- Make content specific, actionable, and valuable
- Use numbers and specific examples where possible
- Hashtags should be relevant to fitness business and admin automation

IMPORTANT: Never use the following words as they are not suitable for the target audience: gnaw, gnaws, gnawing, gnawed. Use simpler alternatives like "eat away", "bother", "wear down", or "frustrate" instead.

Generate the carousel content now:"""

        return prompt

    def _parse_carousel_response(
        self,
        response: str,
        topic: str,
        num_content_slides: int,
    ) -> Dict[str, Any]:
        """Parse and validate carousel content from Claude response.

        Args:
            response: Raw response from Claude.
            topic: The carousel topic.
            num_content_slides: Expected number of content slides.

        Returns:
            Dict[str, Any]: Validated carousel data or empty dict on failure.
        """
        import json
        import re

        try:
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if not json_match:
                log_warning("No JSON found in carousel response")
                return {}

            json_str = json_match.group()
            data = json.loads(json_str)

            # Validate and enforce character limits
            validated = self._validate_carousel_content(data, num_content_slides)

            if validated:
                # Add metadata
                from datetime import datetime

                validated["metadata"] = {
                    "topic": topic,
                    "total_slides": num_content_slides + 2,
                    "content_slides_count": len(validated.get("content_slides", [])),
                    "generated_at": datetime.now(self.sa_tz).isoformat(),
                    "ai_generated": True,
                    "model_used": self.model,
                }

            return validated

        except json.JSONDecodeError as e:
            log_warning("JSON decode error in carousel response: %s", str(e))
            return {}
        except Exception as e:
            log_warning("Error parsing carousel response: %s", str(e))
            return {}

    def _validate_carousel_content(
        self,
        data: Dict[str, Any],
        num_content_slides: int,
    ) -> Dict[str, Any]:
        """Validate and truncate carousel content to fit character limits.

        Args:
            data: Raw parsed carousel data.
            num_content_slides: Expected number of content slides.

        Returns:
            Dict[str, Any]: Validated carousel data with enforced limits.
        """
        validated: Dict[str, Any] = {}

        # Validate cover slide
        cover = data.get("cover", {})
        cover_title = filter_banned_words(str(cover.get("title", "")))[:60]
        validated["cover"] = {"title": cover_title}

        # Validate content slides
        content_slides = data.get("content_slides", [])
        validated_slides = []

        for i, slide in enumerate(content_slides[:num_content_slides]):
            step_number = slide.get("step_number", i + 1)
            title = filter_banned_words(str(slide.get("title", f"Step {step_number}")))[:40]

            # Validate bullets (3-5 per slide, 80 chars each)
            raw_bullets = slide.get("bullets", [])
            bullets = []
            for bullet in raw_bullets[:5]:
                truncated_bullet = filter_banned_words(str(bullet))[:80]
                bullets.append(truncated_bullet)

            # Ensure minimum 3 bullets
            while len(bullets) < 3:
                bullets.append("More details coming soon")

            validated_slides.append({
                "step_number": step_number,
                "title": title,
                "bullets": bullets,
            })

        # Ensure we have the expected number of content slides
        while len(validated_slides) < num_content_slides:
            validated_slides.append({
                "step_number": len(validated_slides) + 1,
                "title": f"Step {len(validated_slides) + 1}",
                "bullets": [
                    "Action item one",
                    "Action item two",
                    "Action item three",
                ],
            })

        validated["content_slides"] = validated_slides

        # Validate CTA slide
        cta = data.get("cta_slide", {})
        validated["cta_slide"] = {
            "headline": filter_banned_words(str(cta.get("headline", "Ready to Get Started?")))[:50],
            "cta_text": filter_banned_words(str(cta.get("cta_text", "Try It Free")))[:30],
            "subtext": filter_banned_words(str(cta.get("subtext", "Join trainers automating their admin")))[:60],
        }

        # Validate caption
        caption = str(data.get("caption", ""))
        if not caption:
            caption = f"Learn how to master {validated['cover']['title'].lower()}. Swipe through for actionable tips!"
        validated["caption"] = filter_banned_words(caption)

        # Validate hashtags
        hashtags = data.get("hashtags", [])
        if not hashtags or not isinstance(hashtags, list):
            hashtags = [
                "#personaltrainer",
                "#fitnessadmin",
                "#trainertools",
                "#fitnessbusiness",
                "#adminautomation",
            ]
        validated["hashtags"] = [str(h) for h in hashtags[:10]]

        return validated

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
    def determine_content_media_type(
        self,
        content_text: str,
        theme: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Determine the appropriate media type for the content.

        Analyzes post content and theme to determine whether the content
        should be presented as a video, static image, or carousel.

        Args:
            content_text: The combined text content of the post.
            theme: Optional theme identifier for context.
            metadata: Optional metadata that may contain type hints.

        Returns:
            str: One of 'video', 'static_image', or 'carousel'.

            Decision Logic:
            - 'video': Tips, educational content, announcements
            - 'static_image': Quotes, single facts, testimonials
            - 'carousel': Lists, step-by-step guides, multiple tips
        """
        # Check for explicit override in metadata
        if metadata:
            media_type_override = metadata.get("media_type")
            if media_type_override in ("video", "static_image", "carousel"):
                log_info(
                    "Media type override from metadata | type=%s",
                    media_type_override,
                )
                return media_type_override

        text_lower = (content_text or "").lower()

        # Define keywords for each media type
        carousel_keywords = [
            "step-by-step",
            "steps",
            "guide",
            "how to",
            "checklist",
            "framework",
            "list of",
            "multiple",
            "series",
            "tips for",
            "ways to",
            "carousel",
        ]

        video_keywords = [
            "tip",
            "tutorial",
            "learn",
            "announcement",
            "introducing",
            "new feature",
            "explain",
            "demonstrate",
            "workout",
            "exercise",
            "technique",
            "educational",
            "watch",
            "see how",
        ]

        static_image_keywords = [
            "quote",
            "fact",
            "testimonial",
            "client says",
            "success story",
            "remember",
            "mindset",
            "motivation",
            "inspiration",
            "celebrate",
            "proud",
        ]

        # Count matches for each type
        carousel_matches = sum(1 for kw in carousel_keywords if kw in text_lower)
        video_matches = sum(1 for kw in video_keywords if kw in text_lower)
        static_matches = sum(1 for kw in static_image_keywords if kw in text_lower)

        # Return the type with the most matches
        max_matches = max(carousel_matches, video_matches, static_matches)

        if max_matches == 0:
            # No clear keywords found, use theme-based defaults
            if theme:
                theme_lower = theme.lower()
                if "carousel" in theme_lower or "list" in theme_lower:
                    log_info(
                        "Media type from theme fallback | theme=%s type=carousel",
                        theme,
                    )
                    return "carousel"
                elif "quote" in theme_lower or "testimonial" in theme_lower or "success" in theme_lower:
                    log_info(
                        "Media type from theme fallback | theme=%s type=static_image",
                        theme,
                    )
                    return "static_image"

            # Default to video for educational content
            log_info("Media type default fallback | type=video")
            return "video"

        # Return the type with most matches (with preference order if tied)
        if carousel_matches >= video_matches and carousel_matches >= static_matches:
            log_info(
                "Media type determined | type=carousel matches=%d",
                carousel_matches,
            )
            return "carousel"
        elif video_matches >= static_matches:
            log_info(
                "Media type determined | type=video matches=%d",
                video_matches,
            )
            return "video"
        else:
            log_info(
                "Media type determined | type=static_image matches=%d",
                static_matches,
            )
            return "static_image"

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

    # ------------------------------------------------------------------
    # Triple Hook System for viral video content
    # ------------------------------------------------------------------
    def _get_video_hooks(self) -> Dict[str, Any]:
        """Get comprehensive triple-hook system for viral videos

        Returns:
            Dict containing visual_hook, text_hook, and verbal_hook
        """
        import random

        viral_hooks = self.config.get('viral_hooks', {})

        # Visual hooks (what viewers SEE in first frame)
        visual_hooks = viral_hooks.get('visual_hooks', {}).get('examples', [
            "Transformation result shown first",
            "Unexpected prop or setup",
            "Mid-action freeze frame",
            "Direct eye contact with camera",
            "Text overlay with bold claim"
        ])

        # Text hooks (on-screen text for sound-off viewing, 1-7 words)
        text_hook_templates = viral_hooks.get('text_hooks', {}).get('templates', [
            "POV: [situation]",
            "The [thing] nobody talks about",
            "Stop if you [identifier]",
            "This changed everything",
            "Wait for it..."
        ])

        # Verbal hooks (what is SAID in first 3 seconds)
        verbal_hook_templates = viral_hooks.get('verbal_hooks', {}).get('templates', [
            "The message came at [time]...",
            "Nobody told me [revelation]...",
            "I lost [thing] because [reason]...",
            "Stop doing [common mistake]...",
            "What if I told you [contrarian claim]..."
        ])

        return {
            'visual': random.choice(visual_hooks),
            'text': random.choice(text_hook_templates),
            'verbal': random.choice(verbal_hook_templates),
            'all_visual': visual_hooks,
            'all_text': text_hook_templates,
            'all_verbal': verbal_hook_templates
        }

    def _generate_triple_hook(self, theme: str, content_type: str = None) -> Dict[str, str]:
        """Generate a cohesive triple hook tailored to theme and content type

        Args:
            theme: Content theme (e.g., 'admin_hacks', 'relatable_trainer_life')
            content_type: Viral content type (e.g., 'relatable_struggle', 'myth_buster')

        Returns:
            Dict with 'visual', 'text', 'verbal' hooks and 'text_overlay_script'
        """
        import random

        hooks = self._get_video_hooks()

        # Theme-specific hook customization
        theme_hooks = {
            'admin_hacks': {
                'text_templates': [
                    "POV: Your admin is done",
                    "This saves 5 hours/week",
                    "Stop doing this manually"
                ],
                'verbal_templates': [
                    "I used to spend 3 hours on this every week...",
                    "What if I told you there's a better way...",
                    "This one automation changed everything..."
                ]
            },
            'relatable_trainer_life': {
                'text_templates': [
                    "Every trainer knows this",
                    "POV: It's 5:47 AM",
                    "The client excuse hall of fame"
                ],
                'verbal_templates': [
                    "The message came at 5:47 AM...",
                    "You know that feeling when...",
                    "I know you've been here..."
                ]
            },
            'client_management_tips': {
                'text_templates': [
                    "Why clients actually leave",
                    "The retention secret",
                    "Stop losing clients to this"
                ],
                'verbal_templates': [
                    "Nobody told me this when I started...",
                    "I lost my best client because...",
                    "The real reason clients ghost you..."
                ]
            },
            'gym_culture_humor': {
                'text_templates': [
                    "Gym people are unhinged",
                    "That one client...",
                    "Tell me you're a trainer without telling me"
                ],
                'verbal_templates': [
                    "I can't be the only one who...",
                    "The way I had to keep a straight face when...",
                    "Trainers, tell me why..."
                ]
            },
            'myth_busting': {
                'text_templates': [
                    "This advice is wrong",
                    "Stop believing this",
                    "The truth about [topic]"
                ],
                'verbal_templates': [
                    "Everything you've been told about this is wrong...",
                    "I'm about to make some people angry...",
                    "This might be controversial but..."
                ]
            }
        }

        # Get theme-specific or fallback to random
        theme_config = theme_hooks.get(theme, {})

        text_hook = random.choice(theme_config.get('text_templates', hooks['all_text']))
        verbal_hook = random.choice(theme_config.get('verbal_templates', hooks['all_verbal']))
        visual_hook = hooks['visual']

        # Create text overlay script (what appears on screen at each moment)
        text_overlay_script = [
            {"time": "0-2s", "text": text_hook, "style": "bold, centered"},
            {"time": "3-5s", "text": "👇 Keep watching", "style": "smaller, bottom"},
        ]

        return {
            'visual': visual_hook,
            'text': text_hook,
            'verbal': verbal_hook,
            'text_overlay_script': text_overlay_script,
            'theme': theme,
            'content_type': content_type
        }

    def _select_video_format(self, theme: str, content_type: str = None) -> Dict[str, Any]:
        """Select optimal video format based on content type and theme

        Args:
            theme: Content theme
            content_type: Optional viral content type override

        Returns:
            Dict with duration_range, target_words, structure, format_name
        """
        video_formats = self.config.get('video_formats', {})
        viral_content_types = self.config.get('viral_content_types', {})

        # Default format configurations
        default_formats = {
            'quick_hit': {
                'duration_range': [15, 25],
                'target_words': [25, 40],
                'structure': {'hook': 2, 'content': 12, 'cta': 3},
                'best_for': ['myth_busting', 'quick_tips', 'relatable_moments', 'challenges']
            },
            'standard': {
                'duration_range': [30, 45],
                'target_words': [50, 75],
                'structure': {'hook': 3, 'setup': 8, 'content': 25, 'cta': 5},
                'best_for': ['tutorials', 'educational', 'behind_scenes']
            },
            'story': {
                'duration_range': [45, 60],
                'target_words': [75, 100],
                'structure': {'hook': 3, 'story_setup': 10, 'tension': 20, 'resolution': 15, 'cta': 7},
                'best_for': ['transformations', 'client_stories', 'personal_journey']
            }
        }

        # Merge with config
        for fmt_name, fmt_config in video_formats.items():
            if fmt_name in default_formats:
                default_formats[fmt_name].update(fmt_config)
            else:
                default_formats[fmt_name] = fmt_config

        # Theme to format mapping
        theme_format_map = {
            'admin_hacks': 'quick_hit',
            'relatable_trainer_life': 'quick_hit',
            'gym_culture_humor': 'quick_hit',
            'myth_busting': 'quick_hit',
            'client_management_tips': 'standard',
            'engagement_questions': 'quick_hit',
            'client_stories': 'story',
            'growth_mindset': 'standard'
        }

        # Content type overrides
        content_type_format_map = {
            'relatable_struggle': 'quick_hit',
            'myth_buster': 'quick_hit',
            'transformation_reveal': 'story',
            'challenge_content': 'quick_hit',
            'behind_scenes': 'standard',
            'quick_tip': 'quick_hit'
        }

        # Determine format
        if content_type and content_type in content_type_format_map:
            format_name = content_type_format_map[content_type]
        elif theme in theme_format_map:
            format_name = theme_format_map[theme]
        else:
            format_name = 'standard'  # Default

        selected_format = default_formats.get(format_name, default_formats['standard'])
        selected_format['format_name'] = format_name

        return selected_format

    def _create_video_script_prompt(
        self,
        theme: str,
        duration: int,
        style: str,
        hook: str,
        target_duration_seconds: int = 55,
        target_word_count_min: int = 75,
        target_word_count_max: int = 100,
        triple_hook: Dict[str, Any] = None,
    ) -> str:
        """Create prompt for video script generation with Triple Hook System

        Args:
            theme: Content theme
            duration: Video duration in seconds
            style: Video style
            hook: Video hook to use
            target_duration_seconds: Target duration for optimal video length
            target_word_count_min: Minimum word count target
            target_word_count_max: Maximum word count target
            triple_hook: Triple hook system dict with visual, text, and verbal hooks

        Returns:
            str: Formatted prompt for video script generation
        """
        # Get AI influencer settings
        ai_settings = self.config.get('ai_influencer_settings', {})
        personality = ai_settings.get('personality_traits', [])
        speaking_style = ai_settings.get('speaking_style', {})

        # Calculate timing breakdown
        hook_duration = 3  # First 3 seconds for hook
        main_content_duration = duration - hook_duration - 5  # 5 seconds for CTA
        main_content_end = duration - 5
        cta_duration = 5

        # Use triple hook if provided, otherwise use legacy hook
        if triple_hook:
            triple_hook_section = f"""
TRIPLE HOOK SYSTEM (CRITICAL - All three must work together):

1. VISUAL HOOK (Frame 1): {triple_hook['visual']}
   - What the viewer SEES before any audio registers
   - Must stop the scroll in <1 second
   - Specify exactly what's on screen

2. TEXT HOOK (0-2s): "{triple_hook['text']}"
   - On-screen text overlay (1-7 words MAX)
   - 92% of viewers watch with sound OFF initially
   - This text must create curiosity alone

3. VERBAL HOOK (0-3s): Start with something like: "{triple_hook['verbal']}"
   - First words spoken
   - NO introductions ("Hi, I'm..." = instant scroll)
   - Pattern interrupt or curiosity gap

VIDEO STRUCTURE:
- 0-1s: Visual hook + text overlay appears
- 1-3s: Verbal hook delivered
- 3-{main_content_end}s: Core content with text overlays at key points
- {main_content_end}-{duration}s: Strong CTA with visual/text reinforcement

TEXT OVERLAY MOMENTS (specify in script):
- Opening hook text
- Key statistic or number (if applicable)
- "Wait for it..." or retention hook at midpoint
- CTA text at end

Also update the JSON response format to include:
- "visual_hook": description of first frame
- "text_overlays": array of {{"time": "Xs-Ys", "text": "...", "style": "..."}}
- "triple_hook_summary": brief description of how all three hooks work together
"""
        else:
            triple_hook_section = f"""
VIDEO STRUCTURE:
1. Hook (0-3s): {hook}
2. Main Content (3-{main_content_end}s): Core message with visual cues
3. CTA ({main_content_end}-{duration}s): Strong call-to-action
"""

        prompt = f"""You are {ai_settings.get('name', 'Refiloe')}, creating a {target_duration_seconds}-second video script for personal trainers.

VIDEO SPECIFICATIONS:
- Target Duration: {target_duration_seconds} seconds (aim for 50-60 seconds optimal range)
- Maximum Duration: {duration} seconds
- Style: {style}
- Theme: {theme}
- Hook: {hook}

SCRIPT LENGTH REQUIREMENTS (CRITICAL):
- Target word count: {target_word_count_min}-{target_word_count_max} words MAXIMUM
- Speaking rate: ~150 words per minute (2.5 words per second)
- This ensures the script fits within the 50-60 second optimal duration
- Be concise and impactful - every word must count
- DO NOT exceed {target_word_count_max} words total

PERSONALITY & VOICE:
- {', '.join(personality)}
- Voice: {speaking_style.get('voice', 'First person')}
- Tone: {speaking_style.get('tone', 'Conversational and engaging')}

VIDEO SCRIPT RESTRICTIONS (CRITICAL):
- NEVER use "Refiloe" or "I'm Refiloe" in video scripts
- NEVER use "Hi there" or "Hey there" as greetings
- Jump straight into the content - no formal introductions
- Speak TO trainers, not ABOUT yourself
- Use "you" and "your" language, avoid "I" and "my" when possible
- Start with a hook, question, or relatable moment
- Good: "The message came at 5:47 AM..."
- Good: "You know that feeling when..."
- Bad: "Hey! I'm Refiloe, and today..."
- Bad: "Hi there, personal trainers..."

RETENTION OPTIMIZATION:
- Hook MUST grab attention in first 3 seconds
- Use power words and emotional triggers
- Include specific numbers and statistics
- Create curiosity and urgency
- Make it impossible to scroll past

{triple_hook_section}

VISUAL CUES TO INCLUDE:
- Text overlays for key points
- Gestures and expressions
- Props or demonstrations
- Screen recordings if applicable
- Transitions between topics

TRENDING ELEMENTS:
- Use current social media language
- Include relevant hashtags in script
- Reference popular challenges or trends
- Use engaging visual descriptions

CALL-TO-ACTION OPTIONS:
- "Comment 'ADMIN' for the free guide"
- "Share this with a trainer who needs it"
- "Save this for your next client"
- "Which tip will you try first?"
- "Follow for more trainer hacks"

REEL TITLE REQUIREMENTS (CRITICAL FOR FACEBOOK REELS):
- Generate an engaging "reel_title" that will be used as the Facebook Reel title
- Maximum 255 characters (Facebook limit)
- Must be curiosity-inducing and scroll-stopping
- Use emotional triggers, time-stamps, or POV format
- Examples of great reel titles:
  * "When clients cancel at 6:47 AM... 😤"
  * "The spreadsheet that changed everything 📊"
  * "POV: You just got your 10th reschedule this week"
  * "Nobody talks about THIS part of being a trainer..."
  * "The message that made me rethink everything 💭"
  * "5:30 AM training session gone wrong..."
- Make it impossible to scroll past
- Should complement the video hook but be standalone engaging
- Can include 1-2 emojis maximum

IMPORTANT: Never use the following words as they are not suitable for the target audience: gnaw, gnaws, gnawing, gnawed. Use simpler alternatives like "eat away", "bother", "wear down", or "frustrate" instead.

OUTPUT FORMAT:
Please provide your response in the following JSON format:
{{
    "title": "Compelling video title",
    "reel_title": "Engaging Facebook Reel title (max 255 chars, curiosity-inducing, e.g., 'When clients cancel at 6:47 AM... 😤')",
    "hook": "The exact opening hook text",
    "visual_hook": "Description of first frame visual",
    "text_overlays": [
        {{"time": "0-2s", "text": "Opening hook text", "style": "bold, centered"}},
        {{"time": "5-7s", "text": "Key point", "style": "medium, bottom"}}
    ],
    "triple_hook_summary": "How visual, text, and verbal hooks work together",
    "script": [
        {{
            "time_start": 0,
            "time_end": 3,
            "text": "Hook text with exact wording",
            "visual_cue": "Visual instruction (e.g., 'Point to camera, serious expression')",
            "tone": "Urgent, attention-grabbing"
        }},
        {{
            "time_start": 3,
            "time_end": {main_content_end},
            "text": "Main content with exact wording",
            "visual_cue": "Visual instruction (e.g., 'Show demonstration, text overlay')",
            "tone": "Educational, engaging"
        }},
        {{
            "time_start": {main_content_end},
            "time_end": {duration},
            "text": "Call-to-action with exact wording",
            "visual_cue": "Visual instruction (e.g., 'Point to comment section, encouraging smile')",
            "tone": "Encouraging, action-oriented"
        }}
    ],
    "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"],
    "visual_notes": "Overall visual direction and style",
    "retention_hooks": ["List of retention elements used"],
    "cta_type": "The type of call-to-action used",
    "estimated_retention": "High/Medium/Low based on hook strength"
}}

Generate a script that will keep trainers watching until the end!"""

        return prompt

    def create_video_script(
        self,
        theme: str,
        duration: int = None,
        style: str = "educational",
        target_duration_seconds: int = None,
        content_type: str = None,
        format_override: str = None,
    ) -> Dict:
        """Generate time-coded video scripts with automatic format selection

        Args:
            theme: Content theme for the video
            duration: Video duration in seconds (optional - auto-selected if None)
            style: Video style (educational, motivational, behind_scenes, tutorial, story)
            target_duration_seconds: Target duration (optional - auto-selected if None)
            content_type: Viral content type for format optimization
            format_override: Force specific format ('quick_hit', 'standard', 'story')

        Returns:
            Dict: Structured video script with time codes, visual cues, and CTAs
        """
        import random

        # Auto-select format if not specified
        if format_override:
            video_format = self.config.get('video_formats', {}).get(format_override, {})
            video_format['format_name'] = format_override
        else:
            video_format = self._select_video_format(theme, content_type)

        format_name = video_format.get('format_name', 'standard')
        duration_range = video_format.get('duration_range', [30, 45])
        word_range = video_format.get('target_words', [50, 75])

        # Set duration from format if not specified
        if duration is None:
            duration = duration_range[1]  # Use upper bound

        if target_duration_seconds is None:
            # Target middle of range
            target_duration_seconds = (duration_range[0] + duration_range[1]) // 2

        # Calculate word counts from format
        target_word_count_min = word_range[0]
        target_word_count_max = word_range[1]

        log_info(
            f"Creating video script - Theme: {theme}, Format: {format_name}, "
            f"Duration: {target_duration_seconds}s, Words: {target_word_count_min}-{target_word_count_max}"
        )

        try:
            # Generate triple hook for this theme
            triple_hook = self._generate_triple_hook(theme, content_type)

            # Get video-specific hooks (for legacy compatibility)
            video_hooks = self._get_video_hooks()
            selected_hook = video_hooks.get('verbal', 'Stop scrolling if you\'re a trainer who...')

            # Create video script prompt with triple hook
            prompt = self._create_video_script_prompt(
                theme,
                duration,
                style,
                selected_hook,
                target_duration_seconds,
                target_word_count_min,
                target_word_count_max,
                triple_hook,
            )

            # Call Claude API
            response = self._call_claude_with_retry(prompt)

            if not response:
                log_error("Failed to get response from Claude API for video script")
                return {}

            # Parse video script response
            script_data = self._parse_video_script_response(response, theme, duration, style)

            if script_data:
                # Add triple hook metadata
                script_data['triple_hook'] = triple_hook

                # Add video format metadata
                script_data['video_format'] = format_name
                script_data['format_config'] = video_format

                # Validate word count
                script_text = " ".join([segment.get("text", "") for segment in script_data.get("script", [])])
                word_count = len(script_text.split())

                # Use format-specific max words for validation
                max_recommended = word_range[1]
                if word_count > max_recommended:
                    log_warning(
                        f"Video script exceeds {max_recommended} words (actual: {word_count} words). "
                        f"This may exceed the target duration of {target_duration_seconds} seconds. "
                        f"Consider requesting a shorter version."
                    )
                    script_data["word_count_warning"] = {
                        "actual_words": word_count,
                        "max_recommended": max_recommended,
                        "exceeded_by": word_count - max_recommended,
                    }

                script_data["word_count"] = word_count
                script_data["target_duration_seconds"] = target_duration_seconds

                log_info(
                    f"Successfully generated video script with Triple Hook System: {theme} - {duration}s - {style} - {format_name} "
                    f"(word count: {word_count}, target: {target_word_count_min}-{target_word_count_max})"
                )
                return script_data
            else:
                log_error("Failed to parse video script response")
                return {}

        except Exception as e:
            log_error(f"Error creating video script: {str(e)}")
            return {}

    def create_quick_hit_script(self, theme: str, content_type: str = 'quick_tip') -> Dict:
        """Generate a quick-hit video script (15-25 seconds) optimized for virality

        Args:
            theme: Content theme
            content_type: Viral content type

        Returns:
            Dict: Short, punchy video script
        """
        return self.create_video_script(
            theme=theme,
            style='punchy',
            content_type=content_type,
            format_override='quick_hit'
        )

    def create_story_script(self, theme: str, story_type: str = 'transformation') -> Dict:
        """Generate a story-format video script (45-60 seconds) with narrative arc

        Args:
            theme: Content theme
            story_type: Type of story (transformation, journey, case_study)

        Returns:
            Dict: Narrative video script with tension and resolution
        """
        return self.create_video_script(
            theme=theme,
            style='story',
            content_type='transformation_reveal' if story_type == 'transformation' else 'behind_scenes',
            format_override='story'
        )


__all__ = ["ContentGenerator"]
