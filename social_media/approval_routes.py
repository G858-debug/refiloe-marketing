"""Flask blueprint providing routes for the social content approval workflow."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from social_media.database import SocialMediaDatabase
from social_media.title_card_service import TitleCardService
from utils.supabase_rest import SupabaseRestClient
from utils.logger import log_error, log_info, log_warning
from facebook_poster import FacebookPoster
import pytz


approval_bp = Blueprint(
    "approval",
    __name__,
    url_prefix="/approval",
    template_folder="templates",
)


_supabase_client = None
_database_service: Optional[SocialMediaDatabase] = None
_video_table = os.getenv("HEYGEN_VIDEO_TABLE", "generated_videos")


def _current_iso_timestamp(db: Optional[SocialMediaDatabase] = None) -> str:
    """Return current timestamp in ISO format, using SA timezone when available."""

    if db and hasattr(db, "sa_tz"):
        return datetime.now(db.sa_tz).isoformat()
    return datetime.utcnow().isoformat()


def _ensure_database() -> Optional[SocialMediaDatabase]:
    """Return a cached instance of :class:`SocialMediaDatabase`.

    Creates a Supabase client on first call using environment configuration.
    """

    global _supabase_client, _database_service

    if _database_service is not None:
        return _database_service

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        log_error("Supabase credentials are missing for approval routes")
        return None

    try:
        _supabase_client = SupabaseRestClient(url, key)
        _database_service = SocialMediaDatabase(_supabase_client)
        log_info("Approval routes connected to Supabase")
    except Exception as exc:  # pragma: no cover - defensive logging
        log_error(f"Failed to initialize Supabase for approval routes: {exc}")
        _supabase_client = None
        _database_service = None

    return _database_service


def _fetch_post(db: SocialMediaDatabase, post_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single post by ID."""

    try:
        log_info(f"Fetching post with ID: {post_id}")

        result = (
            db.db.table("social_posts")
            .select("*")
            .eq("id", post_id)
            .limit(1)
        )

        log_info(f"Fetch result type: {type(result)}")

        if hasattr(result, "execute"):
            result = result.execute()
            log_info(f"Executed fetch result type: {type(result)}")

        if hasattr(result, "data") and result.data:
            if isinstance(result.data, list) and len(result.data) > 0:
                log_info(f"Post found: {result.data[0]}")
                return _normalize_post_data(result.data[0])
            if isinstance(result.data, dict):
                log_info(f"Post found: {result.data}")
                return _normalize_post_data(result.data)

        log_error(f"Post not found with ID: {post_id}")
        return None
    except Exception as exc:
        log_error(f"Error fetching post {post_id}: {exc}")
        return None


def _normalize_post_data(post: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize post data to ensure all template fields are present."""
    if not post:
        return post

    # Map content_text to content for template compatibility
    if 'content_text' in post and 'content' not in post:
        post['content'] = post['content_text']

    # Ensure title exists
    if 'title' not in post:
        # Generate title from content or use default
        content = post.get('content') or post.get('content_text', '')
        if content:
            post['title'] = content[:50] + '...' if len(content) > 50 else content
        else:
            post['title'] = f"Post {post.get('id', 'Unknown')[:8]}"

    # Ensure created_at is present
    if 'created_at' not in post:
        post['created_at'] = datetime.utcnow().isoformat()

    # Ensure metadata is a dict
    if 'metadata' not in post or post['metadata'] is None:
        post['metadata'] = {}

    return post


def _fetch_post_images(db: SocialMediaDatabase, post_id: str) -> list[Dict[str, Any]]:
    """Retrieve image records linked to the given post."""

    try:
        result = (
            db.db.table("social_images")
            .select("*")
            .eq("post_id", post_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        log_error(f"Error fetching images for post {post_id}: {exc}")
        return []


def _fetch_post_video(db: SocialMediaDatabase, post_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent generated video linked to the post."""

    try:
        result = (
            db.db.table(_video_table)
            .select("*")
            .eq("post_id", post_id)
            .order("created_at", desc=True)
            .limit(1)
        )

        if hasattr(result, "execute"):
            result = result.execute()

        if hasattr(result, "data") and result.data:
            if isinstance(result.data, list) and len(result.data) > 0:
                return result.data[0]
            if isinstance(result.data, dict):
                return result.data
    except Exception as exc:
        log_error(f"Error fetching video for post {post_id}: {exc}")
    return None


def _update_post_fields(
    db: SocialMediaDatabase, post_id: str, fields: Dict[str, Any]
) -> bool:
    """Update specific fields on a post record."""

    try:
        response = db.db.table("social_posts").update(fields).eq("id", post_id).execute()
        if response.data:
            return True
        log_error(f"Update returned no data for post {post_id} with fields {fields.keys()}")
        return False
    except Exception as exc:
        log_error(f"Error updating post {post_id}: {exc}")
        return False


def _delete_post_cascade(db: SocialMediaDatabase, post_id: str) -> bool:
    """
    Delete a post and all its associated data (video, images).

    Args:
        db: Database instance
        post_id: ID of the post to delete

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        # Delete associated video(s) - note: some posts may not have videos
        try:
            # Delete from database (SupabaseRestClient.delete() already executes and returns ExecuteResult)
            video_result = db.db.table(_video_table).eq("post_id", post_id).delete()
            deleted_count = len(video_result.data) if video_result.data else 0
            if deleted_count > 0:
                log_info(f"Deleted {deleted_count} video(s) for post {post_id}")
            else:
                log_info(f"No videos found to delete for post {post_id}")
        except ValueError as ve:
            # This is expected if the filter is missing
            log_warning(f"Could not delete videos for post {post_id}: {ve}")
        except Exception as video_exc:
            # Log but don't fail - video table might not exist or video might not exist
            log_warning(f"Error deleting videos for post {post_id}: {video_exc}")

        # Delete associated images - note: some posts may not have images
        try:
            # Delete from database (SupabaseRestClient.delete() already executes and returns ExecuteResult)
            images_result = db.db.table("social_images").eq("post_id", post_id).delete()
            deleted_count = len(images_result.data) if images_result.data else 0
            if deleted_count > 0:
                log_info(f"Deleted {deleted_count} image(s) for post {post_id}")
            else:
                log_info(f"No images found to delete for post {post_id}")
        except ValueError as ve:
            log_warning(f"Could not delete images for post {post_id}: {ve}")
        except Exception as img_exc:
            # Log but don't fail - images table might not exist or images might not exist
            log_warning(f"Error deleting images for post {post_id}: {img_exc}")

        # Delete the post itself - THIS is the critical operation
        try:
            # Delete from database (SupabaseRestClient.delete() already executes and returns ExecuteResult)
            post_result = db.db.table("social_posts").eq("id", post_id).delete()

            # Check if deletion was successful
            if post_result.data:
                log_info(f"Successfully deleted post {post_id} (returned data: {len(post_result.data)} record(s))")
                return True
            else:
                # Some Supabase configurations return empty data on successful delete
                # Try to verify by checking if post still exists
                verify_result = db.db.table("social_posts").select("id").eq("id", post_id).execute()
                if not verify_result.data:
                    log_info(f"Successfully deleted post {post_id} (verified by query)")
                    return True
                else:
                    log_error(f"Failed to delete post {post_id} - post still exists after delete operation")
                    return False

        except Exception as post_exc:
            log_error(f"Failed to delete post {post_id}: {post_exc}")
            return False

    except Exception as exc:
        log_error(f"Error in cascade delete for post {post_id}: {exc}")
        return False


def _upload_video_draft_immediately(db: SocialMediaDatabase, post: Dict) -> Dict:
    """
    Upload a video post to Facebook as a scheduled post immediately upon approval.
    Automatically adds title card if source image and title are available.
    """
    import time as time_module

    page_access_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
    page_id = os.getenv("FACEBOOK_PAGE_ID")

    if not page_access_token or not page_id:
        log_warning("Facebook credentials missing; cannot upload video draft")
        return {'success': False, 'error': 'Facebook credentials missing'}

    try:
        # Calculate the scheduled timestamp
        scheduled_time = post.get('scheduled_time')
        schedule_timestamp = None

        if scheduled_time:
            try:
                from datetime import datetime as dt
                if isinstance(scheduled_time, str):
                    scheduled_dt = dt.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                else:
                    scheduled_dt = scheduled_time

                # Convert to Unix timestamp
                schedule_timestamp = int(scheduled_dt.timestamp())

                # Facebook requires at least 10 mins in future
                current_time = int(time_module.time())
                min_schedule_time = current_time + 600  # 10 minutes

                if schedule_timestamp < min_schedule_time:
                    log_info(f"Scheduled time {scheduled_dt} is less than 10 mins away, using minimum (10 mins from now)")
                    schedule_timestamp = min_schedule_time
                else:
                    log_info(f"Using post's scheduled time: {scheduled_dt} (timestamp: {schedule_timestamp})")

            except Exception as e:
                log_warning(f"Could not parse scheduled_time '{scheduled_time}': {e}")
                schedule_timestamp = int(time_module.time()) + 600
        else:
            log_info("No scheduled_time on post, defaulting to 10 mins from now")
            schedule_timestamp = int(time_module.time()) + 600

        # Get video and title card data
        video_url = post.get('video_url')
        source_image_url = post.get('image_url') or post.get('preview_url')
        title_text = post.get('reel_title') or post.get('title', '')

        # Process video with title card if we have all required data
        processed_video_path = None

        if video_url and source_image_url and title_text:
            try:
                log_info("=" * 60)
                log_info("TITLE CARD INTEGRATION - Starting")
                log_info(f"Video URL: {video_url}")
                log_info(f"Source image: {source_image_url}")
                log_info(f"Title: {title_text}")
                log_info("=" * 60)

                title_card_service = TitleCardService()

                result = title_card_service.create_video_with_title_card(
                    source_image_url=source_image_url,
                    video_url=video_url,
                    title_text=title_text,
                    title_card_duration=1.0
                )

                if result.get('success'):
                    processed_video_path = result.get('video_path')
                    thumbnail_path = result.get('thumbnail_path')
                    log_info(f"✓ Title card added successfully: {processed_video_path}")

                    # Save processed video URL and thumbnail to database
                    log_info("Updating post with processed_video_url and thumbnail_url...")
                    update_fields = {
                        'processed_video_url': processed_video_path,
                        'thumbnail_url': thumbnail_path
                    }
                    if _update_post_fields(db, post['id'], update_fields):
                        log_info(f"✓ Database updated: processed_video_url={processed_video_path}")
                        log_info(f"✓ Database updated: thumbnail_url={thumbnail_path}")
                    else:
                        log_warning("Failed to update post with processed video URL - continuing anyway")
                else:
                    log_warning(f"Title card processing failed: {result.get('error')}")
                    log_warning("Falling back to original video")
            except Exception as e:
                log_error(f"Title card service error: {e}")
                import traceback
                log_error(traceback.format_exc())
                log_warning("Falling back to original video")
        else:
            log_info("Skipping title card - missing required data")
            log_info(f"  video_url: {bool(video_url)}")
            log_info(f"  source_image_url: {bool(source_image_url)}")
            log_info(f"  title_text: {bool(title_text)}")

        # Prefer processed_video_url (with title card) over original video_url
        video_to_upload = post.get('processed_video_url') or video_url
        thumb_offset = 0 if post.get('processed_video_url') else 2000

        log_info(f"Video to upload: {video_to_upload}")
        log_info(f"Using thumb_offset={thumb_offset} ({'title card frame' if thumb_offset == 0 else 'default 2s offset'})")

        poster = FacebookPoster(page_access_token, page_id, db.db)

        # Prepare post data with schedule hint and scheduled_publish_time
        post_data = {
            'content_text': post.get('content_text', ''),
            'video_url': video_to_upload,
            'title': title_text,
            'post_as_draft': True,
            'include_schedule_hint': True,
            'scheduled_time': post.get('scheduled_time'),
            'scheduled_publish_time': schedule_timestamp,  # Pass the calculated timestamp
            'thumb_offset': thumb_offset,  # 0 for title card, 2000 for original
        }

        # Upload to Facebook as scheduled post
        result = poster._post_video(post_data)

        return result

    except Exception as e:
        log_error(f"Error uploading video draft: {e}")
        import traceback
        log_error(traceback.format_exc())
        return {'success': False, 'error': str(e)}


def _send_video_ready_notification(db: SocialMediaDatabase, post: Dict, facebook_post_id: str) -> None:
    """
    Send WhatsApp notification for video ready to add music.

    Args:
        db: Database instance
        post: Post record
        facebook_post_id: Facebook's video ID
    """
    try:
        from utils.whatsapp_notifier import WhatsAppNotifier

        SA_TZ = pytz.timezone('Africa/Johannesburg')

        notifier = WhatsAppNotifier()

        if not notifier.enabled:
            log_info("WhatsApp notifications disabled")
            return

        # Build Creator Studio URL
        creator_studio_url = f"https://business.facebook.com/latest/content_library?asset_id={facebook_post_id}"

        # Get video details
        video_title = post.get('title') or post.get('content_theme', '').replace('_', ' ').title() or 'Untitled Video'
        content_text = post.get('content_text', '')
        caption_preview = content_text[:150] + '...' if len(content_text) > 150 else content_text

        # Format scheduled time for the notification
        scheduled_time = post.get('scheduled_time')
        schedule_hint = ''
        if scheduled_time:
            try:
                if isinstance(scheduled_time, str):
                    scheduled_dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                else:
                    scheduled_dt = scheduled_time
                scheduled_dt = scheduled_dt.astimezone(SA_TZ)
                schedule_hint = f"\n\n📅 *Suggested posting:* {scheduled_dt.strftime('%a, %d %b %Y at %H:%M SAST')}"
            except Exception as e:
                log_warning(f"Could not format scheduled_time: {e}")

        # Send via template (or fallback)
        result = notifier.send_video_ready_template(
            video_title=video_title,
            creator_studio_url=creator_studio_url,
            caption_preview=caption_preview + schedule_hint
        )

        if result.get('success'):
            log_info(f"WhatsApp notification sent for video {post.get('id')}")
        else:
            log_warning(f"WhatsApp notification failed: {result.get('error')}")

    except Exception as e:
        log_error(f"Error sending video notification: {e}")
        import traceback
        log_error(traceback.format_exc())


def _resolve_actor() -> str:
    """Infer the actor performing the action from request context."""

    header_actor = (
        request.headers.get("X-User-Email")
        or request.headers.get("X-User-Name")
        or request.headers.get("X-User-Id")
    )
    if header_actor:
        return header_actor
    return request.remote_addr or "unknown"


def _get_facebook_poster(db: SocialMediaDatabase) -> Optional[FacebookPoster]:
    """Initialize and return a FacebookPoster instance."""
    page_access_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
    page_id = os.getenv("FACEBOOK_PAGE_ID")

    if not page_access_token or not page_id:
        log_error("Facebook credentials not configured")
        return None

    try:
        poster = FacebookPoster(page_access_token, page_id, db.db)
        return poster
    except Exception as exc:
        log_error(f"Failed to initialize FacebookPoster: {exc}")
        return None


def _should_post_immediately(post: Dict[str, Any]) -> bool:
    """Check if a post should be posted immediately based on its scheduled_time."""
    scheduled_time = post.get("scheduled_time")

    if not scheduled_time:
        # No scheduled time means post immediately
        return True

    try:
        # Parse the scheduled time
        if isinstance(scheduled_time, str):
            scheduled_dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
        else:
            scheduled_dt = scheduled_time

        # Make timezone-aware if needed
        if scheduled_dt.tzinfo is None:
            sa_tz = pytz.timezone('Africa/Johannesburg')
            scheduled_dt = sa_tz.localize(scheduled_dt)

        # Get current time in SA timezone
        now = datetime.now(pytz.timezone('Africa/Johannesburg'))

        # If scheduled time is in the past or within 1 minute from now, post immediately
        return scheduled_dt <= now
    except Exception as exc:
        log_error(f"Error parsing scheduled_time: {exc}")
        # On error, don't post immediately to be safe
        return False


def _post_to_facebook(db: SocialMediaDatabase, post: Dict[str, Any]) -> Dict[str, Any]:
    """Post content to Facebook and update the database.

    Returns:
        Dict with 'success' (bool), 'facebook_post_id' (str or None), and 'error' (str or None)
    """
    try:
        poster = _get_facebook_poster(db)
        if not poster:
            return {
                'success': False,
                'facebook_post_id': None,
                'error': 'Facebook poster not available'
            }

        # Post the content
        result = poster.post_approved_content(post)

        if result['success']:
            log_info(f"Successfully posted to Facebook: {result['post_id']}")
            return {
                'success': True,
                'facebook_post_id': result['post_id'],
                'error': None
            }
        else:
            log_error(f"Failed to post to Facebook: {result['error']}")
            # Update post status to failed
            _update_post_fields(db, post['id'], {
                'status': 'failed',
                'metadata': {
                    **(post.get('metadata') or {}),
                    'posting_error': result['error'],
                    'failed_at': _current_iso_timestamp(db)
                }
            })
            return {
                'success': False,
                'facebook_post_id': None,
                'error': result['error']
            }

    except Exception as exc:
        log_error(f"Exception while posting to Facebook: {exc}")
        # Update post status to failed
        _update_post_fields(db, post['id'], {
            'status': 'failed',
            'metadata': {
                **(post.get('metadata') or {}),
                'posting_error': str(exc),
                'failed_at': _current_iso_timestamp(db)
            }
        })
        return {
            'success': False,
            'facebook_post_id': None,
            'error': str(exc)
        }


@approval_bp.route("/pending", methods=["GET"])
def pending_posts():
    """Display all posts awaiting approval."""

    db = _ensure_database()
    if not db:
        return (
            render_template(
                "approval/error.html",
                message="Supabase connection is not configured.",
            ),
            503,
        )

    try:
        log_info("Fetching pending posts...")

        result = (
            db.db.table("social_posts")
            .select("*")
            .eq("status", "pending_approval")
            .order("created_at", desc=True)
        )
        log_info(f"Query result type: {type(result)}")

        if hasattr(result, "execute"):
            result = result.execute()
            log_info(f"Executed pending posts result: {result}")

        if hasattr(result, "data"):
            posts = result.data or []
        else:
            posts = []

        log_info(f"Found {len(posts)} pending posts")
    except Exception as exc:
        log_error(f"Error fetching pending posts: {exc}")
        return (
            render_template(
                "approval/error.html",
                message="Unable to load pending approvals at this time.",
            ),
            500,
        )

    return render_template("approval/pending.html", posts=posts)


@approval_bp.route("/view/<string:post_id>", methods=["GET"])
def view_post(post_id: str):
    """Render a detailed preview for a single post awaiting approval."""

    db = _ensure_database()
    if not db:
        return (
            render_template(
                "approval/error.html",
                message="Supabase connection is not configured.",
            ),
            503,
        )

    post = _fetch_post(db, post_id)
    if not post:
        return (
            render_template(
                "approval/error.html",
                message="The requested post could not be found.",
            ),
            404,
        )

    # Debug logging to see what we're getting
    log_info(f"Fetched post data: {json.dumps(post, indent=2, default=str)}")

    images = _fetch_post_images(db, post_id)
    video = _fetch_post_video(db, post_id)

    # Debug logging for video data (only warn if this is actually a video post)
    if video:
        log_info(f"Fetched video data: {json.dumps(video, indent=2, default=str)}")
    elif post.get('post_type') == 'video':
        log_warning(f"No video found for video post {post_id}")

    return render_template(
        "approval/view.html",
        post=post,
        images=images,
        video=video,
    )


@approval_bp.route("/approve/<string:post_id>", methods=["POST"])
def approve_post(post_id: str):
    """Approve a post, transitioning it to the scheduled state and posting immediately if scheduled time is in the past."""

    db = _ensure_database()
    if not db:
        return jsonify({"error": "Supabase connection is not configured."}), 503

    post = _fetch_post(db, post_id)
    if not post:
        return jsonify({"error": "Post not found."}), 404

    if post.get("status") != "pending_approval":
        log_info(f"Post {post_id} approval skipped; current status: {post.get('status')}")
        return redirect(url_for("approval.view_post", post_id=post_id))

    metadata = post.get("metadata") or {}
    history = metadata.setdefault("approval_history", [])
    history.append(
        {
            "action": "approved",
            "timestamp": _current_iso_timestamp(db),
            "actor": _resolve_actor(),
        }
    )

    update_fields = {
        "status": "scheduled",
        "metadata": metadata,
        "updated_at": _current_iso_timestamp(db),
    }

    if not _update_post_fields(db, post_id, update_fields):
        return (
            render_template(
                "approval/error.html",
                message="Failed to approve post. Please try again.",
            ),
            500,
        )

    log_info(f"Post {post_id} approved for scheduling")

    # Check if it's a video post - upload as draft immediately
    # Refresh post data to get the updated status
    post = _fetch_post(db, post_id)
    post_type = post.get('post_type')
    video_url = post.get('video_url')

    if post_type == 'video' or video_url:
        log_info(f"Video post detected - uploading draft to Facebook immediately")

        # Upload video as draft immediately
        upload_result = _upload_video_draft_immediately(db, post)

        if upload_result.get('success'):
            facebook_post_id = upload_result.get('post_id')

            # Update post status to awaiting_music
            update_fields = {
                'status': 'awaiting_music',
                'facebook_post_id': facebook_post_id,
                'updated_at': _current_iso_timestamp(db)
            }
            _update_post_fields(db, post_id, update_fields)

            log_info(f"Video uploaded as draft to Facebook: {facebook_post_id}")

            # Send WhatsApp notification
            _send_video_ready_notification(db, post, facebook_post_id)

            return jsonify({
                'success': True,
                'message': 'Video approved and uploaded as draft to Facebook. Check WhatsApp for instructions to add music.',
                'post_id': post_id,
                'facebook_post_id': facebook_post_id,
                'status': 'awaiting_music'
            })
        else:
            log_error(f"Failed to upload video draft: {upload_result.get('error')}")
            # Keep as scheduled - scheduler will retry later
            return jsonify({
                'success': True,
                'message': 'Post approved but video upload failed. Scheduler will retry.',
                'post_id': post_id,
                'status': 'scheduled',
                'upload_error': upload_result.get('error')
            })

    # Check if we should post immediately (non-video posts)
    if _should_post_immediately(post):
        log_info(f"Post {post_id} scheduled for immediate posting")
        result = _post_to_facebook(db, post)

        if result['success']:
            log_info(f"Post {post_id} successfully posted to Facebook with ID: {result['facebook_post_id']}")
        else:
            log_warning(f"Failed to post {post_id} to Facebook: {result['error']}")

    return redirect(url_for("approval.view_post", post_id=post_id))


@approval_bp.route("/reject/<string:post_id>", methods=["POST"])
def reject_post(post_id: str):
    """
    Reject and DELETE a post permanently.

    This action will:
    - Delete the post from the database
    - Delete associated video(s)
    - Delete associated images
    - Remove the post from the pending approval list

    Optionally logs a rejection reason before deletion.
    """

    db = _ensure_database()
    if not db:
        return jsonify({"error": "Supabase connection is not configured."}), 503

    post = _fetch_post(db, post_id)
    if not post:
        return jsonify({"error": "Post not found."}), 404

    # Get rejection reason from form or JSON payload
    payload = request.get_json(silent=True) or {}
    reason = request.form.get("reason") or payload.get("reason", "")

    # Log the rejection (optional - you can remove this if you don't need logs)
    log_info(f"Post {post_id} rejected with reason: '{reason}'. Deleting from database...")

    # Optional: If you want to keep a record of rejections, insert into a separate audit table first
    # This is optional - uncomment if you want to track rejections
    """
    try:
        rejection_record = {
            'post_id': post_id,
            'content': post.get('content') or post.get('content_text', ''),
            'rejection_reason': reason or 'No reason provided',
            'rejected_at': _current_iso_timestamp(db),
            'rejected_by': _resolve_actor(),
            'post_data': post  # Store full post data for reference
        }
        db.db.table('rejection_audit_log').insert(rejection_record).execute()
        log_info(f"Rejection logged to audit table for post {post_id}")
    except Exception as audit_exc:
        log_warning(f"Failed to log rejection to audit table: {audit_exc}")
    """

    # Delete the post and all associated data
    if not _delete_post_cascade(db, post_id):
        return (
            render_template(
                "approval/error.html",
                message="Failed to delete rejected post. Please try again.",
            ),
            500,
        )

    log_info(f"Post {post_id} successfully deleted after rejection")

    # Redirect to pending list (post will no longer appear)
    return redirect(url_for("approval.pending_posts"))


@approval_bp.route("/edit/<string:post_id>", methods=["POST"])
def edit_post(post_id: str):
    """Apply content edits prior to approval."""

    db = _ensure_database()
    if not db:
        return jsonify({"error": "Supabase connection is not configured."}), 503

    post = _fetch_post(db, post_id)
    if not post:
        return jsonify({"error": "Post not found."}), 404

    form_data = request.form or {}
    payload = request.get_json(silent=True) or {}

    content = form_data.get("content") or payload.get("content")
    scheduled_time = form_data.get("scheduled_time") or payload.get("scheduled_time")
    metadata_raw = form_data.get("metadata") or payload.get("metadata")

    update_fields: Dict[str, Any] = {}

    if content is not None:
        update_fields["content"] = content

    if scheduled_time is not None:
        update_fields["scheduled_time"] = scheduled_time or None

    if metadata_raw is not None:
        if isinstance(metadata_raw, (dict, list)):
            metadata_value = metadata_raw
        else:
            try:
                metadata_value = json.loads(metadata_raw) if metadata_raw else {}
            except json.JSONDecodeError:
                return (
                    render_template(
                        "approval/error.html",
                        message="Invalid metadata JSON supplied.",
                    ),
                    400,
                )

        update_fields["metadata"] = metadata_value

    if not update_fields:
        log_info(f"Edit request for post {post_id} contained no changes")
        return redirect(url_for("approval.view_post", post_id=post_id))

    update_fields["updated_at"] = _current_iso_timestamp(db)

    if not _update_post_fields(db, post_id, update_fields):
        return (
            render_template(
                "approval/error.html",
                message="Failed to update post content.",
            ),
            500,
        )

    log_info(f"Post {post_id} edited prior to approval")
    return redirect(url_for("approval.view_post", post_id=post_id))


@approval_bp.route("/post-now/<string:post_id>", methods=["POST"])
def post_now(post_id: str):
    """Immediately post an approved item to Facebook.

    This endpoint can be used to manually trigger posting for approved content,
    regardless of the scheduled time.
    """

    db = _ensure_database()
    if not db:
        return jsonify({"error": "Supabase connection is not configured."}), 503

    post = _fetch_post(db, post_id)
    if not post:
        return jsonify({"error": "Post not found."}), 404

    # Check if post is in a valid state for posting
    valid_statuses = ["scheduled", "pending_approval", "failed"]
    if post.get("status") not in valid_statuses:
        log_warning(f"Post {post_id} cannot be posted; current status: {post.get('status')}")
        return jsonify({
            "error": f"Post cannot be posted in current status: {post.get('status')}. Must be one of: {', '.join(valid_statuses)}"
        }), 400

    # If not approved yet, approve it first
    if post.get("status") == "pending_approval":
        metadata = post.get("metadata") or {}
        history = metadata.setdefault("approval_history", [])
        history.append(
            {
                "action": "approved_and_posted",
                "timestamp": _current_iso_timestamp(db),
                "actor": _resolve_actor(),
            }
        )

        update_fields = {
            "status": "scheduled",
            "metadata": metadata,
            "updated_at": _current_iso_timestamp(db),
        }

        if not _update_post_fields(db, post_id, update_fields):
            return jsonify({"error": "Failed to approve post before posting."}), 500

        # Refresh post data
        post = _fetch_post(db, post_id)

    # Post to Facebook
    log_info(f"Manual posting triggered for post {post_id}")
    result = _post_to_facebook(db, post)

    if result['success']:
        log_info(f"Post {post_id} successfully posted to Facebook with ID: {result['facebook_post_id']}")
        return jsonify({
            "success": True,
            "message": "Post successfully published to Facebook",
            "facebook_post_id": result['facebook_post_id'],
            "post_id": post_id
        }), 200
    else:
        log_error(f"Failed to post {post_id} to Facebook: {result['error']}")
        return jsonify({
            "success": False,
            "error": result['error'],
            "post_id": post_id
        }), 500

