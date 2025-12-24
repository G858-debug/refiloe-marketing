"""Content Pipeline Module
=================================

Coordinates text, image, and video generation to produce fully assembled
social media assets that comply with brand guidelines while monitoring cost.

The :class:`ContentPipeline` orchestrates interactions between Claude (text),
FLUX.1 (image), and HeyGen (video) services, layering quality checks and cost
tracking so the existing scheduler can request complete content packages with a
single call.
"""

from __future__ import annotations

import math
import os
import random
from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pytz
import yaml

from utils.logger import log_error, log_info, log_warning

try:  # Package-local import when executed inside social_media package
    from .database import SocialMediaDatabase
except ImportError:  # Fallback when modules are placed at project root
    from database import SocialMediaDatabase

try:
    from .utils.avatar_iv_tracker import can_generate_avatar_iv, get_avatar_iv_credit_status
except ImportError:
    from utils.avatar_iv_tracker import can_generate_avatar_iv, get_avatar_iv_credit_status

try:
    from .content_generator import ContentGenerator
except ImportError:
    from content_generator import ContentGenerator

try:
    from .image_generator import ImageGenerator
except ImportError:
    from image_generator import ImageGenerator

try:
    from .video_generator import VideoGenerator
except ImportError:
    from video_generator import VideoGenerator

try:
    from .thumbnail_generator import ThumbnailGenerator
except ImportError:
    from thumbnail_generator import ThumbnailGenerator

try:
    from .carousel_template_generator import CarouselTemplateGenerator
except ImportError:
    from carousel_template_generator import CarouselTemplateGenerator

try:
    from .config.avatar_mapping import get_avatar_and_look_for_content
except ImportError:
    from config.avatar_mapping import get_avatar_and_look_for_content


class ContentPipeline:
    """High-level orchestrator for cross-modal social media content.

    The pipeline centralises:

    * **Text generation** via Claude Sonnet 4 (through :class:`ContentGenerator`).
    * **Image generation** via FLUX.1 on Replicate (handled by
      :class:`ImageGenerator`).
    * **Video generation** via HeyGen-style avatars (through
      :class:`VideoGenerator`).
    * **Quality validation** covering character consistency, text/visual
      alignment, and brand guidelines.
    * **Cost tracking & optimisation** so the scheduler can balance creativity
      with budget constraints.
    """

    _DEFAULT_COSTS = {
        "claude": {"unit": "1k_tokens", "unit_cost": 0.0085},
        "flux": {"unit": "image", "unit_cost": 0.06},
        "heygen": {"unit": "minute", "unit_cost": 0.45},
    }

    _TEMPLATE_ORDER = [
        "quick_tip_video",
        "educational_video",
        "image_carousel",
        "mixed_media_post",
    ]

    def __init__(
        self,
        config_path: str,
        supabase_client: Any,
        *,
        content_generator: Optional[ContentGenerator] = None,
        image_generator: Optional[ImageGenerator] = None,
        video_generator: Optional[VideoGenerator] = None,
    ) -> None:
        self.sa_tz = pytz.timezone("Africa/Johannesburg")
        self.config_path = self._resolve_config_path(config_path)
        self.config = self._load_config(self.config_path)

        self.db = SocialMediaDatabase(supabase_client)
        self.supabase_client = supabase_client

        self.content_generator = content_generator or self._init_content_generator(
            self.config_path, supabase_client
        )
        self.image_generator = image_generator or self._init_image_generator(
            self.config_path, supabase_client
        )
        self.video_generator = video_generator or self._init_video_generator(
            self.config_path, supabase_client
        )
        self.carousel_generator = self._init_carousel_generator(self.config_path, supabase_client)
        self.thumbnail_generator = self._init_thumbnail_generator()

        self.cost_tracker = self._initialise_cost_tracker()
        self.cost_log: List[Dict[str, Any]] = []
        self.asset_registry: List[Dict[str, Any]] = []

        self.templates = self._build_templates()
        self.character_profile = self.config.get("ai_influencer_settings", {})
        self.launch_date = self._resolve_launch_date()

        log_info(
            f"ContentPipeline initialised with text={bool(self.content_generator)}, "
            f"image={bool(self.image_generator)}, "
            f"video={bool(self.video_generator)}, "
            f"carousel={bool(self.carousel_generator)}, "
            f"thumbnail={bool(self.thumbnail_generator)}"
        )

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def create_social_post(
        self,
        post_type: str = "image",
        *,
        template_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a fully packaged social post.

        Args:
            post_type: One of "image", "video", "carousel", "mixed".
            template_name: Optional override to pick a specific template.
            metadata: Additional directives (e.g., trending topic insights).

        Returns:
            Dictionary containing assembled assets, quality checks, and cost
            summary suitable for downstream scheduling.
        """

        post_type = (post_type or "image").lower()
        template = self._select_template(post_type, template_name)
        generation_meta = metadata or {}

        log_info(
            f"Generating social post | type={post_type} template={template['name']}"
        )

        text_payload = self._generate_text_payload(template, generation_meta)
        visual_assets = self._generate_visual_assets(template, text_payload)
        video_assets = self._generate_video_assets(template, text_payload)

        (
            visual_assets,
            video_assets,
            consistency_report,
        ) = self.ensure_character_consistency(
            template, text_payload, visual_assets, video_assets
        )

        assembled_post = self._combine_assets(
            post_type,
            template,
            text_payload,
            visual_assets,
            video_assets,
            generation_meta,
        )

        assembled_post["consistency_report"] = consistency_report

        quality = self._run_quality_checks(assembled_post, template)
        assembled_post["quality"] = quality
        assembled_post["cost_summary"] = self._cost_summary_snapshot()

        self._register_asset(assembled_post)

        return assembled_post

    def create_video_series(
        self, topic: str, num_videos: int = 5, *, style: str = "educational"
    ) -> Dict[str, Any]:
        """Generate a cohesive multi-part video series.

        Returns a payload containing per-episode assets plus aggregate cost and
        quality intel so the scheduler can schedule episodic drops.
        """

        num_videos = max(1, min(num_videos, 10))
        log_info(f"Generating video series | topic={topic} episodes={num_videos}")

        scripts = self.content_generator.generate_video_series(topic, num_videos)
        optimised_scripts = self._optimise_video_scripts(scripts, style)

        episodes: List[Dict[str, Any]] = []
        for script in optimised_scripts:
            template = self.templates["educational_video"]
            text_payload = {
                "script": script,
                "caption": self._generate_caption_for_video(script, template),
            }
            visual_assets = []  # Videos rely on thumbnails, generated below
            video_assets = self._generate_video_assets(template, text_payload)

            if template.get("thumbnail_style") and text_payload["caption"]:
                prompts = self._build_image_prompts(template, text_payload)
                visual_assets = self._batch_image_generation(prompts, template)

            (
                visual_assets,
                video_assets,
                consistency_report,
            ) = self.ensure_character_consistency(
                template, text_payload, visual_assets, video_assets
            )

            episode_payload = self._combine_assets(
                "video",
                template,
                text_payload,
                visual_assets,
                video_assets,
                {"series_topic": topic},
            )
            episode_payload["quality"] = self._run_quality_checks(
                episode_payload, template
            )
            episode_payload["consistency_report"] = consistency_report
            episodes.append(episode_payload)

        series_payload = {
            "topic": topic,
            "episodes": episodes,
            "cost_summary": self._cost_summary_snapshot(),
            "generated_at": datetime.now(self.sa_tz).isoformat(),
        }

        return series_payload

    def create_weekly_content_batch(self) -> Dict[str, Any]:
        """Produce a seven-day publishing batch aligned with config cadence."""

        week_number = self._calculate_week_number()
        schedule = self.db.get_posting_schedule(week_number)
        posts_per_day = schedule.get("posts_per_day", 4)
        total_posts = posts_per_day * 7

        plan = self._build_weekly_plan(total_posts)
        scheduled_times = self._generate_scheduled_times(schedule)

        batch_posts: List[Dict[str, Any]] = []
        for idx, template_name in enumerate(plan):
            template = self.templates[template_name]
            post_payload = self.create_social_post(
                template["type"], template_name=template_name
            )

            if idx < len(scheduled_times):
                post_payload["scheduled_time"] = scheduled_times[idx].isoformat()

            batch_posts.append(post_payload)

        batch = {
            "week_number": week_number,
            "plan": plan,
            "posts": batch_posts,
            "schedule": schedule,
            "cost_summary": self._cost_summary_snapshot(),
            "generated_at": datetime.now(self.sa_tz).isoformat(),
        }

        log_info(
            f"Weekly batch generated | week={week_number} posts={len(batch_posts)}"
        )

        return batch

    def ensure_character_consistency(
        self,
        template: Dict[str, Any],
        text_payload: Dict[str, Any],
        visual_assets: List[Dict[str, Any]],
        video_assets: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        """Validate visual assets and regenerate anything that drifts off-model."""

        if not self.image_generator:
            report = {
                "status": "skipped",
                "reason": "image_generator_unavailable",
                "assets": [],
                "average_score": None,
                "threshold": None,
            }
            return visual_assets, video_assets, report

        threshold = self._resolve_consistency_threshold()
        reports: List[Dict[str, Any]] = []
        scores: List[float] = []

        baseline = getattr(self.image_generator, "character_reference_url", None)
        baseline_source = "generator_reference" if baseline else None

        first_image_url = next(
            (
                asset.get("image_url")
                for asset in visual_assets
                if isinstance(asset, dict) and asset.get("image_url")
            ),
            None,
        )

        if not baseline and first_image_url:
            try:
                if hasattr(self.image_generator, "set_character_reference") and self.image_generator.set_character_reference(first_image_url):
                    baseline = getattr(
                        self.image_generator, "character_reference_url", first_image_url
                    )
                    baseline_source = "visual_asset"
                else:
                    baseline = first_image_url
                    baseline_source = "visual_asset"
            except Exception as exc:  # pragma: no cover - defensive logging
                log_warning(f"Failed to set initial reference image: {exc}")
                baseline = first_image_url
                baseline_source = "visual_asset"

        for idx, asset in enumerate(visual_assets):
            if not isinstance(asset, dict):
                continue

            asset_url = asset.get("image_url")
            if not asset_url:
                continue

            reference = baseline or asset_url
            _, distance = self.image_generator.validate_character_consistency(
                reference, asset_url
            )
            initial_score = self._consistency_distance_to_score(distance)
            passed = initial_score >= threshold if baseline else True

            asset_report: Dict[str, Any] = {
                "type": "image",
                "index": idx,
                "asset_url": asset_url,
                "initial_score": initial_score,
                "score": initial_score,
                "threshold": threshold,
                "regenerated": False,
                "passed": passed,
            }

            if not passed:
                regenerated = self._regenerate_image_asset(
                    template, asset, reference
                )
                asset_report["regenerated"] = True
                if regenerated and regenerated.get("image_url"):
                    visual_assets[idx] = regenerated
                    regen_url = regenerated["image_url"]
                    _, regen_distance = self.image_generator.validate_character_consistency(
                        reference, regen_url
                    )
                    final_score = self._consistency_distance_to_score(regen_distance)
                    asset_report["score"] = final_score
                    asset_report["asset_url"] = regen_url
                    asset_report["passed"] = final_score >= threshold
                    asset_report.setdefault("notes", []).append("regenerated_with_reference")
                    if final_score >= threshold and not baseline:
                        baseline = regen_url
                        baseline_source = baseline_source or "regenerated_image"
                else:
                    asset_report.setdefault("notes", []).append("regeneration_failed")
            else:
                if not baseline:
                    baseline = asset_url
                    baseline_source = baseline_source or "visual_asset"

            scores.append(asset_report["score"])
            reports.append(asset_report)

        thumbnail_url = None
        if isinstance(video_assets, dict):
            thumbnail_url = video_assets.get("thumbnail_url") or (
                (video_assets.get("result") or {}).get("thumbnail_url")
                if isinstance(video_assets.get("result"), dict)
                else None
            )

        if thumbnail_url:
            reference = baseline or thumbnail_url
            _, distance = self.image_generator.validate_character_consistency(
                reference, thumbnail_url
            )
            initial_score = self._consistency_distance_to_score(distance)
            passed = initial_score >= threshold if baseline else True

            thumbnail_report: Dict[str, Any] = {
                "type": "video_thumbnail",
                "asset_url": thumbnail_url,
                "initial_score": initial_score,
                "score": initial_score,
                "threshold": threshold,
                "regenerated": False,
                "passed": passed,
            }

            if not passed:
                regenerated_thumb = self._regenerate_video_thumbnail(
                    template, text_payload
                )
                thumbnail_report["regenerated"] = True
                if regenerated_thumb and regenerated_thumb.get("image_url"):
                    new_thumbnail_url = regenerated_thumb["image_url"]
                    if isinstance(video_assets, dict):
                        video_assets["thumbnail_url"] = new_thumbnail_url
                        video_assets.setdefault("thumbnail_details", regenerated_thumb)
                    _, regen_distance = self.image_generator.validate_character_consistency(
                        reference, new_thumbnail_url
                    )
                    final_score = self._consistency_distance_to_score(regen_distance)
                    thumbnail_report["score"] = final_score
                    thumbnail_report["asset_url"] = new_thumbnail_url
                    thumbnail_report["passed"] = final_score >= threshold
                    thumbnail_report.setdefault("notes", []).append("thumbnail_replaced")
                    if final_score >= threshold and not baseline:
                        baseline = new_thumbnail_url
                        baseline_source = baseline_source or "video_thumbnail"
                else:
                    thumbnail_report.setdefault(
                        "notes", []
                    ).append("thumbnail_regeneration_failed")
            else:
                if not baseline:
                    baseline = thumbnail_url
                    baseline_source = baseline_source or "video_thumbnail"

            scores.append(thumbnail_report["score"])
            reports.append(thumbnail_report)

        average_score = sum(scores) / len(scores) if scores else None
        report = {
            "status": "completed" if reports else "skipped",
            "threshold": threshold,
            "average_score": average_score,
            "baseline_source": baseline_source,
            "assets": reports,
        }

        return visual_assets, video_assets, report

    def _resolve_consistency_threshold(self) -> float:
        image_cfg = self.config.get("image_generation")
        if isinstance(image_cfg, dict):
            configured = image_cfg.get("consistency_score_threshold")
            if configured is not None:
                try:
                    return float(configured)
                except (TypeError, ValueError):
                    log_warning("Invalid consistency_score_threshold in config; using fallback")

        generator_threshold = getattr(self.image_generator, "_consistency_threshold", None)
        if generator_threshold is not None:
            try:
                diff_threshold = float(generator_threshold)
                return max(0.0, min(100.0, 100.0 - diff_threshold))
            except (TypeError, ValueError):  # pragma: no cover - defensive log path
                log_warning("Invalid generator consistency threshold; using fallback")

        return 75.0

    @staticmethod
    def _consistency_distance_to_score(distance: float) -> float:
        try:
            value = float(distance)
        except (TypeError, ValueError):
            return 0.0

        if not math.isfinite(value):
            return 0.0

        return max(0.0, min(100.0, 100.0 - value))

    def _regenerate_image_asset(
        self,
        template: Dict[str, Any],
        asset: Dict[str, Any],
        reference_url: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not self.image_generator:
            return None

        prompt = (
            asset.get("source_prompt")
            or asset.get("original_prompt")
            or asset.get("prompt")
        )
        if not prompt:
            return None

        style = (
            asset.get("style")
            or template.get("visual_style")
            or template.get("thumbnail_style")
            or "professional"
        )
        setting = asset.get("setting")

        try:
            if reference_url and hasattr(self.image_generator, "set_character_reference"):
                self.image_generator.set_character_reference(reference_url)
        except Exception as exc:  # pragma: no cover - defensive log path
            log_warning(f"Failed to reinforce reference before regeneration: {exc}")

        try:
            if hasattr(self.image_generator, "_generate_character_image"):
                regenerated = self.image_generator._generate_character_image(  # type: ignore[attr-defined]
                    prompt=prompt,
                    style=style,
                    setting=setting,
                    persist=True,
                    use_cache=False,
                    force_refresh=True,
                )
            else:
                regenerated = self.image_generator.generate_influencer_image(
                    prompt=prompt,
                    style=style,
                    setting=setting,
                    use_cache=False,
                )
        except Exception as exc:
            log_error(f"Image regeneration failed: {exc}")
            return None

        if isinstance(regenerated, dict):
            regenerated.setdefault("source_prompt", prompt)
            regenerated.setdefault("style", style)
            if setting:
                regenerated.setdefault("setting", setting)
            regenerated["regenerated_from"] = asset.get("image_url")
            return regenerated

        return None

    def _regenerate_video_thumbnail(
        self,
        template: Dict[str, Any],
        text_payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not self.image_generator:
            return None

        prompts = self._build_image_prompts(template, text_payload)
        if not prompts:
            return None

        prompt, style = prompts[0]

        try:
            if hasattr(self.image_generator, "_generate_character_image"):
                regenerated = self.image_generator._generate_character_image(  # type: ignore[attr-defined]
                    prompt=prompt,
                    style=style,
                    setting=None,
                    persist=False,
                    use_cache=False,
                    force_refresh=True,
                )
            else:
                regenerated = self.image_generator.generate_consistent_character(
                    prompt=prompt,
                    style=style,
                    force_refresh=True,
                )
        except Exception as exc:
            log_error(f"Thumbnail regeneration failed: {exc}")
            return None

        if isinstance(regenerated, dict):
            regenerated.setdefault("source_prompt", prompt)
            regenerated.setdefault("style", style)
            return regenerated

        return None

    # ------------------------------------------------------------------
    # Text generation helpers
    # ------------------------------------------------------------------
    def _generate_text_payload(
        self, template: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}

        if template.get("needs_caption", True):
            caption = self.content_generator.generate_single_post(
                template["theme"],
                template["format"],
                hook_type=template.get("hook_type"),
                emergency_mode=metadata.get("emergency_mode", False),
            )
            payload["caption"] = caption
            caption_tokens = self._estimate_token_usage(caption.get("content", ""))
            self._record_cost("claude", caption_tokens / 1000, {
                "template": template["name"],
                "purpose": "caption",
            })

        if template["type"] == "video":
            script = self.content_generator.create_video_script(
                theme=template["theme"],
                duration=template.get("duration_seconds", 60),
                style=template.get("video_style", "educational"),
            )
            payload["script"] = script
            script_text = " ".join(
                segment.get("text", "") for segment in script.get("script", [])
            )
            script_tokens = self._estimate_token_usage(script_text)
            self._record_cost("claude", script_tokens / 1000, {
                "template": template["name"],
                "purpose": "video_script",
            })

        return payload

    def _generate_caption_for_video(
        self, script: Dict[str, Any], template: Dict[str, Any]
    ) -> Dict[str, Any]:
        caption = self.content_generator.generate_single_post(
            template["theme"], template["format"], hook_type="benefit_hook"
        )
        caption_tokens = self._estimate_token_usage(caption.get("content", ""))
        self._record_cost("claude", caption_tokens / 1000, {
            "template": template["name"],
            "purpose": "series_caption",
        })
        return caption

    # ------------------------------------------------------------------
    # Visual & video generation helpers
    # ------------------------------------------------------------------
    def _generate_visual_assets(
        self, template: Dict[str, Any], text_payload: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if template["type"] not in {"image", "carousel", "mixed", "video"}:
            return []

        if not self.image_generator:
            log_warning("Image generator unavailable; skipping visual generation")
            return []

        # Check media_type from template
        media_type = template.get("media_type")

        # If media_type is 'static_image', use HeyGen static image generation
        if media_type == "static_image":
            log_info(f"Generating HeyGen static image for template={template['name']}")
            return self._generate_heygen_static_image_asset(template, text_payload)

        # If media_type is 'video', skip visual assets (video handles itself)
        if media_type == "video":
            log_info(f"Skipping visual assets for video media_type in template={template['name']}")
            return []

        # If media_type is 'carousel' or template type is carousel, use carousel generator
        if (media_type == "carousel" or template["type"] == "carousel") and self.carousel_generator:
            return self._generate_carousel_assets(template, text_payload)

        # Fallback to Replicate image generation
        log_info(f"Using Replicate image generation for template={template['name']}")
        prompts = self._build_image_prompts(template, text_payload)
        images = self._batch_image_generation(prompts, template)
        return images

    def _generate_heygen_static_image_asset(
        self, template: Dict[str, Any], text_payload: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate a static image using HeyGen Photo Avatar API.

        Args:
            template: Template configuration containing media_type.
            text_payload: Text content including caption for content analysis.

        Returns:
            List containing a single image asset dictionary, or empty list on failure.
        """
        try:
            # Extract caption text for avatar selection
            caption = text_payload.get("caption", {})
            caption_text = caption.get("content", "") or caption.get("title", "")

            if not caption_text:
                log_warning("No caption text available for avatar selection, using default content type")
                caption_text = template.get("theme", "")

            # Get avatar_id and look info using avatar_mapping
            log_info("Selecting avatar and look for HeyGen static image generation")
            avatar_id, look_info = get_avatar_and_look_for_content(
                content_text=caption_text,
                content_type=template.get("content_type")
            )

            log_info(
                f"Selected avatar_id={avatar_id}, look={look_info.get('look_description', 'N/A')}"
            )

            # Generate HeyGen static image
            result = self.image_generator.generate_heygen_static_image(
                avatar_id=avatar_id,
                custom_prompt=template.get("custom_prompt")
            )

            if not result or "error" in result:
                error_msg = result.get("error", "Unknown error") if result else "No result returned"
                log_error(f"HeyGen static image generation failed: {error_msg}")

                # Fallback to Replicate if HeyGen fails
                log_info("Falling back to Replicate image generation")
                prompts = self._build_image_prompts(template, text_payload)
                return self._batch_image_generation(prompts, template)

            # Annotate result with metadata
            result["type"] = "heygen_static_image"
            result["template"] = template["name"]
            result["look_info"] = look_info
            result["source"] = "heygen"

            log_info(
                f"Successfully generated HeyGen static image: {result.get('image_url', 'N/A')}"
            )

            return [result]

        except Exception as exc:
            log_error(f"Error generating HeyGen static image: {exc}")

            # Fallback to Replicate on any error
            log_info("Falling back to Replicate image generation due to error")
            try:
                prompts = self._build_image_prompts(template, text_payload)
                return self._batch_image_generation(prompts, template)
            except Exception as fallback_exc:
                log_error(f"Replicate fallback also failed: {fallback_exc}")
                return []

    def _generate_carousel_assets(
        self, template: Dict[str, Any], text_payload: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate carousel slides using carousel_generator.

        Args:
            template: Template configuration for the carousel.
            text_payload: Text content including caption with carousel data.

        Returns:
            List of dictionaries containing slide image paths and metadata.
        """
        # Generate avatar image for slide 1
        avatar_path = None
        if self.image_generator:
            persona_marker = template.get("persona_marker", "Refiloe")
            avatar_prompt = f"{persona_marker} professional portrait, friendly smile, studio lighting"
            avatar_style = template.get("visual_style", "professional_beige")

            try:
                avatar_result = self.image_generator.generate_influencer_image(
                    avatar_prompt, avatar_style
                )
                if isinstance(avatar_result, dict) and avatar_result.get("image_url"):
                    avatar_path = avatar_result.get("local_path") or avatar_result.get("image_url")
                    self._record_cost("flux", 1, {
                        "template": template["name"],
                        "purpose": "carousel_avatar",
                    })
            except Exception as exc:
                log_warning(f"Failed to generate carousel avatar: {exc}")

        # Generate carousel content using carousel_generator
        carousel_data = self._generate_carousel_content(template, text_payload, avatar_path)
        slide_paths = self.carousel_generator.create_carousel(carousel_data)

        # Convert slide paths to asset dictionaries
        assets: List[Dict[str, Any]] = []
        for idx, path in enumerate(slide_paths):
            assets.append({
                "image_url": path,
                "local_path": path,
                "slide_number": idx + 1,
                "type": "carousel_slide",
                "source_prompt": f"carousel_slide_{idx + 1}",
                "style": template.get("visual_style", "professional_beige"),
            })

        log_info(f"Generated {len(assets)} carousel slides for template={template['name']}")
        return assets

    def _generate_carousel_content(
        self,
        template: Dict[str, Any],
        text_payload: Dict[str, Any],
        avatar_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Structure carousel data for the carousel_generator.

        Args:
            template: Template configuration for the carousel.
            text_payload: Text content including caption with carousel data.
            avatar_path: Optional path to avatar image for cover slide.

        Returns:
            Dictionary structured for carousel_generator.create_carousel().
        """
        caption = text_payload.get("caption", {})
        slides_count = template.get("slides_count") or template.get("slides", 5)

        # Extract title from caption
        title = caption.get("title") or caption.get("hook") or "Tips for Success"

        # Parse content into steps/bullets
        key_points = (
            caption.get("key_points")
            or caption.get("carousel_slides")
            or caption.get("tips")
            or []
        )

        # Generate default steps if no key points available
        if not key_points:
            content_text = caption.get("content", "")
            # Try to extract bullet points from content
            if "\n" in content_text:
                key_points = [
                    line.strip().lstrip("•-*").strip()
                    for line in content_text.split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ][:slides_count - 2]  # Reserve space for cover and CTA

            # Fallback default steps
            if not key_points:
                key_points = [
                    "Identify your most time-consuming tasks",
                    "Set up automation workflows",
                    "Track your productivity gains",
                ]

        # Build slides structure
        slides: List[Dict[str, Any]] = []

        # Slide 1: COVER with avatar and title
        slides.append({
            "type": "COVER",
            "avatar_path": avatar_path or "",
            "title": title,
        })

        # Content slides (slides 2 to n-1)
        for idx, point in enumerate(key_points[:slides_count - 2]):
            step_num = idx + 1

            # Parse point into title and bullets if structured
            if isinstance(point, dict):
                step_title = point.get("title", f"Step {step_num}")
                bullets = point.get("bullets", [point.get("content", "")])
            elif ": " in str(point):
                parts = str(point).split(": ", 1)
                step_title = f"Step {step_num}: {parts[0]}"
                bullets = [parts[1]] if len(parts) > 1 else [parts[0]]
            else:
                step_title = f"Step {step_num}"
                bullets = [str(point)]

            # Ensure we have 3-5 bullets per slide
            while len(bullets) < 3:
                bullets.append("")

            slides.append({
                "type": "CONTENT",
                "step_title": step_title,
                "bullets": bullets[:5],
            })

        # Final slide: CTA
        cta_headline = caption.get("cta_headline") or "Ready to Transform Your Workflow?"
        cta_text = caption.get("cta_text") or caption.get("call_to_action") or "Follow for More Tips!"
        cta_subtext = caption.get("cta_subtext") or "Save this post and share with a fellow trainer"

        slides.append({
            "type": "CTA",
            "headline": cta_headline,
            "cta_text": cta_text,
            "subtext": cta_subtext,
        })

        return {"slides": slides}

    def _generate_video_assets(
        self, template: Dict[str, Any], text_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        if template["type"] not in {"video", "mixed"}:
            return {}

        script = text_payload.get("script") or {}
        duration = template.get("duration_seconds", script.get("duration", 60))

        if not self.video_generator:
            log_warning("Video generator unavailable; returning script-only payload")
            return {
                "status": "pending_generation",
                "script": script,
            }

        # Check Avatar IV credits before attempting generation
        credits_available, credit_status = can_generate_avatar_iv(
            duration,
            self.db.supabase if hasattr(self.db, 'supabase') else None
        )

        # If credits exhausted, mark for manual creation instead of API generation
        if not credits_available:
            log_warning(
                f"Avatar IV credits exhausted ({credit_status.get('remaining', 0):.2f} min remaining, "
                f"{credit_status.get('required', 0):.2f} min required). "
                f"Marking post for manual video creation."
            )
            return {
                "status": "requires_manual_creation",
                "script": script,
                "duration_seconds": duration,
                "requires_manual_video": True,
                "credit_status": credit_status,
                "reason": "avatar_iv_credits_exhausted",
            }

        log_info(
            f"Avatar IV credits available: {credit_status.get('required', 0):.2f} min required, "
            f"{credit_status.get('remaining', 0):.2f} min remaining"
        )

        method_name = template.get("video_generator_method", "generate_ai_video_with_avatars")
        generator_method = getattr(self.video_generator, method_name, None)

        if not callable(generator_method):
            log_warning(
                f"Video generator missing method {method_name}; returning script-only payload"
            )
            return {
                "status": "pending_generation",
                "script": script,
            }

        try:
            kwargs = template.get("video_generator_kwargs", {})
            if "script" in generator_method.__code__.co_varnames:
                kwargs = {"script": script, **kwargs}
            else:
                kwargs = {"script_text": script.get("hook", ""), **kwargs}

            video_result = generator_method(**kwargs)
        except Exception as exc:  # pragma: no cover - defensive log path
            log_error(f"Video generation failed: {exc}")
            video_result = None

        usage_minutes = duration / 60.0
        self._record_cost(
            "heygen",
            usage_minutes,
            {"template": template["name"], "method": method_name},
        )

        # Generate custom thumbnail if video generation succeeded
        thumbnail_path = None
        if video_result and self.thumbnail_generator:
            try:
                # Get source image URL (HeyGen's thumbnail) and reel title
                source_image_url = video_result.get('thumbnail_url')
                reel_title = script.get('reel_title') or script.get('title', '')

                if source_image_url and reel_title:
                    log_info(f"Generating custom thumbnail for video with title: {reel_title}")
                    thumbnail_result = self.thumbnail_generator.generate_thumbnail(
                        image_url=source_image_url,
                        title_text=reel_title
                    )

                    if thumbnail_result.get('success'):
                        thumbnail_path = thumbnail_result.get('thumbnail_path')
                        log_info(f"Custom thumbnail generated successfully: {thumbnail_path}")
                    else:
                        log_warning(f"Thumbnail generation failed: {thumbnail_result.get('error')}")
                else:
                    if not source_image_url:
                        log_warning("No source image URL available for thumbnail generation")
                    if not reel_title:
                        log_warning("No reel title available for thumbnail generation")
            except Exception as exc:
                log_error(f"Error generating thumbnail: {exc}")

        return {
            "status": "generated" if video_result else "pending_generation",
            "script": script,
            "result": video_result,
            "duration_seconds": duration,
            "credit_status": credit_status,
            "video_source": "avatar_iv_api",  # Track that this was API-generated
            "thumbnail_path": thumbnail_path,  # Custom thumbnail path
        }

    # ------------------------------------------------------------------
    # Quality control
    # ------------------------------------------------------------------
    def _run_quality_checks(
        self, assembled_post: Dict[str, Any], template: Dict[str, Any]
    ) -> Dict[str, Any]:
        checks = {
            "character_consistency": self._check_character_consistency(assembled_post),
            "text_visual_alignment": self._check_text_visual_alignment(assembled_post),
            "brand_compliance": self._check_brand_compliance(assembled_post, template),
        }

        checks["overall_passed"] = all(
            result.get("passed", False) for result in checks.values()
        )
        return checks

    def _check_character_consistency(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        persona_name = self.character_profile.get("name", "Refiloe")
        caption_text = asset.get("content", {}).get("caption", {}).get("content", "")
        name_present = persona_name.lower() in caption_text.lower()

        image_prompts = [
            (img or {}).get("prompt", "").lower()
            for img in asset.get("assets", {}).get("images", [])
        ]
        prompt_consistent = not image_prompts or any(
            persona_name.lower() in prompt for prompt in image_prompts
        )

        return {
            "passed": name_present and prompt_consistent,
            "details": {
                "caption_has_persona": name_present,
                "images_reference_persona": prompt_consistent,
            },
        }

    def _check_text_visual_alignment(self, asset: Dict[str, Any]) -> Dict[str, Any]:
        caption = asset.get("content", {}).get("caption", {})
        caption_keywords = set(
            word.lower()
            for word in (caption.get("title", "") + " " + caption.get("content", ""))
            .replace("#", "")
            .split()
        )

        alignment_scores = []
        for image in asset.get("assets", {}).get("images", []):
            prompt = (image or {}).get("prompt", "").lower()
            overlap = caption_keywords.intersection(prompt.split())
            score = len(overlap) / max(len(prompt.split()), 1)
            alignment_scores.append(score)

        passed = True if not alignment_scores else all(score > 0.05 for score in alignment_scores)

        return {
            "passed": passed,
            "details": {
                "alignment_scores": alignment_scores,
                "keywords_checked": list(caption_keywords)[:15],
            },
        }

    def _check_brand_compliance(
        self, asset: Dict[str, Any], template: Dict[str, Any]
    ) -> Dict[str, Any]:
        tone = asset.get("content", {}).get("caption", {}).get("tone", "")
        required_tones = {trait.lower() for trait in self.character_profile.get("personality_traits", [])}
        tone_ok = not required_tones or any(trait in tone.lower() for trait in required_tones)

        hashtags = asset.get("content", {}).get("caption", {}).get("hashtags", [])
        banned_hashtags = self.config.get("facebook_settings", {}).get("hashtag_strategy", {}).get("avoid", [])
        banned_present = any(tag in banned_hashtags for tag in hashtags)

        return {
            "passed": tone_ok and not banned_present,
            "details": {
                "tone_matches_persona": tone_ok,
                "banned_hashtags_found": banned_present,
                "template": template["name"],
            },
        }

    # ------------------------------------------------------------------
    # Planning & scheduling helpers
    # ------------------------------------------------------------------
    def _build_weekly_plan(self, total_posts: int) -> List[str]:
        if total_posts <= 0:
            return []

        proportions = {
            "quick_tip_video": 0.3,
            "educational_video": 0.2,
            "image_carousel": 0.25,
            "mixed_media_post": 0.25,
        }

        counts = {
            name: max(1, int(round(total_posts * ratio)))
            for name, ratio in proportions.items()
        }

        current_total = sum(counts.values())
        priority_order = self._TEMPLATE_ORDER

        # Adjust counts to match requested total
        while current_total > total_posts:
            for name in reversed(priority_order):
                if counts[name] > 1:
                    counts[name] -= 1
                    current_total -= 1
                    if current_total == total_posts:
                        break

        while current_total < total_posts:
            for name in priority_order:
                counts[name] += 1
                current_total += 1
                if current_total == total_posts:
                    break

        plan: List[str] = []
        while len(plan) < total_posts:
            for name in priority_order:
                if counts.get(name, 0) > 0:
                    plan.append(name)
                    counts[name] -= 1
                if len(plan) == total_posts:
                    break

        return plan

    def _generate_scheduled_times(self, schedule: Dict[str, Any]) -> List[datetime]:
        posts_per_day = schedule.get("posts_per_day", 4)
        posting_times = schedule.get("posting_times") or schedule.get("times") or ["09:00"]
        total_posts = posts_per_day * 7
        start_date = date.today() + timedelta(days=1)

        scheduled_times: List[datetime] = []
        for day_offset in range(7):
            current_date = start_date + timedelta(days=day_offset)
            for time_str in posting_times[:posts_per_day]:
                hour, minute = map(int, time_str.split(":"))
                scheduled_dt = self.sa_tz.localize(
                    datetime.combine(current_date, datetime.min.time()).replace(
                        hour=hour, minute=minute
                    )
                )
                scheduled_times.append(scheduled_dt)
                if len(scheduled_times) == total_posts:
                    return scheduled_times

        return scheduled_times

    def _optimise_video_scripts(
        self, scripts: List[Dict[str, Any]], style: str
    ) -> List[Dict[str, Any]]:
        optimised = []
        for script in scripts:
            script = deepcopy(script)
            original_duration = script.get("duration", 60)
            target = min(max(original_duration, 15), 90)
            script["duration"] = target
            script["style"] = style
            optimised.append(script)
        return optimised

    # ------------------------------------------------------------------
    # Template & prompt helpers
    # ------------------------------------------------------------------
    def _select_template(
        self, post_type: str, template_name: Optional[str] = None
    ) -> Dict[str, Any]:
        if template_name and template_name in self.templates:
            return self.templates[template_name]

        candidates = [
            template
            for template in self.templates.values()
            if template["type"] == post_type
        ]
        if not candidates:
            raise ValueError(f"Unsupported post type '{post_type}'")

        return random.choice(candidates)

    def _build_templates(self) -> Dict[str, Dict[str, Any]]:
        persona = self.config.get("ai_influencer_settings", {})
        name = persona.get("name", "Refiloe")

        return {
            "quick_tip_video": {
                "name": "quick_tip_video",
                "type": "video",
                "theme": "admin_hacks",
                "format": "video_with_caption",
                "video_style": "quick_tip",
                "duration_seconds": 25,
                "hook_type": "tip_hook",
                "video_generator_method": "generate_screen_recording_tutorial",
                "video_generator_kwargs": {
                    "show_whatsapp": True,
                    "highlight_actions": True,
                },
                "thumbnail_style": "energetic",
                "needs_caption": True,
                "persona_marker": name,
                "media_type": "video",  # Tips/tutorial content
            },
            "educational_video": {
                "name": "educational_video",
                "type": "video",
                "theme": "client_management_tips",
                "format": "video_with_caption",
                "video_style": "educational",
                "duration_seconds": 75,
                "hook_type": "statistic_hook",
                "video_generator_method": "generate_animated_explainer",
                "video_generator_kwargs": {
                    "include_data_viz": True,
                    "style": "professional",
                },
                "thumbnail_style": "professional",
                "needs_caption": True,
                "persona_marker": name,
                "media_type": "video",  # Educational/tutorial content
            },
            "image_carousel": {
                "name": "image_carousel",
                "type": "carousel",
                "theme": "admin_hacks",
                "format": "carousel_style",
                "slides": 5,
                "visual_style": "educational",
                "needs_caption": True,
                "persona_marker": name,
                "media_type": "carousel",  # List/multi-tip format
            },
            "educational_carousel": {
                "name": "educational_carousel",
                "type": "carousel",
                "format": "carousel_style",
                "theme": "admin_automation_tips",
                "needs_caption": True,
                "needs_images": True,
                "slides_count": 5,
                "visual_style": "professional_beige",
                "persona_marker": name,
                "media_type": "carousel",  # Step-by-step format
            },
            "mixed_media_post": {
                "name": "mixed_media_post",
                "type": "mixed",
                "theme": "relatable_trainer_life",
                "format": "video_with_caption",
                "video_style": "story",
                "duration_seconds": 45,
                "visual_style": "casual",
                "hook_type": "story_hook",
                "video_generator_method": "generate_ai_video_with_avatars",
                "video_generator_kwargs": {
                    "avatar_style": "casual",
                    "duration": 45,
                },
                "needs_caption": True,
                "persona_marker": name,
                "media_type": "video",  # Story/narrative content
            },
            "single_image_highlight": {
                "name": "single_image_highlight",
                "type": "image",
                "theme": "client_management_tips",
                "format": "single_image_with_caption",
                "visual_style": "professional",
                "needs_caption": True,
                "persona_marker": name,
                "media_type": "static_image",  # Quote/highlight content
            },
        }

    def _build_image_prompts(
        self, template: Dict[str, Any], text_payload: Dict[str, Any]
    ) -> List[Tuple[str, str]]:
        persona_marker = template.get("persona_marker", "Refiloe")
        caption = text_payload.get("caption", {})
        key_points = caption.get("key_points") or caption.get("carousel_slides") or []
        main_message = caption.get("title") or caption.get("content", "")[:140]

        prompts: List[str] = []
        if template["type"] == "carousel":
            if not key_points:
                key_points = [
                    "Step-by-step trainer workflow",
                    "Time-saving admin hack",
                    "Client communication tip",
                    "Retention booster",
                    "Call-to-action"
                ]
            for idx, point in enumerate(key_points[: template.get("slides", 5)]):
                prompts.append(
                    f"{persona_marker} presenting slide {idx + 1}: {point}"
                )
        elif template["type"] == "video":
            script = text_payload.get("script", {})
            hook = script.get("hook", main_message)
            prompts.append(
                f"{persona_marker} dynamic thumbnail, text overlay '{hook[:40]}', energetic lighting"
            )
        elif template["type"] == "mixed":
            prompts.append(
                f"{persona_marker} sharing behind-the-scenes trainer moment, casual studio, warm lighting"
            )
        else:  # single image
            prompts.append(
                f"{persona_marker} professional trainer portrait, {main_message}, confident smile"
            )

        style = template.get("visual_style", "professional")
        return [(prompt, style) for prompt in prompts]

    def _batch_image_generation(
        self, prompt_items: List[Tuple[str, str]], template: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if not prompt_items or not self.image_generator:
            return []

        prompt_payload = [
            {"prompt": prompt, "style": style} for prompt, style in prompt_items
        ]

        if len(prompt_payload) == 1:
            result = [
                self.image_generator.generate_influencer_image(
                    prompt_payload[0]["prompt"], prompt_payload[0]["style"]
                )
            ]
        else:
            result = self.image_generator.generate_batch(prompt_payload)

        annotated_results: List[Any] = []
        for idx, res in enumerate(result):
            if isinstance(res, dict):
                payload = prompt_payload[idx] if idx < len(prompt_payload) else {}
                res.setdefault("source_prompt", payload.get("prompt"))
                res.setdefault("style", payload.get("style"))
                if payload.get("setting"):
                    res.setdefault("setting", payload.get("setting"))
                annotated_results.append(res)
            else:
                annotated_results.append(res)

        valid_results = [
            res for res in annotated_results if isinstance(res, dict) and "error" not in res
        ]

        self._record_cost(
            "flux",
            len(valid_results),
            {"template": template["name"], "batch_size": len(prompt_payload)},
        )

        return valid_results

    # ------------------------------------------------------------------
    # Cost tracking
    # ------------------------------------------------------------------
    def _initialise_cost_tracker(self) -> Dict[str, Dict[str, float]]:
        configured_costs = (
            self.config.get("cost_tracking")
            if isinstance(self.config.get("cost_tracking"), dict)
            else {}
        )

        tracker = {}
        for service, defaults in self._DEFAULT_COSTS.items():
            unit_cost = configured_costs.get(service, {}).get("unit_cost")
            if unit_cost is None:
                unit_cost = configured_costs.get(f"{service}_per_unit")
            tracker[service] = {
                "unit": defaults["unit"],
                "unit_cost": float(unit_cost or defaults["unit_cost"]),
                "usage": 0.0,
                "cost": 0.0,
            }
        return tracker

    def _record_cost(
        self, service: str, usage: float, details: Optional[Dict[str, Any]] = None
    ) -> None:
        if service not in self.cost_tracker or usage <= 0:
            return

        tracker = self.cost_tracker[service]
        cost = usage * tracker["unit_cost"]
        tracker["usage"] += usage
        tracker["cost"] += cost

        self.cost_log.append(
            {
                "timestamp": datetime.now(self.sa_tz).isoformat(),
                "service": service,
                "usage": usage,
                "cost": cost,
                "details": details or {},
            }
        )

    def _cost_summary_snapshot(self) -> Dict[str, Dict[str, float]]:
        return {service: tracker.copy() for service, tracker in self.cost_tracker.items()}

    # ------------------------------------------------------------------
    # Utilities & bookkeeping
    # ------------------------------------------------------------------
    def _estimate_token_usage(self, text: str) -> int:
        if not text:
            return 0
        words = text.split()
        approximate_tokens = math.ceil(len(words) * 1.3)
        return approximate_tokens

    def _combine_assets(
        self,
        post_type: str,
        template: Dict[str, Any],
        text_payload: Dict[str, Any],
        visual_assets: List[Dict[str, Any]],
        video_assets: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        asset_id = metadata.get("asset_id") or os.urandom(6).hex()

        # Handle carousel type with multiple image URLs
        if post_type == "carousel" and visual_assets:
            # Extract all slide paths for media_urls (comma-separated or JSON array)
            media_urls = [
                asset.get("image_url") or asset.get("local_path")
                for asset in visual_assets
                if isinstance(asset, dict) and (asset.get("image_url") or asset.get("local_path"))
            ]
            slide_count = len(media_urls)

            combined = {
                "id": asset_id,
                "type": "carousel",
                "post_type": "carousel",
                "template": template["name"],
                "content": {
                    "caption": text_payload.get("caption"),
                    "script": text_payload.get("script"),
                },
                "assets": {
                    "images": visual_assets,
                    "video": video_assets,
                },
                # Store media_urls as JSON array for database storage
                "media_urls": media_urls,
                "media_urls_json": ",".join(media_urls) if media_urls else "",
                "metadata": {
                    "generated_at": datetime.now(self.sa_tz).isoformat(),
                    "persona": self.character_profile.get("name", "Refiloe"),
                    "slide_count": slide_count,
                    "post_type": "carousel",
                    **metadata,
                },
            }
            return combined

        combined = {
            "id": asset_id,
            "type": post_type,
            "template": template["name"],
            "content": {
                "caption": text_payload.get("caption"),
                "script": text_payload.get("script"),
            },
            "assets": {
                "images": visual_assets,
                "video": video_assets,
            },
            "metadata": {
                "generated_at": datetime.now(self.sa_tz).isoformat(),
                "persona": self.character_profile.get("name", "Refiloe"),
                **metadata,
            },
        }
        return combined

    def _register_asset(self, asset: Dict[str, Any]) -> None:
        self.asset_registry.append(asset)
        if len(self.asset_registry) > 200:
            self.asset_registry = self.asset_registry[-200:]

    def _resolve_config_path(self, candidate: str) -> str:
        search_paths = [
            candidate,
            os.path.join(os.path.dirname(__file__), "config.yaml"),
            os.path.join(os.getcwd(), "config.yaml"),
        ]
        for path in search_paths:
            if path and os.path.exists(path):
                return path
        raise FileNotFoundError(
            f"Unable to locate configuration file. Tried: {', '.join(search_paths)}"
        )

    def _load_config(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def _init_content_generator(
        self, config_path: str, supabase_client: Any
    ) -> ContentGenerator:
        try:
            return ContentGenerator(config_path, supabase_client)
        except Exception as exc:  # pragma: no cover - defensive log path
            log_error(f"Failed to initialise ContentGenerator: {exc}")
            raise

    def _init_image_generator(
        self, config_path: str, supabase_client: Any
    ) -> Optional[ImageGenerator]:
        try:
            return ImageGenerator(config_path, supabase_client)
        except Exception as exc:
            log_warning(f"ImageGenerator unavailable: {exc}")
            return None

    def _init_video_generator(
        self, config_path: str, supabase_client: Any
    ) -> Optional[VideoGenerator]:
        try:
            return VideoGenerator(config_path, supabase_client)
        except Exception as exc:
            log_warning(f"VideoGenerator unavailable: {exc}")
            return None

    def _init_carousel_generator(
        self, config_path: str, supabase_client=None
    ) -> Optional[CarouselTemplateGenerator]:
        try:
            return CarouselTemplateGenerator(config_path, supabase_client=supabase_client)
        except Exception as exc:
            log_warning(f"CarouselTemplateGenerator unavailable: {exc}")
            return None

    def _init_thumbnail_generator(self) -> Optional[ThumbnailGenerator]:
        try:
            return ThumbnailGenerator()
        except Exception as exc:
            log_warning(f"ThumbnailGenerator unavailable: {exc}")
            return None

    def _resolve_launch_date(self) -> date:
        launch_str = self.config.get("launch_date")
        if launch_str:
            try:
                return datetime.strptime(launch_str, "%Y-%m-%d").date()
            except ValueError:
                log_warning("Invalid launch_date in config, defaulting to 2024-01-01")
        return date(2024, 1, 1)

    def _calculate_week_number(self) -> int:
        today = datetime.now(self.sa_tz).date()
        delta_days = (today - self.launch_date).days
        return max(1, delta_days // 7 + 1)


__all__ = ["ContentPipeline"]

