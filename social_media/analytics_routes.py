"""Flask blueprint providing analytics and reporting routes for social media content."""

from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytz
from flask import (
    Blueprint,
    Response,
    jsonify,
    make_response,
    render_template,
    request,
)
from social_media.database import SocialMediaDatabase
from utils.logger import log_error, log_info
from utils.supabase_rest import SupabaseRestClient

analytics_bp = Blueprint(
    "analytics",
    __name__,
    url_prefix="/analytics",
    template_folder="templates",
)

# South African timezone
SA_TZ = pytz.timezone('Africa/Johannesburg')

_supabase_client = None
_database_service: Optional[SocialMediaDatabase] = None


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
        log_error("Supabase credentials are missing for analytics routes")
        return None

    try:
        _supabase_client = SupabaseRestClient(url, key)
        _database_service = SocialMediaDatabase(_supabase_client)
        log_info("Analytics routes connected to Supabase")
    except Exception as exc:
        log_error(f"Failed to initialize Supabase for analytics routes: {exc}")
        _supabase_client = None
        _database_service = None

    return _database_service


def _get_week_start_end(date: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """Get the start and end of the current week in SA timezone."""
    if date is None:
        date = datetime.now(SA_TZ)

    # Get start of week (Monday)
    start_of_week = date - timedelta(days=date.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get end of week (Sunday)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)

    return start_of_week, end_of_week


def _calculate_video_success_rate(db: SocialMediaDatabase) -> Dict[str, Any]:
    """Calculate video generation success rate."""
    try:
        # Get all video posts from the last 30 days
        thirty_days_ago = (datetime.now(SA_TZ) - timedelta(days=30)).isoformat()

        # Get total video posts
        result = (
            db.db.table('social_posts')
            .select('*', count='exact')
            .eq('post_type', 'video')
            .gte('created_at', thirty_days_ago)
            .execute()
        )

        total_videos = len(result.data) if result.data else 0

        # Get successful video posts (those with video_url)
        result_success = (
            db.db.table('social_posts')
            .select('*', count='exact')
            .eq('post_type', 'video')
            .gte('created_at', thirty_days_ago)
            .not_.is_('video_url', 'null')
            .execute()
        )

        successful_videos = len(result_success.data) if result_success.data else 0

        success_rate = (successful_videos / total_videos * 100) if total_videos > 0 else 0

        return {
            'total': total_videos,
            'successful': successful_videos,
            'failed': total_videos - successful_videos,
            'success_rate': round(success_rate, 2)
        }
    except Exception as e:
        log_error(f"Error calculating video success rate: {str(e)}")
        return {'total': 0, 'successful': 0, 'failed': 0, 'success_rate': 0}


def _get_top_themes(db: SocialMediaDatabase, limit: int = 5) -> List[Dict[str, Any]]:
    """Get top performing content themes based on engagement."""
    try:
        # Get posts from last 30 days with engagement metrics
        thirty_days_ago = (datetime.now(SA_TZ) - timedelta(days=30)).isoformat()

        result = (
            db.db.table('social_posts')
            .select('content_theme, status')
            .gte('created_at', thirty_days_ago)
            .execute()
        )

        if not result.data:
            return []

        # Count by theme and calculate metrics
        theme_stats = {}
        for post in result.data:
            theme = post.get('content_theme', 'uncategorized')
            if not theme:
                theme = 'uncategorized'

            if theme not in theme_stats:
                theme_stats[theme] = {
                    'theme': theme,
                    'total_posts': 0,
                    'published': 0,
                    'pending': 0,
                    'rejected': 0
                }

            theme_stats[theme]['total_posts'] += 1
            status = post.get('status', '')
            if status == 'published':
                theme_stats[theme]['published'] += 1
            elif status == 'pending_approval':
                theme_stats[theme]['pending'] += 1
            elif status == 'rejected':
                theme_stats[theme]['rejected'] += 1

        # Sort by total posts
        sorted_themes = sorted(
            theme_stats.values(),
            key=lambda x: x['total_posts'],
            reverse=True
        )

        return sorted_themes[:limit]
    except Exception as e:
        log_error(f"Error getting top themes: {str(e)}")
        return []


@analytics_bp.route('/dashboard')
def dashboard():
    """Display analytics dashboard with key metrics."""
    db = _ensure_database()
    if not db:
        return render_template(
            'analytics/error.html',
            message='Database connection is not available.'
        ), 503

    try:
        # Get current week range
        week_start, week_end = _get_week_start_end()

        # Get posts created this week
        result_created = (
            db.db.table('social_posts')
            .select('*', count='exact')
            .gte('created_at', week_start.isoformat())
            .lte('created_at', week_end.isoformat())
            .execute()
        )
        posts_created = len(result_created.data) if result_created.data else 0

        # Get posts published this week
        result_published = (
            db.db.table('social_posts')
            .select('*', count='exact')
            .eq('status', 'published')
            .gte('published_time', week_start.isoformat())
            .lte('published_time', week_end.isoformat())
            .execute()
        )
        posts_published = len(result_published.data) if result_published.data else 0

        # Get approval/rejection ratio (all time)
        result_approved = (
            db.db.table('social_posts')
            .select('*', count='exact')
            .in_('status', ['scheduled', 'published'])
            .execute()
        )
        total_approved = len(result_approved.data) if result_approved.data else 0

        result_rejected = (
            db.db.table('social_posts')
            .select('*', count='exact')
            .eq('status', 'rejected')
            .execute()
        )
        total_rejected = len(result_rejected.data) if result_rejected.data else 0

        # Calculate approval ratio
        total_reviewed = total_approved + total_rejected
        approval_rate = (total_approved / total_reviewed * 100) if total_reviewed > 0 else 0

        # Get video success rate
        video_stats = _calculate_video_success_rate(db)

        # Get top performing themes
        top_themes = _get_top_themes(db)

        # Get status breakdown
        result_all = db.db.table('social_posts').select('status').execute()
        status_counts = {}
        if result_all.data:
            for post in result_all.data:
                status = post.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1

        dashboard_data = {
            'week_start': week_start.strftime('%Y-%m-%d'),
            'week_end': week_end.strftime('%Y-%m-%d'),
            'posts_created_this_week': posts_created,
            'posts_published_this_week': posts_published,
            'video_success_rate': video_stats['success_rate'],
            'video_stats': video_stats,
            'approval_rate': round(approval_rate, 2),
            'total_approved': total_approved,
            'total_rejected': total_rejected,
            'top_themes': top_themes,
            'status_counts': status_counts,
            'last_updated': datetime.now(SA_TZ).strftime('%Y-%m-%d %H:%M:%S')
        }

        return render_template('analytics/dashboard.html', data=dashboard_data)

    except Exception as e:
        log_error(f"Error loading analytics dashboard: {str(e)}")
        return render_template(
            'analytics/error.html',
            message=f'Error loading dashboard: {str(e)}'
        ), 500


@analytics_bp.route('/posts')
def posts_list():
    """Display list of all posts with filtering and export options."""
    db = _ensure_database()
    if not db:
        return render_template(
            'analytics/error.html',
            message='Database connection is not available.'
        ), 503

    try:
        # Get filter parameters
        status_filter = request.args.get('status', '')
        platform_filter = request.args.get('platform', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        theme_filter = request.args.get('theme', '')

        # Build query
        query = db.db.table('social_posts').select('*')

        if status_filter:
            query = query.eq('status', status_filter)

        if platform_filter:
            query = query.eq('platform', platform_filter)

        if theme_filter:
            query = query.eq('content_theme', theme_filter)

        if date_from:
            query = query.gte('created_at', date_from)

        if date_to:
            # Add 1 day to include the entire end date
            end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.lte('created_at', end_date.isoformat())

        # Execute query with ordering
        result = query.order('created_at', desc=True).execute()
        posts = result.data if result.data else []

        # Get unique values for filters
        all_posts = db.db.table('social_posts').select('status, platform, content_theme').execute()

        statuses = set()
        platforms = set()
        themes = set()

        if all_posts.data:
            for post in all_posts.data:
                if post.get('status'):
                    statuses.add(post['status'])
                if post.get('platform'):
                    platforms.add(post['platform'])
                if post.get('content_theme'):
                    themes.add(post['content_theme'])

        filter_options = {
            'statuses': sorted(list(statuses)),
            'platforms': sorted(list(platforms)),
            'themes': sorted(list(themes))
        }

        # Current filters for display
        current_filters = {
            'status': status_filter,
            'platform': platform_filter,
            'theme': theme_filter,
            'date_from': date_from,
            'date_to': date_to
        }

        return render_template(
            'analytics/posts.html',
            posts=posts,
            filter_options=filter_options,
            current_filters=current_filters,
            total_posts=len(posts)
        )

    except Exception as e:
        log_error(f"Error loading posts list: {str(e)}")
        return render_template(
            'analytics/error.html',
            message=f'Error loading posts: {str(e)}'
        ), 500


@analytics_bp.route('/posts/export')
def export_posts_csv():
    """Export posts to CSV format."""
    db = _ensure_database()
    if not db:
        return jsonify({'error': 'Database connection is not available.'}), 503

    try:
        # Get filter parameters (same as posts_list)
        status_filter = request.args.get('status', '')
        platform_filter = request.args.get('platform', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        theme_filter = request.args.get('theme', '')

        # Build query
        query = db.db.table('social_posts').select('*')

        if status_filter:
            query = query.eq('status', status_filter)

        if platform_filter:
            query = query.eq('platform', platform_filter)

        if theme_filter:
            query = query.eq('content_theme', theme_filter)

        if date_from:
            query = query.gte('created_at', date_from)

        if date_to:
            end_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.lte('created_at', end_date.isoformat())

        # Execute query
        result = query.order('created_at', desc=True).execute()
        posts = result.data if result.data else []

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'ID',
            'Post Type',
            'Platform',
            'Status',
            'Content Theme',
            'Content Text',
            'Created At',
            'Scheduled Time',
            'Published Time',
            'Video URL',
            'Video Duration',
            'Completion Rate',
            'Avg Watch Time'
        ])

        # Write data
        for post in posts:
            writer.writerow([
                post.get('id', ''),
                post.get('post_type', ''),
                post.get('platform', ''),
                post.get('status', ''),
                post.get('content_theme', ''),
                post.get('content_text', '')[:100] + '...' if post.get('content_text') else '',
                post.get('created_at', ''),
                post.get('scheduled_time', ''),
                post.get('published_time', ''),
                post.get('video_url', ''),
                post.get('video_duration', 0),
                post.get('completion_rate', 0),
                post.get('avg_watch_time', 0)
            ])

        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=posts_export_{datetime.now(SA_TZ).strftime("%Y%m%d_%H%M%S")}.csv'

        return response

    except Exception as e:
        log_error(f"Error exporting posts to CSV: {str(e)}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/performance')
def performance_metrics():
    """Display performance metrics and engagement analytics."""
    db = _ensure_database()
    if not db:
        return render_template(
            'analytics/error.html',
            message='Database connection is not available.'
        ), 503

    try:
        # Get video performance metrics
        result_videos = (
            db.db.table('social_posts')
            .select('*')
            .eq('post_type', 'video')
            .not_.is_('video_url', 'null')
            .order('created_at', desc=True)
            .limit(50)
            .execute()
        )

        videos = result_videos.data if result_videos.data else []

        # Calculate video metrics
        total_videos = len(videos)
        avg_completion_rate = 0
        avg_watch_time = 0

        if videos:
            total_completion = sum(v.get('completion_rate', 0) for v in videos)
            total_watch_time = sum(v.get('avg_watch_time', 0) for v in videos)

            avg_completion_rate = total_completion / total_videos
            avg_watch_time = total_watch_time / total_videos

        # Analyze best posting times (based on published posts)
        result_published = (
            db.db.table('social_posts')
            .select('published_time, status')
            .eq('status', 'published')
            .not_.is_('published_time', 'null')
            .execute()
        )

        posting_times = {}
        if result_published.data:
            for post in result_published.data:
                pub_time = post.get('published_time')
                if pub_time:
                    try:
                        dt = datetime.fromisoformat(pub_time.replace('Z', '+00:00'))
                        hour = dt.hour
                        posting_times[hour] = posting_times.get(hour, 0) + 1
                    except Exception:
                        continue

        # Find top 5 posting hours
        best_posting_times = sorted(
            posting_times.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Format posting times
        best_times_formatted = [
            {
                'hour': f"{hour:02d}:00",
                'count': count
            }
            for hour, count in best_posting_times
        ]

        # Get engagement metrics placeholder (for when Facebook posting is live)
        engagement_notice = "Engagement metrics will be available once Facebook posting is live and data is collected."

        # Get post type breakdown
        result_all = db.db.table('social_posts').select('post_type').execute()
        post_type_counts = {}
        if result_all.data:
            for post in result_all.data:
                ptype = post.get('post_type', 'unknown')
                post_type_counts[ptype] = post_type_counts.get(ptype, 0) + 1

        performance_data = {
            'total_videos': total_videos,
            'avg_completion_rate': round(avg_completion_rate, 2),
            'avg_watch_time': round(avg_watch_time, 2),
            'best_posting_times': best_times_formatted,
            'engagement_notice': engagement_notice,
            'post_type_breakdown': post_type_counts,
            'recent_videos': videos[:10],  # Show 10 most recent
            'last_updated': datetime.now(SA_TZ).strftime('%Y-%m-%d %H:%M:%S')
        }

        return render_template('analytics/performance.html', data=performance_data)

    except Exception as e:
        log_error(f"Error loading performance metrics: {str(e)}")
        return render_template(
            'analytics/error.html',
            message=f'Error loading performance metrics: {str(e)}'
        ), 500


@analytics_bp.route('/api/dashboard-data')
def api_dashboard_data():
    """API endpoint for dashboard data (for AJAX updates or external tools)."""
    db = _ensure_database()
    if not db:
        return jsonify({'error': 'Database connection is not available.'}), 503

    try:
        week_start, week_end = _get_week_start_end()

        # Get basic metrics
        result_created = (
            db.db.table('social_posts')
            .select('*', count='exact')
            .gte('created_at', week_start.isoformat())
            .lte('created_at', week_end.isoformat())
            .execute()
        )

        video_stats = _calculate_video_success_rate(db)
        top_themes = _get_top_themes(db)

        return jsonify({
            'success': True,
            'posts_created_this_week': len(result_created.data) if result_created.data else 0,
            'video_stats': video_stats,
            'top_themes': top_themes,
            'timestamp': datetime.now(SA_TZ).isoformat()
        })

    except Exception as e:
        log_error(f"Error getting dashboard API data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
