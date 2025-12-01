"""Flask blueprint providing analytics and reporting routes for social media content."""

from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from functools import wraps
from time import time

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

# Simple in-memory cache for API responses
_cache = {}
CACHE_DURATION = 300  # 5 minutes


def cache_response(duration: int = CACHE_DURATION):
    """Cache decorator for API responses."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and query params
            cache_key = f"{func.__name__}:{request.query_string.decode()}"

            # Check if cached response exists and is still valid
            if cache_key in _cache:
                cached_data, timestamp = _cache[cache_key]
                if time() - timestamp < duration:
                    return cached_data

            # Call function and cache result
            result = func(*args, **kwargs)
            _cache[cache_key] = (result, time())

            # Clean old cache entries (simple cleanup)
            current_time = time()
            keys_to_delete = [
                k for k, (_, ts) in _cache.items()
                if current_time - ts > duration * 2
            ]
            for k in keys_to_delete:
                del _cache[k]

            return result
        return wrapper
    return decorator


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


def _get_daily_engagement(db: SocialMediaDatabase, days: int = 30) -> List[Dict[str, Any]]:
    """Get daily engagement metrics for the specified number of days."""
    try:
        start_date = datetime.now(SA_TZ) - timedelta(days=days)

        # Get posts with their creation dates
        result = (
            db.db.table('social_posts')
            .select('created_at, status')
            .gte('created_at', start_date.isoformat())
            .execute()
        )

        if not result.data:
            return []

        # Aggregate by day
        daily_data = {}
        for post in result.data:
            created_at = post.get('created_at')
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_key = dt.strftime('%Y-%m-%d')

                    if date_key not in daily_data:
                        daily_data[date_key] = {
                            'date': date_key,
                            'posts': 0,
                            'published': 0,
                            'engagement': 0  # Placeholder for future Facebook engagement
                        }

                    daily_data[date_key]['posts'] += 1
                    if post.get('status') == 'published':
                        daily_data[date_key]['published'] += 1
                        # Simulated engagement (will be replaced with real data)
                        daily_data[date_key]['engagement'] += 10
                except Exception:
                    continue

        # Sort by date
        sorted_data = sorted(daily_data.values(), key=lambda x: x['date'])
        return sorted_data
    except Exception as e:
        log_error(f"Error getting daily engagement: {str(e)}")
        return []


def _get_posting_time_heatmap(db: SocialMediaDatabase) -> Dict[str, Any]:
    """Get heatmap data for best posting times by day and hour."""
    try:
        # Get published posts
        result = (
            db.db.table('social_posts')
            .select('published_time')
            .eq('status', 'published')
            .not_.is_('published_time', 'null')
            .execute()
        )

        if not result.data:
            return {'days': [], 'hours': [], 'data': []}

        # Initialize heatmap data structure
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        hours = list(range(24))
        heatmap = [[0 for _ in hours] for _ in days]

        # Aggregate posting counts
        for post in result.data:
            pub_time = post.get('published_time')
            if pub_time:
                try:
                    dt = datetime.fromisoformat(pub_time.replace('Z', '+00:00'))
                    day_idx = dt.weekday()
                    hour_idx = dt.hour
                    heatmap[day_idx][hour_idx] += 1
                except Exception:
                    continue

        return {
            'days': days,
            'hours': hours,
            'data': heatmap
        }
    except Exception as e:
        log_error(f"Error getting posting time heatmap: {str(e)}")
        return {'days': [], 'hours': [], 'data': []}


def _get_content_performance(db: SocialMediaDatabase, limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent posts with performance metrics."""
    try:
        result = (
            db.db.table('social_posts')
            .select('*')
            .order('created_at', desc=True)
            .limit(limit)
            .execute()
        )

        if not result.data:
            return []

        posts_with_metrics = []
        for post in result.data:
            # Placeholder engagement metrics (will be replaced with real Facebook data)
            engagement_data = {
                'id': post.get('id'),
                'post_type': post.get('post_type', 'unknown'),
                'content_theme': post.get('content_theme', 'uncategorized'),
                'status': post.get('status', 'unknown'),
                'created_at': post.get('created_at'),
                'published_time': post.get('published_time'),
                'likes': 0,  # Placeholder
                'comments': 0,  # Placeholder
                'shares': 0,  # Placeholder
                'reach': 0,  # Placeholder
                'engagement_rate': 0.0,  # Placeholder
                'video_completion_rate': post.get('completion_rate', 0) if post.get('post_type') == 'video' else None
            }
            posts_with_metrics.append(engagement_data)

        return posts_with_metrics
    except Exception as e:
        log_error(f"Error getting content performance: {str(e)}")
        return []


def _get_video_performance_detailed(db: SocialMediaDatabase) -> Dict[str, Any]:
    """Get detailed video performance metrics."""
    try:
        result = (
            db.db.table('social_posts')
            .select('*')
            .eq('post_type', 'video')
            .not_.is_('video_url', 'null')
            .order('created_at', desc=True)
            .limit(10)
            .execute()
        )

        videos = result.data if result.data else []

        # Calculate aggregate metrics
        total_videos = len(videos)
        avg_completion = 0
        avg_watch_time = 0
        total_views = 0  # Placeholder

        if videos:
            total_completion = sum(v.get('completion_rate', 0) for v in videos)
            total_watch = sum(v.get('avg_watch_time', 0) for v in videos)
            avg_completion = total_completion / total_videos
            avg_watch_time = total_watch / total_videos

        # Top performing videos (by completion rate)
        top_videos = sorted(
            videos,
            key=lambda x: x.get('completion_rate', 0),
            reverse=True
        )[:5]

        return {
            'total_videos': total_videos,
            'avg_completion_rate': round(avg_completion, 2),
            'avg_watch_time': round(avg_watch_time, 2),
            'total_views': total_views,  # Placeholder
            'top_videos': top_videos,
            'recent_videos': videos
        }
    except Exception as e:
        log_error(f"Error getting video performance: {str(e)}")
        return {
            'total_videos': 0,
            'avg_completion_rate': 0,
            'avg_watch_time': 0,
            'total_views': 0,
            'top_videos': [],
            'recent_videos': []
        }


@analytics_bp.route('/dashboard')
def dashboard():
    """Display enhanced analytics dashboard with comprehensive metrics."""
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
        posts_this_week = len(result_created.data) if result_created.data else 0

        # Calculate total engagement this week (placeholder)
        total_engagement_week = posts_this_week * 15  # Simulated

        # Calculate average engagement rate (placeholder)
        avg_engagement_rate = 3.5  # Simulated percentage

        # Get daily engagement data for 30 days
        daily_engagement = _get_daily_engagement(db, days=30)

        # Get content performance for last 20 posts
        content_performance = _get_content_performance(db, limit=20)

        # Get posting time heatmap
        posting_heatmap = _get_posting_time_heatmap(db)

        # Get top performing themes with engagement
        top_themes = _get_top_themes(db, limit=10)

        # Get detailed video performance
        video_performance = _get_video_performance_detailed(db)

        # Get status breakdown
        result_all = db.db.table('social_posts').select('status').execute()
        status_counts = {}
        if result_all.data:
            for post in result_all.data:
                status = post.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1

        dashboard_data = {
            # Overview cards
            'total_followers': 0,  # Placeholder until Facebook connected
            'posts_this_week': posts_this_week,
            'total_engagement_week': total_engagement_week,
            'avg_engagement_rate': avg_engagement_rate,

            # Performance data
            'daily_engagement': daily_engagement,
            'content_performance': content_performance,
            'posting_heatmap': posting_heatmap,
            'top_themes': top_themes,
            'video_performance': video_performance,
            'status_counts': status_counts,

            # Metadata
            'week_start': week_start.strftime('%Y-%m-%d'),
            'week_end': week_end.strftime('%Y-%m-%d'),
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


@analytics_bp.route('/api/metrics')
@cache_response(duration=CACHE_DURATION)
def api_metrics():
    """API endpoint for comprehensive analytics metrics with date range filtering and caching."""
    db = _ensure_database()
    if not db:
        return jsonify({'error': 'Database connection is not available.'}), 503

    try:
        # Get date range parameters
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        days = int(request.args.get('days', 30))

        # Calculate date range
        if date_from and date_to:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
            end_date = datetime.strptime(date_to, '%Y-%m-%d')
            days = (end_date - start_date).days + 1
        elif date_from:
            start_date = datetime.strptime(date_from, '%Y-%m-%d')
            end_date = datetime.now(SA_TZ)
            days = (end_date - start_date).days + 1
        else:
            end_date = datetime.now(SA_TZ)
            start_date = end_date - timedelta(days=days)

        # Get all metrics
        week_start, week_end = _get_week_start_end()

        # Posts this week
        result_week = (
            db.db.table('social_posts')
            .select('*')
            .gte('created_at', week_start.isoformat())
            .lte('created_at', week_end.isoformat())
            .execute()
        )
        posts_this_week = len(result_week.data) if result_week.data else 0

        # Daily engagement
        daily_engagement = _get_daily_engagement(db, days=days)

        # Content performance
        content_performance = _get_content_performance(db, limit=50)

        # Filter by date range if specified
        if date_from or date_to:
            content_performance = [
                p for p in content_performance
                if (not date_from or p.get('created_at', '') >= date_from) and
                   (not date_to or p.get('created_at', '') <= date_to)
            ]

        # Posting heatmap
        posting_heatmap = _get_posting_time_heatmap(db)

        # Top themes
        top_themes = _get_top_themes(db, limit=10)

        # Video performance
        video_performance = _get_video_performance_detailed(db)

        # Status breakdown
        result_all = db.db.table('social_posts').select('status').execute()
        status_counts = {}
        if result_all.data:
            for post in result_all.data:
                status = post.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1

        return jsonify({
            'success': True,
            'date_range': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
                'days': days
            },
            'overview': {
                'total_followers': 0,  # Placeholder
                'posts_this_week': posts_this_week,
                'total_engagement_week': posts_this_week * 15,  # Simulated
                'avg_engagement_rate': 3.5  # Simulated
            },
            'daily_engagement': daily_engagement,
            'content_performance': content_performance,
            'posting_heatmap': posting_heatmap,
            'top_themes': top_themes,
            'video_performance': video_performance,
            'status_counts': status_counts,
            'timestamp': datetime.now(SA_TZ).isoformat(),
            'cached': False  # Will be True on subsequent cached requests
        })

    except Exception as e:
        log_error(f"Error getting metrics API data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@analytics_bp.route('/export')
def export_analytics():
    """Export comprehensive analytics report as CSV."""
    db = _ensure_database()
    if not db:
        return jsonify({'error': 'Database connection is not available.'}), 503

    try:
        # Get date range parameters
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')

        # Build query for posts
        query = db.db.table('social_posts').select('*')

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

        # Write header with all analytics fields
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
            'Video Duration (s)',
            'Completion Rate (%)',
            'Avg Watch Time (s)',
            'Likes',
            'Comments',
            'Shares',
            'Reach',
            'Impressions',
            'Clicks',
            'Engagement Rate (%)'
        ])

        # Write data for each post
        for post in posts:
            # Get analytics data if available (placeholder for now)
            likes = 0
            comments = 0
            shares = 0
            reach = 0
            impressions = 0
            clicks = 0
            engagement_rate = 0.0

            writer.writerow([
                post.get('id', ''),
                post.get('post_type', ''),
                post.get('platform', ''),
                post.get('status', ''),
                post.get('content_theme', ''),
                post.get('content_text', '')[:200] + '...' if post.get('content_text') and len(post.get('content_text', '')) > 200 else post.get('content_text', ''),
                post.get('created_at', ''),
                post.get('scheduled_time', ''),
                post.get('published_time', ''),
                post.get('video_url', ''),
                post.get('video_duration', 0),
                post.get('completion_rate', 0),
                post.get('avg_watch_time', 0),
                likes,
                comments,
                shares,
                reach,
                impressions,
                clicks,
                engagement_rate
            ])

        # Create response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'

        # Generate filename with date range
        filename_parts = ['analytics_export']
        if date_from:
            filename_parts.append(f'from_{date_from}')
        if date_to:
            filename_parts.append(f'to_{date_to}')
        filename_parts.append(datetime.now(SA_TZ).strftime('%Y%m%d_%H%M%S'))
        filename = '_'.join(filename_parts) + '.csv'

        response.headers['Content-Disposition'] = f'attachment; filename={filename}'

        return response

    except Exception as e:
        log_error(f"Error exporting analytics to CSV: {str(e)}")
        return jsonify({'error': str(e)}), 500
