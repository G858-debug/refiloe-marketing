"""
Social media automation scheduler.

This module centralises the logic for registering and running all recurring jobs
required by the marketing automation stack. It is intentionally lightweight: the
actual job bodies are defensive and degrade gracefully when optional
integrations (Anthropic, HeyGen, Facebook) are not configured. The goal is to
provide consistent lifecycle management so the Flask app can start, monitor, and
shut down the scheduler without leaving background threads behind.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import traceback

from utils.logger import log_error, log_info, log_warning


SA_TIMEZONE = pytz.timezone("Africa/Johannesburg")


class SocialMediaScheduler:
    """Wrapper around APScheduler with defensive job registration."""

    def __init__(self, app, supabase_client) -> None:
        self.app = app
        self.supabase_client = supabase_client
        self.scheduler = BackgroundScheduler(timezone=SA_TIMEZONE)
        self._jobs_registered = False
        self._last_run: Dict[str, Dict[str, Optional[str]]] = {}

    # --------------------------------------------------------------------- #
    # Lifecycle management
    # --------------------------------------------------------------------- #
    def start(self) -> bool:
        """
        Register jobs (if needed) and start the background scheduler.

        Returns:
            bool: True when the scheduler is running, False otherwise.
        """
        if self.supabase_client is None:
            raise RuntimeError("Supabase client must be initialised before starting the scheduler.")

        if not self._jobs_registered:
            self._register_jobs()

        if self.scheduler.running:
            log_info("Social media scheduler is already running.")
            return True

        try:
            self.scheduler.start()
            log_info("✅ Social media scheduler started.")
            return True
        except Exception as exc:  # pragma: no cover - APScheduler raises dynamically
            log_error(f"Failed to start social media scheduler: {exc}\n{traceback.format_exc()}")
            return False

    def stop(self) -> None:
        """Shut down the background scheduler gracefully."""
        if not self.scheduler.running:
            return

        try:
            self.scheduler.shutdown(wait=False)
            log_info("🛑 Social media scheduler stopped.")
        except Exception as exc:  # pragma: no cover - shutdown failures are rare
            log_error(f"Error while stopping social media scheduler: {exc}\n{traceback.format_exc()}")

    # --------------------------------------------------------------------- #
    # Job registration & wrappers
    # --------------------------------------------------------------------- #
    def _register_jobs(self) -> None:
        """Register recurring jobs with APScheduler."""
        log_info("Registering social media scheduler jobs.")

        job_definitions: List[Dict[str, Any]] = [
            {
                "id": "video_generation_daily",
                "name": "Daily Video Generation",
                "trigger": CronTrigger(hour=5, minute=0, timezone=SA_TIMEZONE),
                "callable": self._wrap_job("video_generation_daily", self.run_video_generation),
            },
            {
                "id": "content_generation_daily",
                "name": "Daily Content Generation",
                "trigger": CronTrigger(hour=6, minute=0, timezone=SA_TIMEZONE),
                "callable": self._wrap_job("content_generation_daily", self.run_content_generation),
            },
            {
                "id": "content_posting_interval",
                "name": "Content Posting Interval",
                "trigger": IntervalTrigger(minutes=30, timezone=SA_TIMEZONE),
                "callable": self._wrap_job("content_posting_interval", self.run_content_posting),
            },
            {
                "id": "analytics_collection_daily",
                "name": "Daily Analytics Collection",
                "trigger": CronTrigger(hour=23, minute=0, timezone=SA_TIMEZONE),
                "callable": self._wrap_job("analytics_collection_daily", self.run_analytics_collection),
            },
        ]

        for job in job_definitions:
            try:
                self.scheduler.add_job(
                    job["callable"],
                    job["trigger"],
                    id=job["id"],
                    name=job["name"],
                    replace_existing=True,
                )
                log_info(f"Registered scheduler job `{job['id']}`.")
            except Exception as exc:  # pragma: no cover - APScheduler raises dynamically
                log_error(f"Failed to register job `{job['id']}`: {exc}\n{traceback.format_exc()}")
                raise

        self._jobs_registered = True

    def _wrap_job(self, job_id: str, func: Callable[[], None]) -> Callable[[], None]:
        """Decorate job execution with logging and run tracking."""

        def _runner() -> None:
            started_at = datetime.now(SA_TIMEZONE)
            log_info(f"▶️  Starting scheduler job `{job_id}`.")
            status = "success"
            error_message: Optional[str] = None

            try:
                func()
            except Exception as exc:  # pragma: no cover - job body handles errors defensively
                status = "error"
                error_message = str(exc)
                log_error(f"Scheduler job `{job_id}` failed: {exc}\n{traceback.format_exc()}")
            finally:
                self._last_run[job_id] = {
                    "status": status,
                    "last_run": started_at.isoformat(),
                    "error": error_message,
                }
                log_info(f"✅ Finished scheduler job `{job_id}` with status `{status}`.")

        return _runner

    # --------------------------------------------------------------------- #
    # Job implementations
    # --------------------------------------------------------------------- #
    def run_video_generation(self) -> None:
        """Daily job at 5:00 AM SAST to prepare video content."""
        if self.supabase_client is None:
            log_warning("Supabase client unavailable; skipping video generation job.")
            return

        if not os.getenv("HEYGEN_API_KEY"):
            log_warning("HEYGEN_API_KEY missing; video generation job skipped.")
            return

        try:
            from social_media.video_generator import VideoGenerator
        except ImportError as exc:
            log_error(f"Video generator module unavailable: {exc}")
            return

        try:
            generator = VideoGenerator("social_media/config.yaml", self.supabase_client)
            script_text = self.app.config.get(
                "VIDEO_SCHEDULER_DEFAULT_SCRIPT",
                "Refiloe daily motivational update for {date}."
            ).format(date=datetime.now(SA_TIMEZONE).strftime("%Y-%m-%d"))

            result = generator.generate_avatar_video(
                script_text=script_text,
                style="educational",
                metadata={"source": "scheduler.video_generation"},
            )

            video_url = result.get("video_url")
            if video_url:
                log_info(f"Video generation job queued asset: {video_url}")
            else:
                log_warning("Video generation job completed but no video URL was returned.")
        except ValueError as exc:
            # Raised when mandatory env vars for HeyGen are missing.
            log_warning(f"Video generation prerequisites not met: {exc}")
        except Exception as exc:  # pragma: no cover - network/API errors
            log_error(f"Unexpected error during video generation job: {exc}\n{traceback.format_exc()}")

    def run_content_generation(self) -> None:
        """Daily job at 6:00 AM SAST to generate fresh content."""
        if self.supabase_client is None:
            log_warning("Supabase client unavailable; skipping content generation job.")
            return

        if not os.getenv("ANTHROPIC_API_KEY"):
            log_warning("ANTHROPIC_API_KEY missing; content generation job skipped.")
            return

        try:
            from social_media.content_generator import ContentGenerator
        except ImportError as exc:
            log_error(f"Content generator module unavailable: {exc}")
            return

        try:
            generator = ContentGenerator("social_media/config.yaml", self.supabase_client)
            week_number = datetime.now(SA_TIMEZONE).isocalendar()[1]
            batch_size = int(self.app.config.get("CONTENT_SCHEDULER_BATCH_SIZE", 8))
            posts = generator.generate_batch(
                num_posts=batch_size,
                week_number=week_number,
                hook_variations=True,
            )
            log_info(f"Content generation job produced {len(posts)} posts.")
        except ValueError as exc:
            log_warning(f"Content generation prerequisites not met: {exc}")
        except Exception as exc:  # pragma: no cover - API errors
            log_error(f"Unexpected error during content generation job: {exc}\n{traceback.format_exc()}")

    def run_content_posting(self) -> None:
        """Interval job that runs every 30 minutes to post queued content."""
        if self.supabase_client is None:
            log_warning("Supabase client unavailable; skipping content posting job.")
            return

        try:
            now_sa = datetime.now(SA_TIMEZONE)
            response = (
                self.supabase_client.table("social_posts")
                .select("id, platform, scheduled_time, status")
                .eq("status", "scheduled")
                .lte("scheduled_time", now_sa.isoformat())
                .limit(int(self.app.config.get("CONTENT_POSTING_BATCH_LIMIT", 5)))
                .execute()
            )

            posts = getattr(response, "data", None) or []
            if not posts:
                log_info("No scheduled posts ready for publishing at this interval.")
                return

            log_info(f"Found {len(posts)} scheduled posts ready for publishing.")
            for post in posts:
                log_info(
                    "Post ready | id=%s platform=%s scheduled_time=%s",
                    post.get("id"),
                    post.get("platform"),
                    post.get("scheduled_time"),
                )
        except Exception as exc:  # pragma: no cover - Supabase/network errors
            log_error(f"Error while preparing posts for publishing: {exc}\n{traceback.format_exc()}")

    def run_analytics_collection(self) -> None:
        """Daily job at 11:00 PM SAST to collect analytics for published posts."""
        if self.supabase_client is None:
            log_warning("Supabase client unavailable; skipping analytics collection job.")
            return

        try:
            since = datetime.now(SA_TIMEZONE) - timedelta(days=1)
            response = (
                self.supabase_client.table("social_posts")
                .select("id, platform, facebook_post_id, published_time")
                .eq("status", "published")
                .gte("published_time", since.isoformat())
                .limit(int(self.app.config.get("ANALYTICS_COLLECTION_BATCH_LIMIT", 20)))
                .execute()
            )

            posts = getattr(response, "data", None) or []
            log_info(f"Analytics collection job inspecting {len(posts)} recent posts.")
        except Exception as exc:  # pragma: no cover - Supabase/network errors
            log_error(f"Error while collecting analytics: {exc}\n{traceback.format_exc()}")

    # --------------------------------------------------------------------- #
    # Status reporting helpers
    # --------------------------------------------------------------------- #
    def is_running(self) -> bool:
        """Return True when the background scheduler is active."""
        return self.scheduler.running

    def get_status(self) -> Dict[str, Any]:
        """Expose scheduler runtime and job metadata for monitoring endpoints."""
        job_summaries = []
        for job in self.scheduler.get_jobs():
            last_run = self._last_run.get(job.id)
            job_summaries.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                    "last_run": last_run,
                }
            )

        return {
            "running": self.scheduler.running,
            "job_count": len(job_summaries),
            "jobs": job_summaries,
        }


def create_social_media_scheduler(app, supabase_client) -> Optional[SocialMediaScheduler]:
    """
    Backwards-compatible factory used by existing code paths.

    Returns:
        Optional[SocialMediaScheduler]: Scheduler instance or None on failure.
    """
    try:
        scheduler = SocialMediaScheduler(app, supabase_client)
        return scheduler
    except Exception as exc:  # pragma: no cover - defensive guard
        log_error(f"Failed to create social media scheduler: {exc}\n{traceback.format_exc()}")
        return None
