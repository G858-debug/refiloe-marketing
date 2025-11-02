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
from utils.supabase_rest import SupabaseRestClient
from utils.logger import log_error, log_info


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
        result = (
            db.db.table("social_posts")
            .select("*")
            .eq("id", post_id)
            .single()
            .execute()
        )
        return result.data if result.data else None
    except Exception as exc:
        log_error(f"Error fetching post {post_id}: {exc}")
        return None


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
            .execute()
        )
        if result.data:
            return result.data[0]
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
        result = (
            db.db.table("social_posts")
            .select("*")
            .eq("status", "pending_approval")
            .order("created_at", desc=True)
            .execute()
        )
        posts = result.data or []
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

    images = _fetch_post_images(db, post_id)
    video = _fetch_post_video(db, post_id)

    return render_template(
        "approval/view.html",
        post=post,
        images=images,
        video=video,
    )


@approval_bp.route("/approve/<string:post_id>", methods=["POST"])
def approve_post(post_id: str):
    """Approve a post, transitioning it to the scheduled state."""

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
    return redirect(url_for("approval.view_post", post_id=post_id))


@approval_bp.route("/reject/<string:post_id>", methods=["POST"])
def reject_post(post_id: str):
    """Reject a post and optionally record a rejection reason."""

    db = _ensure_database()
    if not db:
        return jsonify({"error": "Supabase connection is not configured."}), 503

    post = _fetch_post(db, post_id)
    if not post:
        return jsonify({"error": "Post not found."}), 404

    payload = request.get_json(silent=True) or {}
    reason = request.form.get("reason") or payload.get("reason", "")

    metadata = post.get("metadata") or {}
    history = metadata.setdefault("approval_history", [])
    history.append(
        {
            "action": "rejected",
            "timestamp": _current_iso_timestamp(db),
            "reason": reason or None,
            "actor": _resolve_actor(),
        }
    )

    if reason:
        metadata["rejection_reason"] = reason
        metadata["rejected_at"] = _current_iso_timestamp(db)
    elif metadata.get("rejection_reason"):
        metadata.pop("rejection_reason", None)
        metadata.pop("rejected_at", None)

    update_fields = {
        "status": "rejected",
        "metadata": metadata,
        "updated_at": _current_iso_timestamp(db),
    }

    if not _update_post_fields(db, post_id, update_fields):
        return (
            render_template(
                "approval/error.html",
                message="Failed to reject post. Please try again.",
            ),
            500,
        )

    log_info(f"Post {post_id} rejected with reason: {reason}")
    return redirect(url_for("approval.view_post", post_id=post_id))


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

