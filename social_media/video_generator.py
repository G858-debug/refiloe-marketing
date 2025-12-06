"""HeyGen-powered video generator for social media automation."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pytz
import requests
import yaml

from utils.logger import log_debug, log_error, log_info, log_warning

try:  # Attempt package-relative import first
    from . import avatar_mapping as _avatar_mapping_module  # type: ignore
except ImportError:  # pragma: no cover - fallback when running from project root
    try:
        import avatar_mapping as _avatar_mapping_module  # type: ignore
    except ImportError:  # pragma: no cover - avatar mapping optional at runtime
        _avatar_mapping_module = None

# Import the new avatar selector
try:
    from .avatar_selector import AvatarSelector as _AvatarSelector  # type: ignore
except ImportError:  # pragma: no cover - fallback when running from project root
    try:
        from avatar_selector import AvatarSelector as _AvatarSelector  # type: ignore
    except ImportError:  # pragma: no cover - avatar selector optional at runtime
        _AvatarSelector = None

if _avatar_mapping_module is not None:
    get_avatar_for_content = getattr(_avatar_mapping_module, "get_avatar_for_content", None)
    get_fallback_avatar_id = getattr(_avatar_mapping_module, "get_fallback_avatar_id", None)
    AvatarSelectionError = getattr(
        _avatar_mapping_module,
        "AvatarSelectionError",
        type("AvatarSelectionError", (Exception,), {}),
    )
else:  # pragma: no cover - defensive defaults when module missing
    get_avatar_for_content = None
    get_fallback_avatar_id = None

    class AvatarSelectionError(Exception):
        """Raised when dynamic avatar selection fails."""



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
        self.default_voice_id = os.getenv("HEYGEN_DEFAULT_VOICE_ID") or self.config.get(
            "heygen_settings", {}
        ).get("default_voice_id")
        self.style_presets = self._build_style_presets()

        self.group_avatar_id = os.getenv("HEYGEN_GROUP_AVATAR_ID")
        self.closeup_avatar_id = os.getenv("HEYGEN_THREEQUARTERS_CLOSEUP_AVATAR_ID")
        self.analytics_table = os.getenv("HEYGEN_VIDEO_ANALYTICS_TABLE", "video_analytics")

        # Initialize avatar selector if available
        self.avatar_selector = None
        if _AvatarSelector is not None:
            try:
                self.avatar_selector = _AvatarSelector(default_avatar_env="HEYGEN_AVATAR_DEFAULT")
                log_info("AvatarSelector initialized successfully")
            except Exception as exc:  # pylint: disable=broad-except
                log_warning(f"Failed to initialize AvatarSelector: {exc}")

        log_info("VideoGenerator initialized with HeyGen integration")

    # ------------------------------------------------------------------
    # Public API

    def generate_avatar_video(
        self,
        script_text: str,
        avatar_id: Optional[str] = None,
        voice_id: Optional[str] = None,
        *,
        style: str = "educational",
        background_music: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        content_text: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a talking avatar video using HeyGen with dynamic avatar selection.

        Args:
            script_text: Full narration script that will be chunked for pacing.
            avatar_id: Optional explicit HeyGen avatar identifier supplied by caller.
            voice_id: HeyGen voice identifier. Defaults to configured default if omitted.
            style: Content style preset (educational, motivational, tips, etc.).
            background_music: Whether to include background music.
            metadata: Optional metadata to persist with the video record.
            content_text: Optional free-form content text used to influence avatar selection.
            content_type: Optional content category used by avatar mapping logic.

        Returns:
            Dict with video metadata including video_url on success.
        """

        log_info("Starting HeyGen avatar video generation")
        self._ensure_within_limit()

        style_settings = self._resolve_style(style)
        chunk_char_limit = style_settings.get("chunk_char_limit", 480)
        # Prepare script for proper pronunciation in narration
        narration_script = self._prepare_script_for_narration(script_text)
        script_chunks = self._chunk_script(narration_script, limit=chunk_char_limit)

        if not script_chunks:
            raise ValueError("Script text is empty after processing")

        resolved_voice_id = voice_id or self.default_voice_id
        if not resolved_voice_id:
            raise ValueError("Voice ID is required for HeyGen video generation")

        primary_content_text = (content_text or script_text or "").strip()

        base_metadata: Dict[str, Any] = dict(metadata or {})

        candidate_chain = self._build_avatar_candidate_chain(
            avatar_id,
            content_text=primary_content_text,
            content_type=content_type,
            metadata=base_metadata,
        )

        if not candidate_chain:
            raise VideoGenerationError("No HeyGen avatar candidates available for generation")

        selection_attempts: List[Dict[str, Any]] = []
        last_error: Optional[Exception] = None

        for attempt_index, candidate in enumerate(candidate_chain):
            current_avatar_id = candidate["avatar_id"]
            avatar_type = self._determine_avatar_type(current_avatar_id)
            attempt_detail: Dict[str, Any] = {
                "avatar_id": current_avatar_id,
                "reason": candidate.get("reason"),
                "source": candidate.get("source"),
                "attempt_index": attempt_index,
                "status": "pending",
                "avatar_type": avatar_type,
            }
            if candidate.get("context"):
                attempt_detail["context"] = candidate["context"]
            selection_attempts.append(attempt_detail)

            attempt_metadata = dict(base_metadata)
            attempt_metadata.setdefault("avatar_type", avatar_type)
            avatar_selection_meta: Dict[str, Any] = {
                "avatar_id": current_avatar_id,
                "reason": candidate.get("reason"),
                "source": candidate.get("source"),
                "attempt_index": attempt_index,
                "content_type": content_type,
                "content_text_excerpt": primary_content_text[:160] if primary_content_text else None,
                "fallback_chain": [
                    {
                        "avatar_id": chain_item["avatar_id"],
                        "reason": chain_item.get("reason"),
                        "source": chain_item.get("source"),
                    }
                    for chain_item in candidate_chain
                ],
                "attempts": selection_attempts,
                "avatar_type": avatar_type,
            }
            if candidate.get("context"):
                avatar_selection_meta["context"] = candidate["context"]
            selector_context = (
                base_metadata.get("avatar_selection", {}).get("selector_context")
                if isinstance(base_metadata.get("avatar_selection"), dict)
                else None
            )
            if selector_context and "selector_context" not in avatar_selection_meta:
                avatar_selection_meta["selector_context"] = selector_context
            attempt_metadata["avatar_selection"] = avatar_selection_meta

            log_info(
                "Attempting HeyGen video with avatar '%s' (reason=%s, source=%s)"
                % (
                    current_avatar_id,
                    candidate.get("reason"),
                    candidate.get("source"),
                )
            )

            try:
                endpoint, payload = self._build_generate_payload(
                    avatar_id=current_avatar_id,
                    voice_id=resolved_voice_id,
                    style_settings=style_settings,
                    script_chunks=script_chunks,
                    background_music=background_music,
                    metadata=attempt_metadata,
                )

                log_debug(
                    "Prepared HeyGen payload with %d chunks for avatar %s (endpoint=%s, type=%s)"
                    % (len(script_chunks), current_avatar_id, endpoint, avatar_type)
                )

                response = self._post_with_retry(endpoint, json=payload)
                video_id = (
                    response.get("data", {}).get("video_id")
                    or response.get("video_id")
                    or response.get("task_id")
                )

                if not video_id:
                    raise VideoGenerationError(
                        "HeyGen response did not include a video identifier"
                    )

                log_info(
                    "HeyGen video request accepted (video_id=%s, avatar=%s)"
                    % (video_id, current_avatar_id)
                )

                video_data = self._poll_video_status(video_id)

                if video_data.get("status") != "completed":
                    self._record_usage(video_id, success=False, style=style)
                    attempt_detail["status"] = "failed"
                    attempt_detail["error"] = f"status={video_data.get('status')}"
                    last_error = VideoGenerationError(
                        f"Video generation failed with status: {video_data.get('status')}"
                    )
                    log_warning(
                        "Video generation incomplete for avatar '%s' (status=%s)"
                        % (current_avatar_id, video_data.get("status"))
                    )
                    continue

                video_url = video_data.get("video_url")
                if not video_url:
                    self._record_usage(video_id, success=False, style=style)
                    attempt_detail["status"] = "failed"
                    attempt_detail["error"] = "missing_video_url"
                    last_error = VideoGenerationError(
                        "HeyGen completed without returning a video URL"
                    )
                    log_warning(
                        "HeyGen completed without video URL for avatar '%s'"
                        % current_avatar_id
                    )
                    continue

                self._record_usage(
                    video_id,
                    success=True,
                    style=style,
                    duration_seconds=video_data.get("duration"),
                )

                attempt_detail["status"] = "success"
                attempt_detail["video_id"] = video_id
                attempt_detail["video_url"] = video_url
                attempt_detail["duration"] = video_data.get("duration")

                avatar_selection_meta["attempts"] = selection_attempts
                avatar_selection_meta["selected_index"] = attempt_index
                avatar_selection_meta["video_id"] = video_id

                self._store_video_record(
                    video_id=video_id,
                    video_data=video_data,
                    script_chunks=script_chunks,
                    avatar_id=current_avatar_id,
                    voice_id=resolved_voice_id,
                    style=style,
                    background_music=background_music,
                    metadata=attempt_metadata,
                )

                result = {
                    "video_id": video_id,
                    "video_url": video_url,
                    "thumbnail_url": video_data.get("thumbnail_url"),
                    "status": video_data.get("status"),
                    "duration": video_data.get("duration"),
                    "style": style,
                    "avatar_id": current_avatar_id,
                    "avatar_type": avatar_type,
                    "voice_id": resolved_voice_id,
                    "script_chunks": script_chunks,
                    "avatar_selection": avatar_selection_meta,
                }

                log_info(
                    "HeyGen video generation complete with avatar '%s' (reason=%s)"
                    % (current_avatar_id, candidate.get("reason"))
                )
                return result

            except requests.RequestException as exc:
                attempt_detail["status"] = "failed"
                attempt_detail["error"] = str(exc)
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code in {404, 422}:
                    log_warning(
                        "HeyGen avatar '%s' unavailable (status_code=%s); trying fallback"
                        % (current_avatar_id, status_code)
                    )
                else:
                    log_warning(
                        "HeyGen request failed for avatar '%s': %s"
                        % (current_avatar_id, exc)
                    )
                last_error = exc
            except VideoGenerationError as exc:
                attempt_detail["status"] = "failed"
                attempt_detail["error"] = str(exc)
                log_warning(
                    "Video generation attempt failed for avatar '%s': %s"
                    % (current_avatar_id, exc)
                )
                last_error = exc
            except Exception as exc:  # pylint: disable=broad-except
                attempt_detail["status"] = "failed"
                attempt_detail["error"] = str(exc)
                log_error(
                    "Unexpected error during HeyGen generation with avatar '%s': %s"
                    % (current_avatar_id, exc)
                )
                last_error = exc

        failure_summary = ", ".join(
            f"{attempt['avatar_id']}: {attempt.get('error')}"
            for attempt in selection_attempts
            if attempt.get("error")
        )
        log_error(
            "All avatar options failed for HeyGen video generation%s"
            % (f" ({failure_summary})" if failure_summary else "")
        )
        raise VideoGenerationError(
            "All avatar options failed for HeyGen video generation"
        ) from last_error

    def generate_avatar_iv_video(
        self,
        script: str,
        image_url: str = None,
        image_key: str = None,
        *,
        voice_id: Optional[str] = None,
        custom_motion_prompt: Optional[str] = None,
        enhance_motion: bool = True,
        aspect_ratio: str = "9:16",
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate video using Avatar IV API with automatic gestures.

        Avatar IV provides automatic hand gestures, arm movements, and expressive
        facial dynamics from a single photo.

        Args:
            script: Text the avatar will speak (max 5000 characters)
            image_url: Public URL to the image (alternative to image_key)
            image_key: HeyGen image asset key (from upload or look generation)
            voice_id: HeyGen voice ID. Uses default if not provided.
            custom_motion_prompt: Optional motion description (e.g., "waves enthusiastically")
            enhance_motion: Whether to let AI enhance the motion prompt
            aspect_ratio: Video aspect ratio ("16:9", "9:16", "1:1")
            title: Optional video title
            metadata: Optional metadata dict

        Returns:
            Dict containing video_id and status

        Raises:
            ValueError: If neither image_url nor image_key provided
            VideoGenerationError: If video generation fails
        """
        if not image_url and not image_key:
            raise ValueError("Either image_url or image_key must be provided")

        if not script or len(script.strip()) == 0:
            raise ValueError("Script cannot be empty")

        if len(script) > 5000:
            raise ValueError("Script exceeds 5000 character limit")

        # Prepare script for proper pronunciation in narration
        narration_script = self._prepare_script_for_narration(script)

        # Use provided voice or default
        resolved_voice_id = voice_id or self.default_voice_id
        if not resolved_voice_id:
            raise ValueError("No voice_id provided and no default voice configured")

        log_info("Starting Avatar IV video generation")
        log_info(f"Script length: {len(narration_script)} characters")
        log_info(f"Voice: {resolved_voice_id}")
        log_info(f"Aspect ratio: {aspect_ratio}")
        if custom_motion_prompt:
            log_info(f"Motion prompt: {custom_motion_prompt}")

        # Build Avatar IV API payload
        payload = {
            "script": narration_script,
            "voice_id": resolved_voice_id,
            "aspect_ratio": aspect_ratio,
        }

        # Add image source (Avatar IV requires image_key format)
        if image_key:
            payload["image_key"] = image_key
            log_info(f"Using image_key: {image_key}")
        elif image_url:
            # Fallback to image_url if no key available
            payload["image_url"] = image_url
            log_info(f"Using image_url: {image_url[:50]}...")

        # Add optional motion prompt
        if custom_motion_prompt:
            payload["custom_motion_prompt"] = custom_motion_prompt
            payload["enhance_custom_motion_prompt"] = enhance_motion

        # Add optional video title (Avatar IV uses 'video_title' not 'title')
        if title:
            payload["video_title"] = title

        # Add metadata if provided
        if metadata:
            payload["callback_data"] = metadata

        # Log the full payload being sent for debugging
        log_info("Avatar IV API payload:")
        log_info(json.dumps(payload, indent=2))

        try:
            # Call Avatar IV endpoint
            response = self._post_with_retry(
                "/video/av4/generate",
                json=payload
            )

            data = response.get("data", {})
            video_id = data.get("video_id")

            if not video_id:
                raise VideoGenerationError(
                    "Avatar IV response did not include video_id"
                )

            log_info(f"Avatar IV video generation started (video_id={video_id})")

            result = {
                "video_id": video_id,
                "status": "processing",
                "api_type": "avatar_iv",
                "script": script,
                "voice_id": resolved_voice_id,
                "aspect_ratio": aspect_ratio,
            }

            if title:
                result["video_title"] = title
            if image_key:
                result["image_key"] = image_key
            if image_url:
                result["image_url"] = image_url
            if custom_motion_prompt:
                result["motion_prompt"] = custom_motion_prompt

            return result

        except requests.RequestException as exc:
            log_error(f"Avatar IV video generation failed: {exc}")
            raise VideoGenerationError(f"Failed to generate Avatar IV video: {exc}") from exc

    def _build_avatar_candidate_chain(
        self,
        requested_avatar_id: Optional[str],
        *,
        content_text: Optional[str],
        content_type: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Assemble avatar candidates honoring primary and fallback rules."""

        candidates: List[Dict[str, Any]] = []
        selection_context: Optional[Dict[str, Any]] = None

        if requested_avatar_id:
            candidates.append(
                {
                    "avatar_id": requested_avatar_id,
                    "reason": "caller_provided_avatar",
                    "source": "caller",
                }
            )

        # Try new avatar selector first (if available)
        if self.avatar_selector is not None:
            try:
                selector_result = self.avatar_selector.select_avatar(
                    content_theme=content_type,
                    content_text=content_text,
                )
                if selector_result and selector_result.get("avatar_id"):
                    # Only add if not already requested by caller
                    if selector_result.get("source") != "override":
                        candidates.append(
                            {
                                "avatar_id": selector_result["avatar_id"],
                                "reason": selector_result.get("reason", "avatar_selector"),
                                "source": f"avatar_selector_{selector_result.get('source', 'unknown')}",
                                "context": selector_result,
                            }
                        )
                        selection_context = selector_result
            except Exception as exc:  # pylint: disable=broad-except
                log_warning(f"Avatar selector failed: {exc}")

        # Fall back to legacy avatar mapping (if available)
        if callable(get_avatar_for_content):  # pragma: no branch - runtime guarded
            selection_kwargs: Dict[str, Any] = {}
            if content_text:
                selection_kwargs["content_text"] = content_text
            if content_type:
                selection_kwargs["content_type"] = content_type

            try:
                selection_result = get_avatar_for_content(**selection_kwargs)
                mapping_context = selection_result if isinstance(selection_result, dict) else None

                derived_avatar_id: Optional[str] = None
                derived_reason: Optional[str] = None

                if isinstance(selection_result, dict):
                    derived_avatar_id = selection_result.get("avatar_id") or selection_result.get("id")
                    derived_reason = selection_result.get("reason") or selection_result.get("strategy")
                elif isinstance(selection_result, (list, tuple)) and selection_result:
                    primary = selection_result[0]
                    if isinstance(primary, dict):
                        derived_avatar_id = primary.get("avatar_id") or primary.get("id")
                        derived_reason = primary.get("reason") or primary.get("strategy")
                        mapping_context = primary
                    elif isinstance(primary, str):
                        derived_avatar_id = primary
                elif isinstance(selection_result, str):
                    derived_avatar_id = selection_result

                if derived_avatar_id:
                    candidates.append(
                        {
                            "avatar_id": derived_avatar_id,
                            "reason": derived_reason or "avatar_mapping_selection",
                            "source": "avatar_mapping",
                            "context": mapping_context,
                        }
                    )
                    if not selection_context:
                        selection_context = mapping_context
            except AvatarSelectionError as exc:
                log_warning(f"Dynamic avatar selection failed: {exc}")
            except Exception as exc:  # pylint: disable=broad-except
                log_warning(f"Unexpected error during avatar mapping selection: {exc}")

        if not candidates and self.default_avatar_id:
            candidates.append(
                {
                    "avatar_id": self.default_avatar_id,
                    "reason": "default_avatar_configured",
                    "source": "default",
                }
            )

        group_avatar = self._resolve_named_avatar("GROUP")
        if group_avatar:
            candidates.append(
                {
                    "avatar_id": group_avatar,
                    "reason": "group_avatar_fallback",
                    "source": "fallback_group",
                }
            )

        closeup_avatar = self._resolve_named_avatar("THREEQUARTERS_CLOSEUP")
        if closeup_avatar:
            candidates.append(
                {
                    "avatar_id": closeup_avatar,
                    "reason": "threequarters_closeup_fallback",
                    "source": "fallback_closeup",
                }
            )

        deduped: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        for candidate in candidates:
            candidate_id = candidate.get("avatar_id")
            if not candidate_id or candidate_id in seen_ids:
                continue
            deduped.append(candidate)
            seen_ids.add(candidate_id)

        if metadata is not None:
            avatar_meta = metadata.setdefault("avatar_selection", {})
            if selection_context:
                avatar_meta.setdefault("selector_context", selection_context)

        return deduped

    def _resolve_named_avatar(self, name: str) -> Optional[str]:
        """Resolve a named fallback avatar to a HeyGen identifier."""

        normalised = name.upper()
        if normalised == "GROUP" and self.group_avatar_id:
            return self.group_avatar_id
        if normalised == "THREEQUARTERS_CLOSEUP" and self.closeup_avatar_id:
            return self.closeup_avatar_id

        resolved: Optional[str] = None
        if callable(get_fallback_avatar_id):
            try:
                resolved = get_fallback_avatar_id(normalised)  # type: ignore[misc]
            except TypeError:
                try:
                    resolved = get_fallback_avatar_id(name=normalised)  # type: ignore[call-arg]
                except Exception as exc:  # pylint: disable=broad-except
                    log_debug(f"Fallback avatar resolver rejected keyword argument: {exc}")
            except Exception as exc:  # pylint: disable=broad-except
                log_warning(f"Failed to resolve fallback avatar '{name}': {exc}")

        if normalised == "GROUP" and resolved:
            self.group_avatar_id = resolved
        elif normalised == "THREEQUARTERS_CLOSEUP" and resolved:
            self.closeup_avatar_id = resolved

        return resolved

    def list_available_avatars(self) -> List[Dict[str, Any]]:
        """Return the available HeyGen avatars for the account."""

        response = self._get_with_retry("/avatar/list")
        avatars = response.get("data") or response.get("avatars") or []
        log_info(f"Fetched {len(avatars)} HeyGen avatars")
        return avatars

    def get_photo_avatar_group(self, group_id: str) -> List[Dict[str, Any]]:
        """Get all avatar looks within a photo avatar group."""

        try:
            response = self._get_with_retry(f"/avatar_group/{group_id}/avatars")
            data = response.get("data", {})
            avatars = data.get("avatars", [])
            log_info(f"Found {len(avatars)} avatar looks in group {group_id}")
            return avatars
        except Exception as exc:  # pylint: disable=broad-except
            log_error(f"Failed to get photo avatar group: {exc}")
            return []

    def get_avatar_analytics(
        self,
        *,
        limit: Optional[int] = None,
        min_samples: int = 1,
    ) -> List[Dict[str, Any]]:
        """Aggregate engagement metrics per avatar to identify top performers."""

        if not self.supabase_client:
            log_warning("Supabase client not configured; returning empty avatar analytics")
            return []

        try:
            video_query = (
                self.supabase_client.table(self.video_table)
                .select("video_id, avatar_id, metadata")
                .execute()
            )
        except Exception as exc:  # pylint: disable=broad-except
            log_warning(f"Failed to fetch generated videos for analytics: {exc}")
            return []

        video_records = [record for record in (video_query.data or []) if record.get("avatar_id")]
        if not video_records:
            log_info("No generated video records found for avatar analytics computation")
            return []

        analytics_map: Dict[str, Dict[str, Any]] = {}
        if self.analytics_table:
            try:
                analytics_query = (
                    self.supabase_client.table(self.analytics_table)
                    .select("*")
                    .execute()
                )
                analytics_map = {
                    row.get("video_id") or row.get("id"): row
                    for row in (analytics_query.data or [])
                }
            except Exception as exc:  # pylint: disable=broad-except
                log_warning(f"Unable to retrieve detailed video analytics: {exc}")

        def _normalise_metadata(value: Any) -> Dict[str, Any]:
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return {}
            return {}

        def _as_float(value: Any) -> Optional[float]:
            try:
                if value is None:
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        avatar_stats: Dict[str, Dict[str, Any]] = {}

        for record in video_records:
            avatar_key = record.get("avatar_id") or "UNKNOWN"
            stats = avatar_stats.setdefault(
                avatar_key,
                {
                    "avatar_id": avatar_key,
                    "video_count": 0,
                    "engagement_rates": [],
                    "completion_rates": [],
                    "view_counts": [],
                    "reason_counts": {},
                },
            )

            stats["video_count"] += 1

            metadata = _normalise_metadata(record.get("metadata"))
            selection_meta = (
                metadata.get("avatar_selection")
                if isinstance(metadata.get("avatar_selection"), dict)
                else {}
            )

            reason_value = selection_meta.get("reason")
            if reason_value:
                stats["reason_counts"][reason_value] = stats["reason_counts"].get(reason_value, 0) + 1

            engagement_candidates = [
                metadata.get("engagement_rate"),
                selection_meta.get("engagement_rate"),
            ]
            analytics_row = analytics_map.get(record.get("video_id"))
            if analytics_row:
                engagement_candidates.append(analytics_row.get("engagement_rate"))
                view_candidate = _as_float(
                    analytics_row.get("view_count")
                    or analytics_row.get("views")
                    or analytics_row.get("impressions")
                )
                if view_candidate is not None:
                    stats["view_counts"].append(view_candidate)

                completion_candidate = _as_float(
                    analytics_row.get("completion_rate")
                    or analytics_row.get("average_view_duration")
                )
                if completion_candidate is not None:
                    stats["completion_rates"].append(completion_candidate)
            else:
                view_candidate = _as_float(metadata.get("view_count"))
                if view_candidate is not None:
                    stats["view_counts"].append(view_candidate)

                completion_candidate = _as_float(metadata.get("completion_rate"))
                if completion_candidate is not None:
                    stats["completion_rates"].append(completion_candidate)

            engagement = next((value for value in engagement_candidates if _as_float(value) is not None), None)
            stats["engagement_rates"].append(_as_float(engagement))

        analytics_summary: List[Dict[str, Any]] = []
        for avatar_key, stats in avatar_stats.items():
            engagement_values = [value for value in stats["engagement_rates"] if value is not None]
            completion_values = [value for value in stats["completion_rates"] if value is not None]
            view_values = [value for value in stats["view_counts"] if value is not None]

            if stats["video_count"] < min_samples:
                continue

            average_engagement = (
                round(sum(engagement_values) / len(engagement_values), 2)
                if engagement_values
                else None
            )
            average_completion = (
                round(sum(completion_values) / len(completion_values), 2)
                if completion_values
                else None
            )
            average_views = (
                round(sum(view_values) / len(view_values), 2)
                if view_values
                else None
            )

            top_reasons = sorted(
                stats["reason_counts"].items(),
                key=lambda item: item[1],
                reverse=True,
            )[:3]

            analytics_summary.append(
                {
                    "avatar_id": avatar_key,
                    "video_count": stats["video_count"],
                    "average_engagement_rate": average_engagement,
                    "average_completion_rate": average_completion,
                    "average_view_count": average_views,
                    "engagement_samples": len(engagement_values),
                    "top_selection_reasons": top_reasons,
                }
            )

        analytics_summary.sort(
            key=lambda item: (
                item["average_engagement_rate"] is None,
                -(item["average_engagement_rate"] or 0.0),
            )
        )

        if limit:
            analytics_summary = analytics_summary[: limit]

        if analytics_summary:
            best_avatar = analytics_summary[0]
            log_info(
                "Avatar analytics computed | top_avatar=%s avg_engagement=%s"
                % (best_avatar.get("avatar_id"), best_avatar.get("average_engagement_rate"))
            )
        else:
            log_info("Avatar analytics computed but no qualifying records met sample threshold")

        return analytics_summary

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
                content_text=script_text,
                content_type=avatar_style,
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

    def _prepare_script_for_narration(self, script_text: str) -> str:
        """Prepare script text for HeyGen narration by replacing words with phonetic pronunciations.

        This ensures proper pronunciation of names and terms in AI-generated voice narration.
        Maintains original spelling in all other contexts (captions, display text, etc.).

        Args:
            script_text: Original script text

        Returns:
            str: Script with phonetic substitutions for narration
        """
        import re

        # Phonetic pronunciation mappings for HeyGen voice narration
        pronunciation_map = {
            # Name pronunciations
            'Refiloe': 'Reh FILL weh',
            'Refiloe\'s': 'Reh FILL weh\'s',
        }

        narration_script = script_text

        # Replace each term with its phonetic pronunciation
        for original, phonetic in pronunciation_map.items():
            # Use word boundary matching to avoid partial replacements
            pattern = r'\b' + re.escape(original) + r'\b'
            narration_script = re.sub(pattern, phonetic, narration_script, flags=re.IGNORECASE)

        # Log if substitutions were made (for debugging)
        if narration_script != script_text:
            substitutions_made = sum(1 for orig in pronunciation_map.keys() if orig.lower() in script_text.lower())
            log_info(f"Applied {substitutions_made} pronunciation substitution(s) for HeyGen narration")

        return narration_script

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
    ) -> Tuple[str, Dict[str, Any]]:
        is_photo_avatar = self._is_photo_avatar_id(avatar_id)

        dimension_value = style_settings.get("dimension", "1080x1920")
        width, height = self._parse_dimension(dimension_value)

        voice_payload: Dict[str, Any] = {
            "type": "text",
            "input_text": " ".join(script_chunks),
            "voice_id": voice_id,
        }

        character_payload: Dict[str, Any]
        if is_photo_avatar:
            character_payload = {
                "type": "talking_photo",
                "talking_photo_id": avatar_id,
            }
        else:
            character_payload = {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal",
            }

        background_setting = style_settings.get("background")
        if isinstance(background_setting, dict):
            background_config = dict(background_setting)
        else:
            background_color = style_settings.get("background_color", "#FFFFFF")
            background_config = {
                "type": "color",
                "value": background_color,
            }

        video_input: Dict[str, Any] = {
            "character": character_payload,
            "voice": voice_payload,
            "background": background_config,
        }

        if isinstance(background_music, dict):
            video_input["background_music"] = background_music
        else:
            video_input["background_music"] = bool(background_music)

        payload: Dict[str, Any] = {
            "video_inputs": [video_input],
            "dimension": {"width": width, "height": height},
            "test": False,
            "caption": style_settings.get("subtitles", True),
        }

        if metadata:
            payload["metadata"] = dict(metadata)

        endpoint = "/video/generate"
        return endpoint, payload

    @staticmethod
    def _parse_dimension(dimension_value: Any) -> Tuple[int, int]:
        default_width, default_height = 1080, 1920

        if isinstance(dimension_value, dict):
            width = dimension_value.get("width", default_width)
            height = dimension_value.get("height", default_height)
            try:
                return int(width), int(height)
            except (TypeError, ValueError):
                return default_width, default_height

        if isinstance(dimension_value, str):
            parts = dimension_value.lower().replace(" ", "").split("x")
            if len(parts) == 2:
                try:
                    return int(parts[0]), int(parts[1])
                except (TypeError, ValueError):
                    pass

        return default_width, default_height

    @staticmethod
    def _is_photo_avatar_id(avatar_id: Optional[str]) -> bool:
        if not avatar_id:
            return False

        clean_id = avatar_id.replace("-", "").strip()
        if len(clean_id) != 32:
            return False

        try:
            int(clean_id, 16)
            return True
        except ValueError:
            return False

    def _determine_avatar_type(self, avatar_id: Optional[str]) -> str:
        return "photo" if self._is_photo_avatar_id(avatar_id) else "standard"

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
            # Insert into database (SupabaseRestClient.insert() already executes and returns ExecuteResult)
            self.supabase_client.table(self.usage_table).insert(record)
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
            # Insert into database (SupabaseRestClient.insert() already executes and returns ExecuteResult)
            self.supabase_client.table(self.video_table).insert(record)
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

                # Log error details before raising
                if not response.ok:
                    log_error(f"HeyGen API error response:")
                    log_error(f"Status Code: {response.status_code}")
                    log_error(f"Response Headers: {dict(response.headers)}")
                    try:
                        error_body = response.json()
                        log_error(f"Response Body: {json.dumps(error_body, indent=2)}")
                    except Exception:
                        log_error(f"Response Text: {response.text}")

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

        status_url = "https://api.heygen.com/v1/video_status.get"
        params = {"video_id": video_id}
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        while time.time() < deadline:
            for attempt in range(self.max_retries):
                try:
                    response = requests.get(
                        status_url,
                        headers=headers,
                        params=params,
                        timeout=30,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    data = payload.get("data") or payload
                    status = data.get("status")

                    log_debug(f"HeyGen video {video_id} status: {status}")

                    if status in {"completed", "failed", "cancelled"}:
                        data.setdefault("video_id", video_id)
                        return data

                    break
                except Exception as exc:  # pylint: disable=broad-except
                    if attempt < self.max_retries - 1:
                        log_warning(
                            "HeyGen status check failed (attempt %s/%s): %s"
                            % (attempt + 1, self.max_retries, exc)
                        )
                        time.sleep(self.retry_backoff)
                        continue
                    raise

            time.sleep(self.poll_interval)

        raise VideoGenerationError(
            f"Timed out waiting for HeyGen video {video_id} to complete"
        )

    def check_video_status(self, video_id: str) -> Dict[str, Any]:
        """
        Check the status of a HeyGen video without polling/waiting.

        Args:
            video_id: The HeyGen video ID to check

        Returns:
            Dict with status, video_url, and error fields
        """
        status_url = "https://api.heygen.com/v1/video_status.get"
        params = {"video_id": video_id}
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(
                status_url,
                headers=headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data") or payload

            return {
                'status': data.get('status'),
                'video_url': data.get('video_url'),
                'error': data.get('error'),
                'duration': data.get('duration')
            }
        except Exception as exc:
            log_error(f"Error checking video status for {video_id}: {exc}")
            return {
                'status': 'error',
                'video_url': None,
                'error': str(exc)
            }

