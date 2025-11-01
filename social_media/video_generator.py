"""HeyGen-powered video generator for social media automation."""

from __future__ import annotations

import os
import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz
import requests
import yaml

from utils.logger import log_debug, log_error, log_info, log_warning


HEYGEN_API_BASE_URL = "https://api.heygen.com/v2"


class UsageLimitExceeded(Exception):
    """Raised when the HeyGen monthly quota has been reached."""


class VideoGenerationError(Exception):
    """Raised when HeyGen video generation fails."""


class VideoGenerator:
    """Generate talking avatar videos via HeyGen and manage avatar settings."""

    def __init__(self, config_path: str, supabase_client):
        self.config_path = config_path
        self.supabase_client = supabase_client

        self.api_key = os.getenv("HEYGEN_API_KEY")
        if not self.api_key:
            raise ValueError("HEYGEN_API_KEY environment variable is required")

        self.default_avatar_id = os.getenv("HEYGEN_AVATAR_ID")
        self.monthly_limit = int(os.getenv("HEYGEN_MONTHLY_LIMIT", "120"))

        self.sa_tz = pytz.timezone("Africa/Johannesburg")
        self.max_retries = 5
        self.retry_backoff = 5
        self.poll_interval = 10
        self.poll_timeout = int(os.getenv("HEYGEN_POLL_TIMEOUT", "420"))

        self.usage_table = os.getenv("HEYGEN_USAGE_TABLE", "video_generation_usage")
        self.video_table = os.getenv("HEYGEN_VIDEO_TABLE", "generated_videos")

        self.config = self._load_config(config_path)
        self.style_presets = self._build_style_presets()

        log_info("VideoGenerator initialized with HeyGen integration")

    # ------------------------------------------------------------------
    # Public API

    def generate_avatar_video(
        self,
        script_text: str,
        avatar_id: str,
        voice_id: str,
        *,
        style: str = "educational",
        background_music: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a talking avatar video using HeyGen.

        Args:
            script_text: Full narration script that will be chunked for pacing.
            avatar_id: HeyGen avatar identifier.
            voice_id: HeyGen voice identifier.
            style: Content style preset (educational, motivational, tips, etc.).
            background_music: Whether to include background music.
            metadata: Optional metadata to persist with the video record.

        Returns:
            Dict with video metadata including video_url on success.
        """

        log_info("Starting HeyGen avatar video generation")
        self._ensure_within_limit()

        style_settings = self._resolve_style(style)
        chunk_char_limit = style_settings.get("chunk_char_limit", 480)
        script_chunks = self._chunk_script(script_text, limit=chunk_char_limit)

        if not script_chunks:
            raise ValueError("Script text is empty after processing")

        payload = self._build_generate_payload(
            avatar_id=avatar_id,
            voice_id=voice_id,
            style_settings=style_settings,
            script_chunks=script_chunks,
            background_music=background_music,
            metadata=metadata or {},
        )

        log_debug(f"HeyGen payload prepared with {len(script_chunks)} chunks")

        response = self._post_with_retry("/video/generate", json=payload)
        video_id = (
            response.get("data", {}).get("video_id")
            or response.get("video_id")
            or response.get("task_id")
        )

        if not video_id:
            raise VideoGenerationError("HeyGen response did not include a video identifier")

        log_info(f"HeyGen video request accepted (video_id={video_id})")

        video_data = self._poll_video_status(video_id)

        if video_data.get("status") != "completed":
            self._record_usage(video_id, success=False, style=style)
            raise VideoGenerationError(
                f"Video generation failed with status: {video_data.get('status')}"
            )

        video_url = video_data.get("video_url")
        if not video_url:
            self._record_usage(video_id, success=False, style=style)
            raise VideoGenerationError("HeyGen completed without returning a video URL")

        self._record_usage(
            video_id,
            success=True,
            style=style,
            duration_seconds=video_data.get("duration"),
        )

        self._store_video_record(
            video_id=video_id,
            video_data=video_data,
            script_chunks=script_chunks,
            avatar_id=avatar_id,
            voice_id=voice_id,
            style=style,
            background_music=background_music,
            metadata=metadata or {},
        )

        result = {
            "video_id": video_id,
            "video_url": video_url,
            "thumbnail_url": video_data.get("thumbnail_url"),
            "status": video_data.get("status"),
            "duration": video_data.get("duration"),
            "style": style,
            "avatar_id": avatar_id,
            "voice_id": voice_id,
            "script_chunks": script_chunks,
        }

        log_info(f"HeyGen video generation complete: {video_url}")
        return result

    def list_available_avatars(self) -> List[Dict[str, Any]]:
        """Return the available HeyGen avatars for the account."""

        response = self._get_with_retry("/avatar/list")
        avatars = response.get("data") or response.get("avatars") or []
        log_info(f"Fetched {len(avatars)} HeyGen avatars")
        return avatars

    def set_default_avatar(self, avatar_id: str) -> None:
        """Set the default avatar after validating its existence."""

        avatar_details = self.get_avatar_details(avatar_id)
        if not avatar_details:
            raise ValueError(f"Avatar {avatar_id} not found on HeyGen")

        self.default_avatar_id = avatar_id
        log_info(f"Default HeyGen avatar set to {avatar_id}")

    def get_avatar_details(self, avatar_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single avatar's details from HeyGen."""

        response = self._get_with_retry(f"/avatar/{avatar_id}")
        data = response.get("data") or response
        if not data:
            log_warning(f"No details returned for avatar {avatar_id}")
            return None
        log_debug(f"Avatar details retrieved for {avatar_id}")
        return data

    # ------------------------------------------------------------------
    # Legacy compatibility helpers

    def generate_ai_video_with_avatars(
        self,
        script_text: str,
        avatar_style: str,
        duration: int,
        *,
        voice_id: Optional[str] = None,
        background_music: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Backward compatible wrapper for existing scheduler integration."""

        avatar_id = self.default_avatar_id
        if not avatar_id:
            log_error("Default HeyGen avatar not configured")
            return None

        style_key = self._map_avatar_style(avatar_style)
        style_settings = self._resolve_style(style_key)
        resolved_voice_id = voice_id or style_settings.get("voice_id")

        if not resolved_voice_id:
            log_error("Voice ID is required for HeyGen video generation")
            return None

        try:
            result = self.generate_avatar_video(
                script_text=script_text,
                avatar_id=avatar_id,
                voice_id=resolved_voice_id,
                style=style_key,
                background_music=background_music,
                metadata={
                    "requested_duration": duration,
                    "avatar_style": avatar_style,
                },
            )

            result["video_type"] = "ai_avatar"
            result.setdefault("video_duration", duration)
            return result

        except UsageLimitExceeded as exc:
            log_warning(str(exc))
        except VideoGenerationError as exc:
            log_error(str(exc))
        except Exception as exc:  # pylint: disable=broad-except
            log_error(f"Unexpected error during HeyGen video generation: {exc}")

        return None

    def generate_video_script(
        self,
        theme: str,
        duration: int,
        style: str,
        topic_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Simple script generator aligned with configured style templates."""

        try:
            style_settings = self._resolve_style(style)
            pace = style_settings.get("pace", "balanced")
            hook = (topic_data or {}).get("title") or theme.replace("_", " ").title()

            script = (
                f"Hey trainers! Let's talk about {hook.lower()} today. "
                "Here are the key points you need to know to keep your clients engaged and progressing."
            )

            tips = style_settings.get("default_tips", [])
            if tips:
                script += " " + " ".join(tips[:3])

            caption = f"{hook} ? {pace} delivery"
            return {
                "script_text": script,
                "caption": caption,
                "duration": duration,
                "style": style,
            }

        except Exception as exc:  # pylint: disable=broad-except
            log_error(f"Failed to generate video script: {exc}")
            return None

    # ------------------------------------------------------------------
    # Internal helpers

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        try:
            if not os.path.exists(config_path):
                raise FileNotFoundError

            with open(config_path, "r", encoding="utf-8") as file:
                return yaml.safe_load(file) or {}

        except FileNotFoundError:
            log_warning(f"Video config not found at {config_path}; using defaults")
        except Exception as exc:
            log_warning(f"Error reading video config: {exc}; using defaults")

        return {}

    def _build_style_presets(self) -> Dict[str, Dict[str, Any]]:
        defaults = {
            "educational": {
                "style_key": "educational",
                "pace": "balanced",
                "chunk_char_limit": 480,
                "background_track": "uplifting",
                "voice_id": os.getenv("HEYGEN_EDUCATIONAL_VOICE_ID"),
                "default_tips": [
                    "? Break concepts into simple steps.",
                    "? Share one actionable takeaway.",
                    "? Invite feedback at the end.",
                ],
            },
            "motivational": {
                "style_key": "motivational",
                "pace": "energetic",
                "chunk_char_limit": 360,
                "background_track": "motivational",
                "voice_id": os.getenv("HEYGEN_MOTIVATIONAL_VOICE_ID"),
                "default_tips": [
                    "?? Highlight a quick win.",
                    "?? Encourage immediate action.",
                    "?? Close with an inspiring question.",
                ],
            },
            "tips": {
                "style_key": "quick_tips",
                "pace": "dynamic",
                "chunk_char_limit": 320,
                "background_track": "light",
                "voice_id": os.getenv("HEYGEN_TIPS_VOICE_ID"),
                "default_tips": [
                    "?? Tip 1: Keep admin templates ready.",
                    "?? Tip 2: Automate repetitive tasks.",
                    "?? Tip 3: Track progress weekly.",
                ],
            },
        }

        custom_styles = (
            self.config.get("video_generation", {}).get("styles", {})
        )

        for name, settings in custom_styles.items():
            slug = name.lower().replace(" ", "_")
            defaults[slug] = {**defaults.get(slug, {}), **settings}

        return defaults

    def _resolve_style(self, style: str) -> Dict[str, Any]:
        key = style.lower().replace(" ", "_")
        if key not in self.style_presets:
            log_warning(
                f"Unknown video style '{style}'. Falling back to 'educational'."
            )
            return self.style_presets["educational"]
        return self.style_presets[key]

    def _map_avatar_style(self, avatar_style: str) -> str:
        mapping = {
            "energetic": "motivational",
            "professional": "educational",
            "quick_tip": "tips",
            "quick_tips": "tips",
        }
        return mapping.get(avatar_style.lower(), "educational")

    def _chunk_script(self, script_text: str, *, limit: int) -> List[str]:
        cleaned = re.sub(r"\s+", " ", script_text).strip()
        if not cleaned:
            return []

        sentences = re.split(r"(?<=[.!?])\s", cleaned)
        chunks: List[str] = []
        current = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            prospective = f"{current} {sentence}".strip() if current else sentence
            if len(prospective) <= limit:
                current = prospective
            else:
                if current:
                    chunks.append(current)
                current = sentence

        if current:
            chunks.append(current)

        return chunks

    def _build_generate_payload(
        self,
        *,
        avatar_id: str,
        voice_id: str,
        style_settings: Dict[str, Any],
        script_chunks: List[str],
        background_music: bool,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        script_sections = [
            {
                "text": chunk,
                "pause_after": style_settings.get("default_pause", 0.6),
            }
            for chunk in script_chunks
        ]

        payload: Dict[str, Any] = {
            "avatar_id": avatar_id,
            "voice_id": voice_id,
            "video_style": style_settings.get("style_key", "custom"),
            "background_music": background_music,
            "music_track": style_settings.get("background_track"),
            "subtitles": style_settings.get("subtitles", True),
            "config": {
                "dimension": style_settings.get("dimension", "1080x1920"),
                "pace": style_settings.get("pace", "balanced"),
                "language": style_settings.get("language", "en"),
            },
            "script": {
                "type": "text",
                "sections": script_sections,
            },
            "metadata": metadata,
        }

        # Remove None values for cleaner payloads
        payload = {
            key: value
            for key, value in payload.items()
            if value is not None
        }

        return payload

    def _ensure_within_limit(self) -> None:
        if self.monthly_limit <= 0:
            return

        usage = self._get_current_month_usage()
        log_debug(
            f"Current HeyGen usage: {usage}/{self.monthly_limit} videos this month"
        )

        if usage >= self.monthly_limit:
            raise UsageLimitExceeded(
                f"Monthly HeyGen video limit reached ({usage}/{self.monthly_limit})"
            )

    def _get_current_month_usage(self) -> int:
        if not self.supabase_client:
            return 0

        now = datetime.now(self.sa_tz)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        try:
            result = (
                self.supabase_client.table(self.usage_table)
                .select("credits_used, video_count, success, requested_at")
                .gte("requested_at", month_start.isoformat())
                .lte("requested_at", now.isoformat())
                .execute()
            )

            records = result.data or []
            total = 0
            for record in records:
                if record.get("success") is False:
                    continue
                if record.get("credits_used") is not None:
                    total += record.get("credits_used")
                elif record.get("video_count") is not None:
                    total += record.get("video_count")
                else:
                    total += 1

            return total

        except Exception as exc:  # pylint: disable=broad-except
            log_warning(f"Unable to fetch HeyGen usage from Supabase: {exc}")
            return 0

    def _record_usage(
        self,
        video_id: str,
        *,
        success: bool,
        style: str,
        duration_seconds: Optional[int] = None,
    ) -> None:
        if not self.supabase_client:
            log_debug("Supabase client not configured; skipping usage tracking")
            return

        record = {
            "id": str(uuid.uuid4()),
            "video_id": video_id,
            "style": style,
            "success": success,
            "duration_seconds": duration_seconds,
            "credits_used": 1,
            "requested_at": datetime.now(self.sa_tz).isoformat(),
        }

        try:
            self.supabase_client.table(self.usage_table).insert(record).execute()
            log_debug(f"Recorded HeyGen usage for video {video_id}")
        except Exception as exc:  # pylint: disable=broad-except
            log_warning(f"Failed to record HeyGen usage: {exc}")

    def _store_video_record(
        self,
        *,
        video_id: str,
        video_data: Dict[str, Any],
        script_chunks: List[str],
        avatar_id: str,
        voice_id: str,
        style: str,
        background_music: bool,
        metadata: Dict[str, Any],
    ) -> None:
        if not self.supabase_client:
            log_warning("Supabase client not configured; skipping video persistence")
            return

        record = {
            "id": str(uuid.uuid4()),
            "video_id": video_id,
            "video_url": video_data.get("video_url"),
            "thumbnail_url": video_data.get("thumbnail_url"),
            "status": video_data.get("status"),
            "avatar_id": avatar_id,
            "voice_id": voice_id,
            "style": style,
            "background_music": background_music,
            "duration_seconds": video_data.get("duration"),
            "script": "\n\n".join(script_chunks),
            "metadata": metadata,
            "created_at": datetime.now(self.sa_tz).isoformat(),
        }

        try:
            self.supabase_client.table(self.video_table).insert(record).execute()
            log_info(f"Stored HeyGen video record {video_id} in Supabase")
        except Exception as exc:  # pylint: disable=broad-except
            log_warning(f"Failed to persist HeyGen video record: {exc}")

    # ------------------------------------------------------------------
    # HTTP helpers

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post_with_retry(self, endpoint: str, *, json: Dict[str, Any]) -> Dict[str, Any]:
        return self._request_with_retry("POST", endpoint, json=json)

    def _get_with_retry(
        self, endpoint: str, *, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return self._request_with_retry("GET", endpoint, params=params)

    def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{HEYGEN_API_BASE_URL}{endpoint}"
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.request(
                    method,
                    url,
                    headers=self._headers,
                    json=json,
                    params=params,
                    timeout=45,
                )

                if response.status_code == 429:
                    wait_time = self.retry_backoff * attempt
                    log_warning(
                        f"HeyGen rate limit hit. Retrying in {wait_time}s (attempt {attempt})"
                    )
                    time.sleep(wait_time)
                    continue

                if response.status_code >= 500:
                    wait_time = self.retry_backoff * attempt
                    log_warning(
                        f"HeyGen server error {response.status_code}. Retrying in {wait_time}s"
                    )
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    log_error(
                        f"HeyGen request failed after {self.max_retries} attempts: {exc}"
                    )
                    raise

                wait_time = self.retry_backoff * attempt
                log_warning(
                    f"HeyGen request error ({exc}). Retrying in {wait_time}s"
                )
                time.sleep(wait_time)

        raise VideoGenerationError("Failed to communicate with HeyGen API")

    def _poll_video_status(self, video_id: str) -> Dict[str, Any]:
        deadline = time.time() + self.poll_timeout
        params = {"video_id": video_id}

        while time.time() < deadline:
            response = self._get_with_retry("/video/status", params=params)
            data = response.get("data") or response
            status = data.get("status")

            log_debug(f"HeyGen video {video_id} status: {status}")

            if status in {"completed", "failed", "cancelled"}:
                data.setdefault("video_id", video_id)
                return data

            time.sleep(self.poll_interval)

        raise VideoGenerationError(
            f"Timed out waiting for HeyGen video {video_id} to complete"
        )

