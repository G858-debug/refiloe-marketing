"""Avatar IV Credit Tracking Module
=====================================

Tracks Avatar IV video generation credits to manage monthly quota and determine
when videos need to be created manually instead of via API.

HeyGen Avatar IV Subscription:
- Plan: 60 credits/month
- Each credit = 1 minute of video generation
- Resets on the 1st of each month

This module provides functions to:
- Check if Avatar IV credits are available for generation
- Track credit usage
- Determine when to flag posts for manual video creation
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Tuple

import pytz

from utils.logger import log_error, log_info, log_warning


SA_TIMEZONE = pytz.timezone("Africa/Johannesburg")

# Avatar IV monthly credit limit (in minutes)
AVATAR_IV_MONTHLY_CREDITS = 60


def get_current_month_start() -> datetime:
    """Get the start of the current billing cycle (1st of current month).

    Returns:
        datetime: Start of current month in UTC timezone
    """
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)


def get_avatar_iv_usage_this_month(supabase_client) -> float:
    """Calculate total Avatar IV credits used this billing cycle.

    Queries the social_posts table for videos generated via Avatar IV API
    during the current billing cycle (since 1st of current month).

    Args:
        supabase_client: Supabase client for database queries

    Returns:
        float: Total minutes of Avatar IV video generated this month
    """
    if not supabase_client:
        log_error("Supabase client not available for Avatar IV usage tracking")
        return 0.0

    try:
        month_start = get_current_month_start()

        # Query posts with:
        # - post_type = 'video'
        # - video_source = 'avatar_iv_api' (API-generated, not manual)
        # - created_at >= month_start
        response = (
            supabase_client.table("social_posts")
            .select("duration_seconds, video_source, created_at")
            .eq("post_type", "video")
            .eq("video_source", "avatar_iv_api")
            .gte("created_at", month_start.isoformat())
            .execute()
        )

        posts = response.data if response.data else []

        # Calculate total duration in minutes
        total_seconds = sum(
            float(post.get("duration_seconds", 0))
            for post in posts
            if post.get("duration_seconds")
        )

        total_minutes = total_seconds / 60.0

        log_info(
            f"Avatar IV usage this month: {total_minutes:.2f} minutes "
            f"({len(posts)} videos generated since {month_start.strftime('%Y-%m-%d')})"
        )

        return total_minutes

    except Exception as exc:
        log_error(f"Failed to calculate Avatar IV usage: {exc}")
        # Return 0 on error (fail open - allow generation to proceed)
        return 0.0


def get_remaining_avatar_iv_credits(supabase_client) -> float:
    """Get remaining Avatar IV credits for this billing cycle.

    Args:
        supabase_client: Supabase client for database queries

    Returns:
        float: Remaining credits in minutes
    """
    used = get_avatar_iv_usage_this_month(supabase_client)
    remaining = max(0.0, AVATAR_IV_MONTHLY_CREDITS - used)

    log_info(
        f"Avatar IV credits: {remaining:.2f} minutes remaining "
        f"({used:.2f}/{AVATAR_IV_MONTHLY_CREDITS} used)"
    )

    return remaining


def can_generate_avatar_iv(
    estimated_duration: int,
    supabase_client
) -> Tuple[bool, Dict[str, float]]:
    """Check if Avatar IV credits are available for video generation.

    Args:
        estimated_duration: Estimated video duration in seconds
        supabase_client: Supabase client for database queries

    Returns:
        Tuple containing:
        - bool: True if credits available, False if exhausted
        - dict: Credit status info (used, remaining, required, available)
    """
    if not supabase_client:
        log_warning("Supabase client unavailable; allowing Avatar IV generation (fail open)")
        return True, {
            "used": 0.0,
            "remaining": AVATAR_IV_MONTHLY_CREDITS,
            "required": estimated_duration / 60.0,
            "available": True,
            "warning": "Database unavailable - usage tracking disabled"
        }

    try:
        # Get current usage
        used = get_avatar_iv_usage_this_month(supabase_client)
        remaining = max(0.0, AVATAR_IV_MONTHLY_CREDITS - used)

        # Convert estimated duration to minutes
        required_minutes = estimated_duration / 60.0

        # Check if enough credits remain
        available = remaining >= required_minutes

        status = {
            "used": used,
            "remaining": remaining,
            "required": required_minutes,
            "available": available,
            "total_credits": AVATAR_IV_MONTHLY_CREDITS,
            "month_start": get_current_month_start().isoformat()
        }

        if available:
            log_info(
                f"Avatar IV credits available: {required_minutes:.2f} min required, "
                f"{remaining:.2f} min remaining"
            )
        else:
            log_warning(
                f"Avatar IV credits exhausted: {required_minutes:.2f} min required, "
                f"only {remaining:.2f} min remaining. Flagging for manual creation."
            )

        return available, status

    except Exception as exc:
        log_error(f"Error checking Avatar IV credits: {exc}")
        # Fail open - allow generation on error
        return True, {
            "used": 0.0,
            "remaining": AVATAR_IV_MONTHLY_CREDITS,
            "required": estimated_duration / 60.0,
            "available": True,
            "error": str(exc)
        }


def get_avatar_iv_credit_status(supabase_client) -> Dict[str, float]:
    """Get current Avatar IV credit status for logging/reporting.

    Args:
        supabase_client: Supabase client for database queries

    Returns:
        dict: Credit status with used, remaining, total, and percentage
    """
    used = get_avatar_iv_usage_this_month(supabase_client)
    remaining = max(0.0, AVATAR_IV_MONTHLY_CREDITS - used)
    percentage_used = (used / AVATAR_IV_MONTHLY_CREDITS) * 100 if AVATAR_IV_MONTHLY_CREDITS > 0 else 0.0

    return {
        "used_minutes": used,
        "remaining_minutes": remaining,
        "total_credits": AVATAR_IV_MONTHLY_CREDITS,
        "percentage_used": percentage_used,
        "month_start": get_current_month_start().isoformat()
    }


__all__ = [
    "can_generate_avatar_iv",
    "get_avatar_iv_credit_status",
    "get_avatar_iv_usage_this_month",
    "get_remaining_avatar_iv_credits",
    "AVATAR_IV_MONTHLY_CREDITS"
]
