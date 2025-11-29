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
import time
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
            # TEMPORARILY DISABLED - Modifying video generation codebase
            # To re-enable: uncomment this job definition
            # {
            #     "id": "video_generation_daily",
            #     "name": "Daily Video Generation",
            #     "trigger": CronTrigger(hour=5, minute=0, timezone=SA_TIMEZONE),
            #     "callable": self._wrap_job("video_generation_daily", self.run_video_generation),
            # },
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
            {
                "id": "weekly_avatar_looks",
                "name": "Weekly Avatar Looks Generation",
                "trigger": CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=SA_TIMEZONE),
                "callable": self._wrap_job("weekly_avatar_looks", self.run_weekly_avatar_looks),
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

        # Delegate to the enhanced post_scheduled_content method
        self.post_scheduled_content()

    def post_scheduled_content(self) -> None:
        """
        Enhanced method to post scheduled content with retry logic and notifications.

        Features:
        - Queries database for posts with status='scheduled' and scheduled_time <= now
        - Posts to Facebook using FacebookPoster
        - Updates post status and stores facebook_post_id
        - Implements retry logic with exponential backoff (max 3 retries)
        - Sends notifications for successes, failures, and low content pipeline
        """
        if self.supabase_client is None:
            log_warning("Supabase client unavailable; skipping content posting.")
            return

        try:
            # Query posts ready to publish
            now_sa = datetime.now(SA_TIMEZONE)
            response = (
                self.supabase_client.table("social_posts")
                .select("*")  # Get all fields including content_text, metadata, etc.
                .eq("status", "scheduled")
                .lte("scheduled_time", now_sa.isoformat())
                .limit(int(self.app.config.get("CONTENT_POSTING_BATCH_LIMIT", 5)))
                .execute()
            )

            posts = getattr(response, "data", None) or []
            if not posts:
                log_info("No scheduled posts ready for publishing at this interval.")

                # Check content pipeline health
                self._check_content_pipeline()
                return

            log_info(f"Found {len(posts)} scheduled posts ready for publishing.")

            # Process each post
            for post in posts:
                self._process_post(post)

            # Check content pipeline health after processing
            self._check_content_pipeline()

        except Exception as exc:  # pragma: no cover - Supabase/network errors
            log_error(f"Error while posting scheduled content: {exc}\n{traceback.format_exc()}")
            self._send_notification(
                "error",
                f"Content posting job failed: {str(exc)}",
                {"error": str(exc)}
            )

    def _process_post(self, post: Dict[str, Any]) -> None:
        """
        Process a single post: attempt to publish with retry logic.

        Args:
            post: Post dictionary from database
        """
        post_id = post.get("id")
        platform = post.get("platform", "facebook")

        log_info(f"Processing post {post_id} for platform {platform}")

        # Currently only support Facebook
        if platform.lower() != "facebook":
            log_warning(f"Platform {platform} not yet supported, skipping post {post_id}")
            return

        # Check if Facebook credentials are available
        page_access_token = os.getenv("PAGE_ACCESS_TOKEN")
        page_id = os.getenv("PAGE_ID")

        if not page_access_token or not page_id:
            log_warning("Facebook credentials missing; cannot post content.")
            self._send_notification(
                "warning",
                "Facebook credentials missing",
                {"post_id": post_id}
            )
            return

        # Get retry metadata
        metadata = post.get("metadata") or {}
        retry_count = metadata.get("retry_count", 0)
        max_retries = 3

        # Check if max retries exceeded
        if retry_count >= max_retries:
            log_error(f"Post {post_id} has exceeded max retries ({max_retries}), marking as failed")
            self._mark_post_failed(post_id, "Maximum retry attempts exceeded")
            self._send_notification(
                "failure",
                f"Post {post_id} failed after {max_retries} retry attempts",
                {"post_id": post_id, "content_preview": post.get("content_text", "")[:100]}
            )
            return

        # Attempt to post
        try:
            from facebook_poster import FacebookPoster

            poster = FacebookPoster(page_access_token, page_id, self.supabase_client)

            # Prepare post data
            post_data = {
                "content_text": post.get("content_text", ""),
                "image_ids": post.get("image_ids") or [],
            }

            # Call Facebook API
            result = poster.post_to_page(post_data)

            if result.get("success"):
                # Post succeeded - update database
                facebook_post_id = result.get("post_id")
                self._mark_post_published(post_id, facebook_post_id)

                log_info(f"Successfully published post {post_id} as Facebook post {facebook_post_id}")
                self._send_notification(
                    "success",
                    f"Post published successfully",
                    {
                        "post_id": post_id,
                        "facebook_post_id": facebook_post_id,
                        "content_preview": post.get("content_text", "")[:100]
                    }
                )
            else:
                # Post failed - implement retry logic
                error_message = result.get("error", "Unknown error")
                log_error(f"Failed to post {post_id}: {error_message}")

                # Increment retry count and schedule retry with exponential backoff
                self._handle_post_failure(post_id, retry_count, error_message)

        except ImportError:
            log_error("FacebookPoster module not available")
            self._send_notification(
                "error",
                "FacebookPoster module not available",
                {"post_id": post_id}
            )
        except Exception as exc:
            log_error(f"Unexpected error posting {post_id}: {exc}\n{traceback.format_exc()}")
            self._handle_post_failure(post_id, retry_count, str(exc))

    def _handle_post_failure(self, post_id: str, retry_count: int, error_message: str) -> None:
        """
        Handle post failure with retry logic and exponential backoff.

        Args:
            post_id: Post UUID
            retry_count: Current retry count
            error_message: Error message from failed attempt
        """
        max_retries = 3
        new_retry_count = retry_count + 1

        if new_retry_count >= max_retries:
            # Max retries reached - mark as failed
            self._mark_post_failed(post_id, error_message)
            self._send_notification(
                "failure",
                f"Post {post_id} failed after {max_retries} attempts",
                {"post_id": post_id, "final_error": error_message}
            )
        else:
            # Schedule retry with exponential backoff
            backoff_minutes = 2 ** new_retry_count  # 2, 4, 8 minutes
            next_attempt = datetime.now(SA_TIMEZONE) + timedelta(minutes=backoff_minutes)

            log_info(f"Scheduling retry {new_retry_count}/{max_retries} for post {post_id} at {next_attempt}")

            # Update metadata with retry info
            try:
                # Get current post data to preserve existing metadata
                post_response = (
                    self.supabase_client.table("social_posts")
                    .select("metadata")
                    .eq("id", post_id)
                    .single()
                    .execute()
                )

                current_metadata = {}
                if post_response.data:
                    current_metadata = post_response.data.get("metadata") or {}

                # Update retry metadata
                current_metadata["retry_count"] = new_retry_count
                current_metadata["last_error"] = error_message
                current_metadata["last_attempt"] = datetime.now(SA_TIMEZONE).isoformat()
                current_metadata["next_attempt"] = next_attempt.isoformat()

                # Update post with new metadata and scheduled time
                update_data = {
                    "metadata": current_metadata,
                    "scheduled_time": next_attempt.isoformat(),
                    "updated_at": datetime.now(SA_TIMEZONE).isoformat()
                }

                self.supabase_client.table("social_posts").update(update_data).eq(
                    "id", post_id
                ).execute()

                log_info(f"Updated post {post_id} for retry {new_retry_count} in {backoff_minutes} minutes")

            except Exception as exc:
                log_error(f"Failed to update retry metadata for post {post_id}: {exc}")

    def _mark_post_published(self, post_id: str, facebook_post_id: str) -> None:
        """
        Mark post as published and store Facebook post ID.

        Args:
            post_id: Post UUID
            facebook_post_id: Facebook's post ID
        """
        try:
            update_data = {
                "status": "published",
                "facebook_post_id": facebook_post_id,
                "published_time": datetime.now(SA_TIMEZONE).isoformat(),
                "updated_at": datetime.now(SA_TIMEZONE).isoformat()
            }

            result = self.supabase_client.table("social_posts").update(update_data).eq(
                "id", post_id
            ).execute()

            if result.data:
                log_info(f"Post {post_id} marked as published with Facebook ID: {facebook_post_id}")
            else:
                log_error(f"Failed to update post {post_id} status to published")

        except Exception as exc:
            log_error(f"Error marking post {post_id} as published: {exc}")

    def _mark_post_failed(self, post_id: str, error_message: str) -> None:
        """
        Mark post as failed after max retries.

        Args:
            post_id: Post UUID
            error_message: Final error message
        """
        try:
            # Get current metadata to preserve it
            post_response = (
                self.supabase_client.table("social_posts")
                .select("metadata")
                .eq("id", post_id)
                .single()
                .execute()
            )

            metadata = {}
            if post_response.data:
                metadata = post_response.data.get("metadata") or {}

            # Add failure info to metadata
            metadata["failed_at"] = datetime.now(SA_TIMEZONE).isoformat()
            metadata["failure_reason"] = error_message

            update_data = {
                "status": "failed",
                "metadata": metadata,
                "updated_at": datetime.now(SA_TIMEZONE).isoformat()
            }

            result = self.supabase_client.table("social_posts").update(update_data).eq(
                "id", post_id
            ).execute()

            if result.data:
                log_info(f"Post {post_id} marked as failed: {error_message}")
            else:
                log_error(f"Failed to update post {post_id} status to failed")

        except Exception as exc:
            log_error(f"Error marking post {post_id} as failed: {exc}")

    def _check_content_pipeline(self) -> None:
        """
        Check if content pipeline is healthy (at least 3 days of scheduled content).
        Send notification if running low on content.
        """
        try:
            now_sa = datetime.now(SA_TIMEZONE)
            three_days_from_now = now_sa + timedelta(days=3)

            # Count scheduled posts in next 3 days
            response = (
                self.supabase_client.table("social_posts")
                .select("id", count="exact")
                .eq("status", "scheduled")
                .gte("scheduled_time", now_sa.isoformat())
                .lte("scheduled_time", three_days_from_now.isoformat())
                .execute()
            )

            count = response.count if hasattr(response, "count") else len(response.data or [])

            if count < 3:
                log_warning(f"Low content pipeline: only {count} posts scheduled in next 3 days")
                self._send_notification(
                    "warning",
                    f"Low content pipeline detected",
                    {
                        "scheduled_posts_count": count,
                        "threshold": 3,
                        "period_days": 3,
                        "message": f"Only {count} posts scheduled for the next 3 days. Consider generating more content."
                    }
                )
            else:
                log_info(f"Content pipeline healthy: {count} posts scheduled in next 3 days")

        except Exception as exc:
            log_error(f"Error checking content pipeline: {exc}")

    def _send_notification(self, notification_type: str, message: str, details: Dict[str, Any]) -> None:
        """
        Send notification for post events.

        Future implementation: Email/Slack notifications
        Current implementation: Structured logging

        Args:
            notification_type: Type of notification (success, failure, warning, error)
            message: Notification message
            details: Additional details dictionary
        """
        notification_data = {
            "type": notification_type,
            "message": message,
            "timestamp": datetime.now(SA_TIMEZONE).isoformat(),
            "details": details
        }

        if notification_type == "success":
            log_info(f"✅ NOTIFICATION [{notification_type.upper()}]: {message} | Details: {details}")
        elif notification_type == "failure":
            log_error(f"❌ NOTIFICATION [{notification_type.upper()}]: {message} | Details: {details}")
        elif notification_type == "warning":
            log_warning(f"⚠️  NOTIFICATION [{notification_type.upper()}]: {message} | Details: {details}")
        elif notification_type == "error":
            log_error(f"🚨 NOTIFICATION [{notification_type.upper()}]: {message} | Details: {details}")
        else:
            log_info(f"📢 NOTIFICATION [{notification_type.upper()}]: {message} | Details: {details}")

        # TODO: Implement email notifications
        # TODO: Implement Slack notifications

    def run_weekly_avatar_looks(self) -> None:
        """Weekly job at 3:00 AM SAST every Sunday to generate fresh avatar looks.

        Generates 2-3 new looks with different themes to keep content visually varied.
        Each look is generated with motion and saved to the avatar_looks table.
        """
        if self.supabase_client is None:
            log_warning("Supabase client unavailable; skipping weekly avatar looks job.")
            return

        if not os.getenv("HEYGEN_API_KEY"):
            log_warning("HEYGEN_API_KEY missing; weekly avatar looks job skipped.")
            return

        if not os.getenv("HEYGEN_AVATAR_GROUP"):
            log_warning("HEYGEN_AVATAR_GROUP missing; weekly avatar looks job skipped.")
            return

        try:
            from social_media.looks_generator import (
                LooksGenerator,
                LookGenerationError,
                MotionAdditionError,
            )
        except ImportError as exc:
            log_error(f"LooksGenerator module unavailable: {exc}")
            return

        # Define theme categories with their associated look types
        # We rotate through these themes to provide visual variety
        theme_rotation = [
            {"theme": "gym", "looks": ["gym_trainer", "home_workout"]},
            {"theme": "office", "looks": ["office_professional"]},
            {"theme": "outdoor", "looks": ["outdoor_wellness", "retreat_leader"]},
            {"theme": "casual", "looks": ["podcast_host", "yoga_instructor"]},
            {"theme": "professional", "looks": ["motivational_speaker", "nutrition_expert", "studio_portrait"]},
        ]

        # Determine which themes to use this week based on week number
        week_number = datetime.now(SA_TIMEZONE).isocalendar()[1]
        num_looks = 2 + (week_number % 2)  # Alternates between 2 and 3 looks

        # Select themes based on week rotation (ensures different themes each week)
        selected_themes = []
        for i in range(num_looks):
            theme_index = (week_number + i) % len(theme_rotation)
            selected_themes.append(theme_rotation[theme_index])

        log_info(
            f"Weekly avatar looks job starting: generating {num_looks} looks "
            f"for week {week_number} with themes: {[t['theme'] for t in selected_themes]}"
        )

        try:
            generator = LooksGenerator(self.supabase_client)
        except ValueError as exc:
            log_warning(f"LooksGenerator initialization failed: {exc}")
            return

        # Track results for logging
        successful_looks = []
        failed_looks = []

        for theme_info in selected_themes:
            theme = theme_info["theme"]
            look_options = theme_info["looks"]

            # Select a specific look from the theme based on week number
            look_index = week_number % len(look_options)
            look_type = look_options[look_index]

            log_info(f"Generating avatar look: {look_type} (theme: {theme})")

            try:
                # Generate look with motion and save to database
                result = generator.generate_look_with_motion(
                    look_type=look_type,
                    motion_prompt="natural head movement and subtle expressions",
                    motion_type="natural",
                    save_to_database=True,
                )

                record_id = result.get("database_record_id")
                look_id = result.get("look_id")
                photo_avatar_id = result.get("photo_avatar_id")

                if record_id:
                    successful_looks.append({
                        "look_type": look_type,
                        "theme": theme,
                        "record_id": record_id,
                        "look_id": look_id,
                        "photo_avatar_id": photo_avatar_id,
                    })
                    log_info(
                        f"Avatar look '{look_type}' generated successfully "
                        f"(record_id={record_id}, look_id={look_id}, "
                        f"photo_avatar_id={photo_avatar_id})"
                    )
                else:
                    # Look generated but database save failed
                    successful_looks.append({
                        "look_type": look_type,
                        "theme": theme,
                        "record_id": None,
                        "look_id": look_id,
                        "photo_avatar_id": photo_avatar_id,
                        "warning": "Database save failed",
                    })
                    log_warning(
                        f"Avatar look '{look_type}' generated but database save failed "
                        f"(look_id={look_id})"
                    )

            except LookGenerationError as exc:
                failed_looks.append({
                    "look_type": look_type,
                    "theme": theme,
                    "error": f"Look generation failed: {exc}",
                })
                log_error(f"Failed to generate look '{look_type}': {exc}")
                # Continue to next look - don't let one failure stop the job

            except MotionAdditionError as exc:
                failed_looks.append({
                    "look_type": look_type,
                    "theme": theme,
                    "error": f"Motion addition failed: {exc}",
                })
                log_error(f"Failed to add motion to look '{look_type}': {exc}")
                # Continue to next look

            except Exception as exc:
                failed_looks.append({
                    "look_type": look_type,
                    "theme": theme,
                    "error": f"Unexpected error: {exc}",
                })
                log_error(
                    f"Unexpected error generating look '{look_type}': {exc}\n"
                    f"{traceback.format_exc()}"
                )
                # Continue to next look

        # Log summary
        log_info(
            f"Weekly avatar looks job completed: "
            f"{len(successful_looks)} successful, {len(failed_looks)} failed"
        )

        if successful_looks:
            look_ids = [l.get("look_id", "unknown") for l in successful_looks]
            log_info(f"Generated look IDs: {look_ids}")

        if failed_looks:
            log_warning(f"Failed looks: {[l['look_type'] for l in failed_looks]}")

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
