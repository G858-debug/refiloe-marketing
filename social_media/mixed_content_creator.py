"""Mixed Content Creator
=================================

Generates multi-format social media assets that blend avatars, text overlays,
and motion graphics. The module orchestrates HeyGen avatar narration with
Shotstack or Remotion rendering pipelines to create campaign-ready before/after
videos, carousel-style explainers, interactive tutorials, and motivational
reels. Each content package is saved to Supabase and scheduled automatically
via the `MixedContentCreator.schedule_variants` helper.

Key capabilities:
- Combine HeyGen avatar clips with dynamic templates
- Add captions, text overlays, transitions, and background music
- Support template-based renders across 1:1, 9:16, and 16:9 aspect ratios
- Inject engagement elements (CTA overlays, polls, hashtag suggestions)
- Integrate with the social media scheduler for automated deployment
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytz
import requests

from utils.logger import log_error, log_info, log_warning
from database import SocialMediaDatabase


@dataclass
class RenderResult:
    """Represents the response returned by a rendering provider."""

    render_job_id: str
    status: str
    preview_url: Optional[str]
    webhook_url: Optional[str]


class MixedContentCreator:
    """Generate mixed-media content packages using template-driven video renders."""

    ASPECT_RATIO_PRESETS: Dict[str, Dict[str, Any]] = {
        "1:1": {
            "resolution": {"width": 1080, "height": 1080},
            "platform": "instagram",
            "default_offset_hours": 2,
        },
        "9:16": {
            "resolution": {"width": 1080, "height": 1920},
            "platform": "instagram_reels",
            "default_offset_hours": 3,
        },
        "16:9": {
            "resolution": {"width": 1920, "height": 1080},
            "platform": "youtube",
            "default_offset_hours": 5,
        },
    }

    DEFAULT_CALL_TO_ACTIONS: Dict[str, List[str]] = {
        "before_after": [
            "Comment 'TRANSFORM' for the full client plan",
            "Save this for your next client transformation",
            "Tag a fellow trainer who needs this reminder",
        ],
        "tips": [
            "Share this with a trainer who needs it",
            "Which tip will you try first? Comment below",
            "Follow for more trainer hacks every day",
        ],
        "tutorial": [
            "Pause and follow along step-by-step",
            "Drop a ? when you've tested this workflow",
            "DM me 'SYSTEM' for the automation checklist",
        ],
        "motivational": [
            "Repeat this to yourself today ? you've got this",
            "Tag a trainer who's grinding with you",
            "Double tap if you're committing to the grind",
        ],
    }

    DEFAULT_HASHTAGS: Dict[str, List[str]] = {
        "transformation": [
            "#TrainerTransformation",
            "#ClientWins",
            "#BeforeAfter",
            "#FitnessCoach",
            "#RefiloeAI",
        ],
        "tips": [
            "#TrainerTips",
            "#AdminHacks",
            "#TrainerTools",
            "#SocialMediaForTrainers",
            "#FitnessBusiness",
        ],
        "tutorial": [
            "#TrainerWorkflow",
            "#AutomationTips",
            "#TrainerSystems",
            "#FitnessAutomation",
            "#GymOwnerLife",
        ],
        "motivational": [
            "#TrainerMindset",
            "#MotivationMonday",
            "#KeepCoaching",
            "#RefiloeNation",
            "#FitnessCommunity",
        ],
    }

    DEFAULT_POLL_TEMPLATES: Dict[str, Dict[str, Any]] = {
        "before_after": {
            "question": "Want the full plan?",
            "options": ["Yes, send it", "I'll start today", "Need accountability"],
        },
        "tips": {
            "question": "Which tip should we deep dive next?",
            "options": ["Lead gen", "Client retention", "Automation"],
        },
        "tutorial": {
            "question": "How confident are you after this walkthrough?",
            "options": ["Ready to implement", "Need more support", "Still testing"],
        },
        "motivational": {
            "question": "What keeps you consistent?",
            "options": ["Client wins", "Future self", "Community"],
        },
    }

    def __init__(
        self,
        config_path: str,
        supabase_client: Any,
        renderer_provider: Optional[str] = None,
    ) -> None:
        self.config_path = config_path
        self.supabase_client = supabase_client
        self.db = SocialMediaDatabase(supabase_client)
        self.sa_tz = pytz.timezone("Africa/Johannesburg")

        self.config: Dict[str, Any] = self._load_config()

        # Rendering providers
        self.renderer_provider = (renderer_provider or os.getenv("VIDEO_RENDERER_PROVIDER", "shotstack")).lower()
        self.shotstack_api_key = os.getenv("SHOTSTACK_API_KEY")
        self.shotstack_host = os.getenv("SHOTSTACK_API_HOST", "https://api.shotstack.io/stage")
        self.remotion_endpoint = os.getenv("REMOTION_RENDER_URL")

        # Avatar generation
        self.heygen_api_key = os.getenv("HEYGEN_API_KEY")
        self.heygen_host = os.getenv("HEYGEN_API_HOST", "https://api.heygen.com/v1")

        # Default trainer
        self.default_trainer_id = self.config.get("default_trainer_id", "refiloe_ai")

        log_info(
            "MixedContentCreator initialized | renderer=%s | heygen=%s | trainer=%s"
            % (
                self.renderer_provider,
                "enabled" if self.heygen_api_key else "disabled",
                self.default_trainer_id,
            )
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create_before_after_comparison(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a transformation story leveraging avatar narration and overlays."""

        log_info("Starting before/after comparison build")

        try:
            storyboard = self._prepare_storyboard("before_after", data)
            overlays = self._prepare_cta_overlays("before_after", data)
            poll = self._prepare_poll("before_after", data)
            hashtags = self._suggest_hashtags("transformation", data)

            variants = self._render_video_variants(
                template_id=storyboard["template_id"],
                storyboard=storyboard,
                overlays=overlays,
                music_track=data.get("music_track") or self.config.get("default_music", {}).get("motivational"),
            )

            scheduled_posts = self._schedule_variants(
                variants=variants,
                caption_base=storyboard["caption"],
                campaign_code="before_after_comparison",
                hashtags=hashtags,
                poll=poll,
            )

            return {
                "success": True,
                "campaign": "before_after_comparison",
                "variants": variants,
                "scheduled_posts": scheduled_posts,
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            log_error(f"Failed to create before/after comparison: {exc}")
            return {"success": False, "error": str(exc)}

    def create_tips_carousel_video(self, tips_list: List[str]) -> Dict[str, Any]:
        """Convert a list of tips into a carousel-inspired vertical video."""

        log_info(f"Building tips carousel video from {len(tips_list)} tips")

        if not tips_list:
            return {"success": False, "error": "tips_list cannot be empty"}

        try:
            data = {
                "slides": tips_list,
                "headline": tips_list[0] if tips_list else "Trainer Tips",
            }
            storyboard = self._prepare_storyboard("tips", data)
            overlays = self._prepare_cta_overlays("tips", data)
            poll = self._prepare_poll("tips", data)
            hashtags = self._suggest_hashtags("tips", data)

            variants = self._render_video_variants(
                template_id=storyboard["template_id"],
                storyboard=storyboard,
                overlays=overlays,
                music_track=self.config.get("default_music", {}).get("upbeat"),
            )

            scheduled_posts = self._schedule_variants(
                variants=variants,
                caption_base=storyboard["caption"],
                campaign_code="tips_carousel_video",
                hashtags=hashtags,
                poll=poll,
            )

            return {
                "success": True,
                "campaign": "tips_carousel_video",
                "variants": variants,
                "scheduled_posts": scheduled_posts,
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            log_error(f"Failed to create tips carousel video: {exc}")
            return {"success": False, "error": str(exc)}

    def create_tutorial_with_avatar(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a narrated tutorial that highlights each workflow step."""

        log_info(f"Generating tutorial with {len(steps)} steps")

        if not steps:
            return {"success": False, "error": "steps cannot be empty"}

        try:
            data = {"steps": steps, "headline": steps[0].get("title", "Trainer Tutorial")}
            storyboard = self._prepare_storyboard("tutorial", data)
            overlays = self._prepare_cta_overlays("tutorial", data)
            poll = self._prepare_poll("tutorial", data)
            hashtags = self._suggest_hashtags("tutorial", data)

            variants = self._render_video_variants(
                template_id=storyboard["template_id"],
                storyboard=storyboard,
                overlays=overlays,
                music_track=self.config.get("default_music", {}).get("focus"),
            )

            scheduled_posts = self._schedule_variants(
                variants=variants,
                caption_base=storyboard["caption"],
                campaign_code="tutorial_with_avatar",
                hashtags=hashtags,
                poll=poll,
            )

            return {
                "success": True,
                "campaign": "tutorial_with_avatar",
                "variants": variants,
                "scheduled_posts": scheduled_posts,
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            log_error(f"Failed to create tutorial with avatar: {exc}")
            return {"success": False, "error": str(exc)}

    def create_motivational_reel(self, script: Dict[str, Any], music_track: Optional[str]) -> Dict[str, Any]:
        """Create a motivational reel with avatar narration and dynamic pacing."""

        log_info(f"Creating motivational reel titled '{script.get('title', 'Motivational Reel')}'")

        if not script.get("script"):
            return {"success": False, "error": "script must include a 'script' key with sections"}

        try:
            data = dict(script)
            storyboard = self._prepare_storyboard("motivational", data)
            overlays = self._prepare_cta_overlays("motivational", data)
            poll = self._prepare_poll("motivational", data)
            hashtags = self._suggest_hashtags("motivational", data)

            variants = self._render_video_variants(
                template_id=storyboard["template_id"],
                storyboard=storyboard,
                overlays=overlays,
                music_track=music_track
                or script.get("music_track")
                or self.config.get("default_music", {}).get("motivational"),
            )

            scheduled_posts = self._schedule_variants(
                variants=variants,
                caption_base=storyboard["caption"],
                campaign_code="motivational_reel",
                hashtags=hashtags,
                poll=poll,
            )

            return {
                "success": True,
                "campaign": "motivational_reel",
                "variants": variants,
                "scheduled_posts": scheduled_posts,
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            log_error(f"Failed to create motivational reel: {exc}")
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_config(self) -> Dict[str, Any]:
        try:
            import yaml

            with open(self.config_path, "r", encoding="utf-8") as cfg:
                config = yaml.safe_load(cfg)
                log_info(f"MixedContentCreator config loaded from {self.config_path}")
                return config or {}
        except FileNotFoundError:
            log_warning(f"MixedContentCreator config {self.config_path} not found. Using defaults")
        except Exception as exc:  # pragma: no cover - defensive logging
            log_warning(f"Unable to read MixedContentCreator config: {exc}")

        return {
            "default_music": {
                "motivational": "https://cdn.refiloe.ai/audio/motivational_mix.mp3",
                "upbeat": "https://cdn.refiloe.ai/audio/upbeat_training_mix.mp3",
                "focus": "https://cdn.refiloe.ai/audio/focus_instrumental.mp3",
            },
            "templates": {
                "before_after": "trainer-before-after-template",
                "tips": "trainer-tips-carousel-template",
                "tutorial": "trainer-workflow-tutorial-template",
                "motivational": "trainer-motivation-reel-template",
            },
            "default_trainer_id": "refiloe_ai",
        }

    def _prepare_storyboard(self, content_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        template_map = self.config.get("templates", {})
        template_id = template_map.get(content_type, f"refiloe-{content_type}-template")

        caption = data.get("caption") or self._build_default_caption(content_type, data)

        script_sections = self._extract_script_sections(content_type, data)
        avatar_clips = self._generate_avatar_clips(script_sections, data.get("avatar_voice"))

        segments = self._build_segments(content_type, data, avatar_clips)

        return {
            "template_id": template_id,
            "caption": caption,
            "segments": segments,
            "script_sections": script_sections,
            "avatar_clips": avatar_clips,
            "duration": sum(segment.get("length", 4) for segment in segments),
        }

    def _build_segments(
        self,
        content_type: str,
        data: Dict[str, Any],
        avatar_clips: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        segments: List[Dict[str, Any]] = []

        if content_type == "before_after":
            segments.extend(
                [
                    {
                        "type": "image",
                        "src": data.get("before_media")
                        or self.config.get("placeholders", {}).get("before"),
                        "length": 3,
                        "overlay_text": data.get("before_label", "Before"),
                        "transition": "fade",
                    },
                    {
                        "type": "image",
                        "src": data.get("after_media")
                        or self.config.get("placeholders", {}).get("after"),
                        "length": 3,
                        "overlay_text": data.get("after_label", "After"),
                        "transition": "zoomIn",
                    },
                ]
            )

            if data.get("metrics"):
                metrics_text = " | ".join(f"{k}: {v}" for k, v in data["metrics"].items())
                segments.append(
                    {
                        "type": "title",
                        "text": metrics_text,
                        "length": 4,
                        "transition": "slideUp",
                    }
                )

        elif content_type == "tips":
            for idx, tip in enumerate(data.get("slides", []), start=1):
                segments.append(
                    {
                        "type": "title",
                        "text": f"Tip {idx}: {tip}",
                        "length": 4,
                        "transition": "slideLeft" if idx % 2 else "slideRight",
                    }
                )

        elif content_type == "tutorial":
            for step_number, step in enumerate(data.get("steps", []), start=1):
                segments.append(
                    {
                        "type": "title",
                        "text": f"Step {step_number}: {step.get('title', 'Step')}\n{step.get('instruction', '')}",
                        "length": step.get("duration", 6),
                        "transition": "morph",
                    }
                )
                if step.get("screenshot_url"):
                    segments.append(
                        {
                            "type": "image",
                            "src": step["screenshot_url"],
                            "length": max(4, step.get("duration", 6) - 2),
                            "transition": "fade",
                        }
                    )

        elif content_type == "motivational":
            for section in data.get("script", []):
                segments.append(
                    {
                        "type": "title",
                        "text": section.get("text", ""),
                        "length": section.get("duration", 4),
                        "transition": "fade",
                    }
                )

        # Append avatar clips as separate segments for compositing order
        for clip in avatar_clips:
            segments.append(
                {
                    "type": "avatar",
                    "src": clip.get("url"),
                    "length": clip.get("length", 6),
                    "transition": "fade",
                }
            )

        return segments

    def _prepare_cta_overlays(self, content_type: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        ctas = self.DEFAULT_CALL_TO_ACTIONS.get(content_type, [])
        selected = data.get("cta_overlays") or ctas[:2]

        overlays: List[Dict[str, Any]] = []
        start_time = 1.5

        for text in selected:
            overlays.append(
                {
                    "text": text,
                    "start": start_time,
                    "length": 3.5,
                    "position": "bottom",
                    "style": "cta-pill",
                }
            )
            start_time += 4

        return overlays

    def _prepare_poll(self, content_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(data.get("poll"), dict):
            return data["poll"]
        template = self.DEFAULT_POLL_TEMPLATES.get(content_type, {}).copy()
        if not template:
            template = {
                "question": "What do you want next?",
                "options": ["More tips", "Full tutorial", "Client stories"],
            }
        return template

    def _suggest_hashtags(self, theme: str, data: Dict[str, Any]) -> List[str]:
        custom = data.get("hashtags")
        if custom:
            return custom

        suggested = self.DEFAULT_HASHTAGS.get(theme, [])
        extras = data.get("extra_hashtags") or []

        return list(dict.fromkeys(suggested + extras))[:8]

    def _extract_script_sections(self, content_type: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        if content_type == "tutorial":
            sections = []
            for step in data.get("steps", []):
                sections.append(
                    {
                        "text": step.get("voiceover")
                        or step.get("instruction", "Explain this step"),
                        "duration": step.get("duration", 6),
                    }
                )
            return sections

        if content_type == "tips":
            return [
                {
                    "text": tip,
                    "duration": 4,
                }
                for tip in data.get("slides", [])
            ]

        if content_type == "motivational":
            return data.get("script", [])

        if content_type == "before_after":
            script = data.get("script")
            if isinstance(script, list):
                return script
            default_narration = [
                {
                    "text": "You are looking at a trainer who refused to settle.",
                    "duration": 4,
                },
                {
                    "text": "From missed sessions to a fully booked roster.",
                    "duration": 4,
                },
                {
                    "text": "Here's exactly what changed.",
                    "duration": 4,
                },
            ]
            if isinstance(script, dict):
                default_narration[0]["text"] = script.get("intro", default_narration[0]["text"])
                default_narration[1]["text"] = script.get("pivot", default_narration[1]["text"])
                default_narration[2]["text"] = script.get("cta", default_narration[2]["text"])
            return default_narration

        return data.get("script", [])

    def _build_default_caption(self, content_type: str, data: Dict[str, Any]) -> str:
        if content_type == "before_after":
            return (
                f"Before ?? After: {data.get('headline', 'Trainer transformation')}\n"
                "Here are the systems we optimized and the results our trainer achieved."
            )
        if content_type == "tips":
            return (
                f"{data.get('headline', 'Trainer tips you need right now')}\n"
                "Swipe through these rapid-fire admin wins and tell me which one you're testing today."
            )
        if content_type == "tutorial":
            return (
                f"Step-by-step: {data.get('headline', 'Trainer workflow')}\n"
                "Follow along and comment ? once you've implemented this."
            )
        if content_type == "motivational":
            return (
                f"{data.get('title', 'Your daily coaching reminder')}\n"
                "Play this whenever you need proof you're building something special."
            )
        return "Refiloe mixed media drop"

    def _render_video_variants(
        self,
        template_id: str,
        storyboard: Dict[str, Any],
        overlays: List[Dict[str, Any]],
        music_track: Optional[str],
    ) -> Dict[str, Dict[str, Any]]:
        variants: Dict[str, Dict[str, Any]] = {}

        for aspect_ratio, preset in self.ASPECT_RATIO_PRESETS.items():
            payload = self._build_renderer_payload(
                template_id=template_id,
                storyboard=storyboard,
                overlays=overlays,
                aspect_ratio=aspect_ratio,
                resolution=preset["resolution"],
                music_track=music_track,
            )

            render_response = self._dispatch_render_job(payload)

            variants[aspect_ratio] = {
                "render_job_id": render_response.render_job_id,
                "status": render_response.status,
                "preview_url": render_response.preview_url,
                "webhook_url": render_response.webhook_url,
                "caption": storyboard["caption"],
                "aspect_ratio": aspect_ratio,
                "template_id": template_id,
                "duration": storyboard.get("duration"),
                "platform": preset.get("platform"),
            }

        return variants

    def _build_renderer_payload(
        self,
        template_id: str,
        storyboard: Dict[str, Any],
        overlays: List[Dict[str, Any]],
        aspect_ratio: str,
        resolution: Dict[str, int],
        music_track: Optional[str],
    ) -> Dict[str, Any]:
        if self.renderer_provider == "remotion":
            return self._build_remotion_payload(
                template_id, storyboard, overlays, aspect_ratio, resolution, music_track
            )
        return self._build_shotstack_payload(
            template_id, storyboard, overlays, aspect_ratio, resolution, music_track
        )

    def _build_shotstack_payload(
        self,
        template_id: str,
        storyboard: Dict[str, Any],
        overlays: List[Dict[str, Any]],
        aspect_ratio: str,
        resolution: Dict[str, int],
        music_track: Optional[str],
    ) -> Dict[str, Any]:
        track_clips = self._compose_track_clips(storyboard, overlays)

        timeline = {
            "background": "#000000",
            "tracks": [{"clips": track_clips}],
        }
        if music_track:
            timeline["soundtrack"] = {"src": music_track}

        return {
            "templateId": template_id,
            "timeline": timeline,
            "output": {
                "format": "mp4",
                "resolution": f"{resolution['width']}x{resolution['height']}",
                "aspectRatio": aspect_ratio,
            },
            "meta": {
                "campaign": template_id,
                "generatedAt": datetime.now(self.sa_tz).isoformat(),
            },
        }

    def _build_remotion_payload(
        self,
        template_id: str,
        storyboard: Dict[str, Any],
        overlays: List[Dict[str, Any]],
        aspect_ratio: str,
        resolution: Dict[str, int],
        music_track: Optional[str],
    ) -> Dict[str, Any]:
        total_duration = storyboard.get("duration", 45)
        fps = 30

        input_props = {
            "segments": storyboard.get("segments"),
            "overlays": overlays,
            "musicTrack": music_track,
            "avatarClips": storyboard.get("avatar_clips"),
            "caption": storyboard.get("caption"),
        }

        return {
            "composition": template_id,
            "inputProps": input_props,
            "codec": "h264",
            "durationInFrames": int(total_duration * fps),
            "fps": fps,
            "dimensions": {
                "width": resolution["width"],
                "height": resolution["height"],
            },
            "metadata": {
                "aspectRatio": aspect_ratio,
                "generatedAt": datetime.now(self.sa_tz).isoformat(),
            },
        }

    def _compose_track_clips(self, storyboard: Dict[str, Any], overlays: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        clips: List[Dict[str, Any]] = []
        current_start = 0.0

        for segment in storyboard.get("segments", []):
            length = segment.get("length", 4)
            clip: Dict[str, Any] = {
                "asset": {},
                "start": current_start,
                "length": length,
                "transition": {"in": segment.get("transition", "fade")},
            }

            if segment["type"] == "image":
                clip["asset"].update({"type": "image", "src": segment.get("src")})
                if segment.get("overlay_text"):
                    clip["animations"] = [
                        {
                            "type": "zoomIn",
                            "start": current_start,
                            "length": length,
                        }
                    ]
                    clip.setdefault("filters", []).append({"type": "contrast", "strength": 0.1})
            elif segment["type"] == "avatar":
                clip["asset"].update({"type": "video", "src": segment.get("src")})
                clip["transition"] = {"in": "crossfade"}
                clip.setdefault("filters", []).append({"type": "warm", "strength": 0.1})
            else:  # title
                clip["asset"].update(
                    {
                        "type": "title",
                        "text": segment.get("text"),
                        "style": "subtitle",
                    }
                )

            clips.append(clip)
            current_start += length

        for overlay in overlays:
            clips.append(
                {
                    "asset": {
                        "type": "title",
                        "text": overlay["text"],
                        "style": overlay.get("style", "cta-pill"),
                        "position": overlay.get("position", "bottom"),
                    },
                    "start": overlay.get("start", 0),
                    "length": overlay.get("length", 3),
                }
            )

        return clips

    def _dispatch_render_job(self, payload: Dict[str, Any]) -> RenderResult:
        if self.renderer_provider == "remotion":
            return self._render_with_remotion(payload)
        return self._render_with_shotstack(payload)

    def _render_with_shotstack(self, payload: Dict[str, Any]) -> RenderResult:
        if not self.shotstack_api_key:
            log_warning("SHOTSTACK_API_KEY missing. Returning mock render response")
            return self._mock_render_response()

        try:
            response = requests.post(
                f"{self.shotstack_host}/render",
                headers={
                    "x-api-key": self.shotstack_api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            render_id = data.get("response", {}).get("id") or data.get("id") or str(uuid.uuid4())
            return RenderResult(
                render_job_id=render_id,
                status=data.get("status", "queued"),
                preview_url=data.get("response", {}).get("url"),
                webhook_url=data.get("response", {}).get("webhook"),
            )
        except requests.RequestException as exc:
            log_error(f"Shotstack render failed: {exc}")
            return self._mock_render_response(status="failed")

    def _render_with_remotion(self, payload: Dict[str, Any]) -> RenderResult:
        if not self.remotion_endpoint:
            log_warning("REMOTION_RENDER_URL missing. Returning mock render response")
            return self._mock_render_response()

        try:
            response = requests.post(
                self.remotion_endpoint,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            render_id = data.get("renderId") or str(uuid.uuid4())
            return RenderResult(
                render_job_id=render_id,
                status=data.get("status", "queued"),
                preview_url=data.get("url"),
                webhook_url=data.get("webhookUrl"),
            )
        except requests.RequestException as exc:
            log_error(f"Remotion render failed: {exc}")
            return self._mock_render_response(status="failed")

    def _mock_render_response(self, status: str = "queued") -> RenderResult:
        render_id = f"mock-{uuid.uuid4()}"
        preview_url = f"https://cdn.refiloe.ai/mock/{render_id}.mp4"
        return RenderResult(
            render_job_id=render_id,
            status=status,
            preview_url=preview_url,
            webhook_url=None,
        )

    def _generate_avatar_clips(
        self,
        script_sections: List[Dict[str, Any]],
        avatar_voice: Optional[str],
    ) -> List[Dict[str, Any]]:
        if not script_sections:
            return []

        if not self.heygen_api_key:
            log_warning("HEYGEN_API_KEY missing. Using placeholder avatar clips")
            return [
                {
                    "url": f"https://cdn.refiloe.ai/mock-avatars/{idx}.mp4",
                    "length": section.get("duration", 6),
                }
                for idx, section in enumerate(script_sections, start=1)
            ]

        generated_clips: List[Dict[str, Any]] = []

        for idx, section in enumerate(script_sections, start=1):
            try:
                payload = {
                    "voice": avatar_voice or self.config.get("default_avatar_voice", "alloy"),
                    "script": section.get("text", ""),
                    "background": "green",
                }
                response = requests.post(
                    f"{self.heygen_host}/video.generate",
                    headers={"X-API-KEY": self.heygen_api_key, "Content-Type": "application/json"},
                    json=payload,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json().get("data", {})
                video_id = data.get("video_id") or data.get("id")
                clip_url = self._poll_heygen_job(video_id)
                generated_clips.append({"url": clip_url, "length": section.get("duration", 6)})
            except requests.RequestException as exc:
                log_warning(f"HeyGen clip generation failed for section {idx}: {exc}")
                generated_clips.append(
                    {
                        "url": f"https://cdn.refiloe.ai/mock-avatars/{idx}.mp4",
                        "length": section.get("duration", 6),
                    }
                )

        return generated_clips

    def _poll_heygen_job(self, video_id: Optional[str], timeout: int = 120) -> str:
        if not video_id:
            return f"https://cdn.refiloe.ai/mock-avatars/{uuid.uuid4()}.mp4"

        elapsed = 0
        polling_interval = 6

        while elapsed < timeout:
            try:
                response = requests.get(
                    f"{self.heygen_host}/video.status/{video_id}",
                    headers={"X-API-KEY": self.heygen_api_key},
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json().get("data", {})
                status = data.get("status")
                if status == "completed":
                    return data.get("video_url") or data.get("url")
                if status == "failed":
                    log_warning(f"HeyGen video {video_id} failed")
                    break
            except requests.RequestException as exc:
                log_warning(f"HeyGen polling error for {video_id}: {exc}")
                break

            time.sleep(polling_interval)
            elapsed += polling_interval

        log_warning(f"HeyGen polling timeout for {video_id}. Using placeholder clip")
        return f"https://cdn.refiloe.ai/mock-avatars/{video_id or uuid.uuid4()}.mp4"

    def _schedule_variants(
        self,
        variants: Dict[str, Dict[str, Any]],
        caption_base: str,
        campaign_code: str,
        hashtags: List[str],
        poll: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        scheduled_posts: List[Dict[str, Any]] = []
        now_sa = datetime.now(self.sa_tz)

        for aspect_ratio, variant in variants.items():
            offset_hours = self.ASPECT_RATIO_PRESETS[aspect_ratio]["default_offset_hours"]
            scheduled_time = now_sa + timedelta(hours=offset_hours)
            caption = self._compose_caption(caption_base, hashtags, poll)

            metadata = {
                "campaign": campaign_code,
                "render_job_id": variant["render_job_id"],
                "render_status": variant["status"],
                "preview_url": variant.get("preview_url"),
                "webhook_url": variant.get("webhook_url"),
                "aspect_ratio": aspect_ratio,
                "hashtags": hashtags,
                "poll": poll,
            }

            post_payload = {
                "content": caption,
                "platform": variant.get("platform", "facebook"),
                "scheduled_time": scheduled_time.isoformat(),
                "status": "scheduled",
                "trainer_id": self.default_trainer_id,
                "template_id": variant.get("template_id"),
                "metadata": metadata,
            }

            post_id = self.db.save_post(post_payload)

            scheduled_posts.append(
                {
                    "post_id": post_id,
                    "scheduled_time": scheduled_time.isoformat(),
                    "platform": post_payload["platform"],
                    "aspect_ratio": aspect_ratio,
                    "render_job_id": variant["render_job_id"],
                }
            )

        log_info(
            f"Scheduled {len(scheduled_posts)} mixed media posts for campaign {campaign_code}"
        )
        return scheduled_posts

    def _compose_caption(self, caption_base: str, hashtags: List[str], poll: Dict[str, Any]) -> str:
        hashtag_block = " ".join(hashtags)
        poll_prompt = poll.get("question") if poll else ""
        return f"{caption_base}\n\n{poll_prompt}\n\n{hashtag_block}".strip()


__all__ = ["MixedContentCreator"]
