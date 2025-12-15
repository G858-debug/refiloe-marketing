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

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import pytz
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import traceback

from utils.logger import log_error, log_info, log_warning
from utils.whatsapp_notifier import WhatsAppNotifier
from social_media.weekly_report import WeeklyReportGenerator

try:
    from social_media.utils.avatar_iv_tracker import get_avatar_iv_credit_status
except ImportError:
    from utils.avatar_iv_tracker import get_avatar_iv_credit_status


SA_TIMEZONE = pytz.timezone("Africa/Johannesburg")


class SocialMediaScheduler:
    """Wrapper around APScheduler with defensive job registration."""

    def __init__(self, app, supabase_client) -> None:
        self.app = app
        self.supabase_client = supabase_client
        self.scheduler = BackgroundScheduler(timezone=SA_TIMEZONE)
        self._jobs_registered = False
        self._last_run: Dict[str, Dict[str, Optional[str]]] = {}
        self.sa_tz = SA_TIMEZONE
        self.whatsapp = WhatsAppNotifier()
        self.report_generator = WeeklyReportGenerator(supabase_client)

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
    def fetch_orphaned_videos_job(self) -> None:
        """
        Fetch and update videos that are still processing on HeyGen.

        This job handles the async video generation pattern:
        1. Finds posts with status='generating' and a video_id
        2. Checks video completion status with HeyGen
        3. Updates posts when videos are ready
        """
        log_info("=" * 60)
        log_info("🎥 FETCH ORPHANED VIDEOS JOB STARTED")
        log_info("=" * 60)

        if not self.supabase_client:
            log_error("❌ Supabase client not initialized")
            return

        try:
            # Find posts with status='generating' then filter for video_id not null
            # Note: The custom Supabase REST client doesn't support .not_ chaining
            result = self.supabase_client.table('social_posts').select(
                'id, video_id, post_type, content_text, created_at, updated_at'
            ).eq('status', 'generating').execute()

            # Filter in Python for posts that have video_id
            posts = result.data if result.data else []
            posts = [post for post in posts if post.get('video_id') is not None]
            # Also check for posts stuck in 'generating' with NO video_id (worker timeout victims)
            posts_without_video_id = [post for post in (result.data or []) if not post.get('video_id')]

            log_info(f"📊 Found {len(posts)} posts with video_id in 'generating' status")
            log_info(f"📊 Found {len(posts_without_video_id)} posts stuck in 'generating' without video_id")

            # Filter posts that have been stuck for MORE than 5 minutes
            # This prevents race conditions where we reset posts while video generation is still in progress
            stuck_threshold = datetime.now(SA_TIMEZONE) - timedelta(minutes=5)
            truly_stuck_posts = []

            for post in posts_without_video_id:
                updated_at_str = post.get('updated_at')
                if updated_at_str:
                    try:
                        # Parse the updated_at timestamp (assumes ISO format with timezone)
                        updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                        # Convert to SA timezone for comparison
                        if updated_at.tzinfo is None:
                            updated_at = updated_at.replace(tzinfo=timezone.utc)
                        updated_at_sa = updated_at.astimezone(SA_TIMEZONE)

                        # Check if post has been stuck for more than 5 minutes
                        if updated_at_sa < stuck_threshold:
                            time_stuck = datetime.now(SA_TIMEZONE) - updated_at_sa
                            minutes_stuck = int(time_stuck.total_seconds() / 60)
                            post['_minutes_stuck'] = minutes_stuck
                            truly_stuck_posts.append(post)
                    except Exception as e:
                        log_warning(f"⚠️  Could not parse updated_at for post {post.get('id')}: {e}")
                        # Include post if we can't parse timestamp (defensive fallback)
                        truly_stuck_posts.append(post)

            log_info(f"📊 Found {len(truly_stuck_posts)} posts stuck for >5 minutes (filtered from {len(posts_without_video_id)} total)")

            # Reset stuck posts without video_id back to approved
            if truly_stuck_posts:
                log_warning(f"⚠️  Resetting {len(truly_stuck_posts)} stuck posts to 'approved' status")

                for stuck_post in truly_stuck_posts:
                    post_id = stuck_post.get('id')
                    minutes_stuck = stuck_post.get('_minutes_stuck', 'unknown')
                    try:
                        self.supabase_client.table('social_posts').update({
                            'status': 'approved',
                            'video_id': None,
                            'updated_at': datetime.now(timezone.utc).isoformat()
                        }).eq('id', post_id).execute()

                        log_info(f"✅ Reset stuck post {post_id} to approved status (stuck for {minutes_stuck} minutes)")
                    except Exception as e:
                        log_error(f"❌ Failed to reset post {post_id}: {e}")

            # If no posts with video_id to check, we're done
            if not posts:
                log_info("✅ No videos with video_id to check")
                log_info("=" * 60)
                log_info(f"✅ Fetch job complete: 0 videos retrieved, {len(truly_stuck_posts)} stuck posts reset")
                log_info("=" * 60)
                return

            # Initialize video generator for status checks
            from social_media.video_generator import VideoGenerator
            video_gen = VideoGenerator('social_media/config.yaml', self.supabase_client)

            videos_completed = 0
            videos_still_processing = 0
            videos_failed = 0

            for post in posts:
                post_id = post.get('id')
                video_id = post.get('video_id')

                log_info(f"\n--- Checking Post {post_id} ---")
                log_info(f"Video ID: {video_id}")

                try:
                    # Check video status with HeyGen
                    status_result = video_gen.check_video_status(video_id)

                    video_status = status_result.get('status')
                    video_url = status_result.get('video_url')
                    error = status_result.get('error')

                    log_info(f"HeyGen status: {video_status}")

                    if video_status == 'completed' and video_url:
                        # Video is ready! Update post
                        log_info(f"✅ Video completed: {video_url}")

                        self.supabase_client.table('social_posts').update({
                            'video_url': video_url,
                            'status': 'pending_approval',
                            'media_generation_completed_at': datetime.now(SA_TIMEZONE).isoformat(),
                            'updated_at': datetime.now(SA_TIMEZONE).isoformat()
                        }).eq('id', post_id).execute()

                        log_info(f"✅ Post {post_id} updated to pending_approval")
                        videos_completed += 1

                    elif video_status == 'failed' or (error and 'not found' in str(error).lower()):
                        # Video failed or not found
                        log_error(f"❌ Video failed for post {post_id}: {error or video_status}")

                        # Reset to approved so user can retry
                        self.supabase_client.table('social_posts').update({
                            'status': 'approved',
                            'video_id': None,
                            'updated_at': datetime.now(SA_TIMEZONE).isoformat()
                        }).eq('id', post_id).execute()

                        log_info(f"🔄 Post {post_id} reset to approved for retry")
                        videos_failed += 1

                    elif video_status in ['processing', 'pending', 'unknown']:
                        # Still processing - check again next run
                        log_info(f"⏳ Video still processing for post {post_id}")
                        videos_still_processing += 1

                    else:
                        # Unexpected status
                        log_warning(f"⚠️ Unexpected video status '{video_status}' for post {post_id}")
                        videos_still_processing += 1

                except Exception as e:
                    log_error(f"❌ Error checking video {video_id} for post {post_id}: {e}")
                    log_error(f"Traceback: {traceback.format_exc()}")
                    videos_failed += 1

            log_info("=" * 60)
            log_info(f"✅ Fetch job complete:")
            log_info(f"   - Completed: {videos_completed}")
            log_info(f"   - Still processing: {videos_still_processing}")
            log_info(f"   - Failed: {videos_failed}")
            log_info("=" * 60)

        except Exception as e:
            log_error(f"❌ Fetch orphaned videos job failed: {e}")
            log_error(f"Traceback: {traceback.format_exc()}")

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
            {
                "id": "weekly_report_generation",
                "name": "Weekly Report Generation",
                "trigger": CronTrigger(day_of_week="sat", hour=20, minute=0, timezone=SA_TIMEZONE),
                "callable": self._wrap_job("weekly_report_generation", self.run_weekly_report),
            },
            {
                "id": "comment_processing_interval",
                "name": "Facebook Comment Processing",
                "trigger": IntervalTrigger(minutes=15, timezone=SA_TIMEZONE),
                "callable": self._wrap_job("comment_processing_interval", self.run_comment_processing),
            },
            {
                "id": "fetch_orphaned_videos",
                "name": "Fetch Orphaned Videos",
                "trigger": IntervalTrigger(minutes=2, timezone=SA_TIMEZONE),
                "callable": self._wrap_job("fetch_orphaned_videos", self.fetch_orphaned_videos_job),
            },
            {
                "id": "weekly_manual_video_reminder",
                "name": "Weekly Manual Video Reminder",
                "trigger": CronTrigger(day_of_week="sun", hour=9, minute=0, timezone=SA_TIMEZONE),
                "callable": self._wrap_job("weekly_manual_video_reminder", self.run_weekly_manual_video_reminder),
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

        # Log Avatar IV credit status at start of job
        try:
            credit_status = get_avatar_iv_credit_status(self.supabase_client)
            log_info(
                f"📊 Avatar IV Credit Status: "
                f"{credit_status.get('used_minutes', 0):.2f}/{credit_status.get('total_credits', 60)} minutes used "
                f"({credit_status.get('percentage_used', 0):.1f}%), "
                f"{credit_status.get('remaining_minutes', 0):.2f} minutes remaining"
            )

            # Warn if credits are running low (>80% used)
            if credit_status.get('percentage_used', 0) > 80:
                log_warning(
                    f"⚠️  Avatar IV credits running low: "
                    f"{credit_status.get('percentage_used', 0):.1f}% used"
                )
        except Exception as exc:
            log_warning(f"Could not fetch Avatar IV credit status: {exc}")

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

            # Track video generation outcomes
            api_generated_count = 0
            manual_flagged_count = 0

            for post in posts:
                if post.get("post_type") == "video":
                    # Check if post was flagged for manual creation
                    video_assets = post.get("assets", {}).get("video", {})
                    if video_assets.get("requires_manual_video"):
                        manual_flagged_count += 1
                    elif video_assets.get("video_source") == "avatar_iv_api":
                        api_generated_count += 1

            # Log video generation summary
            if api_generated_count > 0 or manual_flagged_count > 0:
                log_info(
                    f"📹 Video generation summary: "
                    f"{api_generated_count} generated via Avatar IV API, "
                    f"{manual_flagged_count} flagged for manual creation"
                )

            # Send notification if many posts flagged for manual creation
            if manual_flagged_count > 3:
                log_warning(
                    f"⚠️  High number of posts flagged for manual video creation: {manual_flagged_count}"
                )
                self._send_notification(
                    "warning",
                    f"{manual_flagged_count} posts require manual video creation",
                    {
                        "manual_flagged_count": manual_flagged_count,
                        "api_generated_count": api_generated_count,
                        "credit_status": credit_status if 'credit_status' in locals() else None,
                        "message": (
                            f"{manual_flagged_count} posts were flagged for manual video creation "
                            f"due to Avatar IV credit exhaustion. Check the pending scripts dashboard."
                        )
                    }
                )

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
            # IMPORTANT: Only fetch posts with status='scheduled'
            # This ensures BOTH approval stages are complete:
            # 1. Media approval (media_approved=True)
            # 2. Content approval (content_approved=True)
            # Posts are only set to 'scheduled' status after both approvals
            now_sa = datetime.now(SA_TIMEZONE)
            response = (
                self.supabase_client.table("social_posts")
                .select("*")  # Get all fields including content_text, metadata, etc.
                .eq("status", "scheduled")  # Only posts that passed BOTH approval stages
                .lte("scheduled_time", now_sa.isoformat())  # Scheduled time has been reached
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

                # Update in database (SupabaseRestClient.update() already executes and returns ExecuteResult)
                self.supabase_client.table("social_posts").update(update_data).eq(
                    "id", post_id
                )

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

            # Update in database (SupabaseRestClient.update() already executes and returns ExecuteResult)
            result = self.supabase_client.table("social_posts").update(update_data).eq(
                "id", post_id
            )

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

            # Update in database (SupabaseRestClient.update() already executes and returns ExecuteResult)
            result = self.supabase_client.table("social_posts").update(update_data).eq(
                "id", post_id
            )

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
        Send notification via WhatsApp and logging.

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

        # Send via WhatsApp for important notifications
        important_types = ['failure', 'error', 'viral', 'milestone']
        if notification_type in important_types and self.whatsapp:
            try:
                self.whatsapp.send_alert(
                    notification_type,
                    message,
                    details
                )
            except Exception as e:
                log_error(f"Failed to send WhatsApp notification: {e}")

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

    def run_weekly_report(self) -> None:
        """Generate and send weekly performance report via WhatsApp."""
        try:
            log_info("Starting weekly report generation...")

            # Generate report
            report = self.report_generator.generate_report()

            # Format for WhatsApp
            whatsapp_text = self.report_generator.format_for_whatsapp()

            # Send via WhatsApp
            result = self.whatsapp.send_weekly_report(whatsapp_text)

            if result.get('success'):
                log_info("Weekly report sent successfully via WhatsApp")
            else:
                log_error(f"Failed to send weekly report: {result.get('error')}")

            # Also save to database for dashboard
            self._save_report_to_database(report)

        except Exception as e:
            log_error(f"Error in weekly report job: {e}")
            # Try to send error notification
            self.whatsapp.send_alert(
                'error',
                'Weekly Report Failed',
                {'error': str(e)}
            )

    def run_comment_processing(self) -> None:
        """
        Process Facebook comments every 15 minutes with AI-powered auto-replies.
        """
        if self.supabase_client is None:
            log_warning("Supabase client unavailable; skipping comment processing job.")
            return

        if not os.getenv("ANTHROPIC_API_KEY"):
            log_warning("ANTHROPIC_API_KEY missing; comment processing job skipped.")
            return

        if not os.getenv("PAGE_ACCESS_TOKEN"):
            log_warning("PAGE_ACCESS_TOKEN missing; comment processing job skipped.")
            return

        try:
            from social_media.comment_manager import CommentManager
            from facebook_poster import FacebookPoster
        except ImportError as exc:
            log_error(f"Comment manager or Facebook poster module unavailable: {exc}")
            return

        try:
            # Initialize Facebook poster
            page_access_token = os.getenv("PAGE_ACCESS_TOKEN")
            page_id = os.getenv("PAGE_ID")

            if not page_id:
                log_warning("PAGE_ID missing; comment processing job skipped.")
                return

            facebook_poster = FacebookPoster(page_access_token, page_id, self.supabase_client)

            # Initialize comment manager
            comment_manager = CommentManager(
                self.supabase_client,
                facebook_poster,
                config=None  # Will load from config.yaml
            )

            # Process new comments
            log_info("Starting comment processing cycle")
            results = comment_manager.process_new_comments()

            # Log results
            total = results.get("total_comments", 0)
            processed = results.get("processed", 0)
            replied = results.get("replied", 0)
            flagged = results.get("flagged", 0)
            errors = results.get("errors", 0)

            log_info(
                f"Comment processing completed: {total} new comments, "
                f"{processed} processed, {replied} replied, {flagged} flagged, {errors} errors"
            )

            # Send notification if there are flagged comments
            if flagged > 0:
                self._send_notification(
                    "info",
                    f"{flagged} comments flagged for review",
                    {
                        "flagged_count": flagged,
                        "total_comments": total,
                        "message": f"{flagged} comments require human review."
                    }
                )

        except Exception as exc:  # pragma: no cover - unexpected errors
            log_error(f"Unexpected error during comment processing job: {exc}\n{traceback.format_exc()}")

    def run_weekly_manual_video_reminder(self) -> None:
        """Weekly reminder every Sunday at 9:00 AM SAST about pending manual videos.

        Checks if there are posts with requires_manual_video=true for the upcoming week
        and sends a WhatsApp notification with count and link to the pending scripts dashboard.
        """
        if self.supabase_client is None:
            log_warning("Supabase client unavailable; skipping weekly manual video reminder.")
            return

        try:
            # Get date range for upcoming week (next 7 days)
            now_sa = datetime.now(SA_TIMEZONE)
            week_from_now = now_sa + timedelta(days=7)

            # Query posts with requires_manual_video=true scheduled in next 7 days
            response = (
                self.supabase_client.table("social_posts")
                .select("id, content_text, scheduled_time, post_type")
                .eq("requires_manual_video", True)
                .gte("scheduled_time", now_sa.isoformat())
                .lte("scheduled_time", week_from_now.isoformat())
                .execute()
            )

            pending_posts = response.data if response.data else []
            pending_count = len(pending_posts)

            log_info(
                f"📹 Weekly manual video reminder: {pending_count} posts "
                f"require manual video creation for upcoming week"
            )

            # Send notification if there are pending manual videos
            if pending_count > 0:
                # Get base URL for dashboard link
                dashboard_url = os.getenv("APP_BASE_URL", "http://localhost:5001")
                pending_scripts_url = f"{dashboard_url}/admin/pending-scripts"

                self._send_notification(
                    "warning",
                    f"{pending_count} videos need manual creation this week",
                    {
                        "pending_count": pending_count,
                        "week_start": now_sa.strftime("%Y-%m-%d"),
                        "week_end": week_from_now.strftime("%Y-%m-%d"),
                        "dashboard_link": pending_scripts_url,
                        "message": (
                            f"📹 Weekly Reminder:\n\n"
                            f"{pending_count} video script(s) are pending manual Avatar IV creation "
                            f"for the upcoming week ({now_sa.strftime('%b %d')} - {week_from_now.strftime('%b %d')}).\n\n"
                            f"View pending scripts:\n{pending_scripts_url}"
                        )
                    }
                )

                # Also log details about the pending posts
                for idx, post in enumerate(pending_posts[:5], 1):  # Log first 5
                    scheduled_time = post.get("scheduled_time", "Unknown")
                    content_preview = (post.get("content_text") or "")[:50]
                    log_info(
                        f"  {idx}. Post {post.get('id')}: "
                        f"scheduled {scheduled_time} - {content_preview}..."
                    )

                if pending_count > 5:
                    log_info(f"  ... and {pending_count - 5} more")
            else:
                log_info("✅ No pending manual videos for upcoming week - all clear!")

        except Exception as exc:
            log_error(f"Error in weekly manual video reminder job: {exc}\n{traceback.format_exc()}")

    def _save_report_to_database(self, report: Dict[str, Any]) -> None:
        """
        Save weekly report to database for dashboard viewing.

        Args:
            report: Report data dictionary containing metrics and metadata
        """
        try:
            report_record = {
                "id": str(uuid.uuid4()),
                "report_date": datetime.now(SA_TIMEZONE).date().isoformat(),
                "metrics_json": report,
                "sent_at": datetime.now(SA_TIMEZONE).isoformat(),
                "created_at": datetime.now(SA_TIMEZONE).isoformat()
            }

            # Save to weekly_reports table
            result = self.supabase_client.table("weekly_reports").insert(report_record)

            if hasattr(result, "data") and result.data:
                log_info(f"Weekly report saved to database with ID: {report_record['id']}")
            else:
                log_warning("Weekly report generated but could not be saved to database")

        except Exception as exc:
            # Don't fail the job if saving fails - report was still generated
            log_warning(f"Could not save weekly report to database: {exc}")
            log_warning("Report was still generated successfully - database save is optional")

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
