"""
Weekly Report Generator for Refiloe Marketing System

Generates comprehensive weekly performance reports from social media metrics including:
- Posts published (count, reach, engagement)
- Top and worst performing posts
- Video performance metrics
- Analytics summary
- Insights and recommendations

Supports multiple output formats:
- Plain text (for WhatsApp/console)
- HTML (for web dashboard)
- JSON (for API/programmatic access)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pytz

from database import SocialMediaDatabase
from utils.logger import log_debug, log_error, log_info, log_warning
from utils.whatsapp_notifier import WhatsAppNotifier


SA_TIMEZONE = pytz.timezone("Africa/Johannesburg")


class WeeklyReportGenerator:
    """Generates comprehensive weekly performance reports for social media content."""

    def __init__(self, supabase_client):
        """
        Initialize the weekly report generator.

        Args:
            supabase_client: Supabase client instance for database queries
        """
        self.supabase_client = supabase_client
        self.db = SocialMediaDatabase(supabase_client)
        self.sa_tz = SA_TIMEZONE
        self._cached_report_data = None  # Cache for report data to avoid regenerating

    def generate_report(
        self,
        week_start: Optional[datetime] = None,
        week_end: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate a weekly report for the specified period.

        Args:
            week_start: Start date for the report period (defaults to 7 days ago)
            week_end: End date for the report period (defaults to now)

        Returns:
            Dict containing:
                - success: bool
                - metrics: dict (raw metrics data)
                - formatted: dict (formatted versions for different outputs)
                - insights: list (actionable insights)
                - period: dict (start and end dates)
                - error: str (if success is False)
        """
        try:
            # Determine date range
            if week_end is None:
                week_end = datetime.now(self.sa_tz)
            else:
                # Ensure week_end is timezone-aware
                if week_end.tzinfo is None:
                    week_end = self.sa_tz.localize(week_end)
                else:
                    week_end = week_end.astimezone(self.sa_tz)

            if week_start is None:
                week_start = week_end - timedelta(days=7)
            else:
                # Ensure week_start is timezone-aware
                if week_start.tzinfo is None:
                    week_start = self.sa_tz.localize(week_start)
                else:
                    week_start = week_start.astimezone(self.sa_tz)

            log_info(f"Generating weekly report from {week_start.date()} to {week_end.date()}")

            # Collect metrics from all sources
            metrics = self._collect_metrics(week_start, week_end)

            # Add growth metrics (week-over-week comparison)
            growth_metrics = self._calculate_growth_metrics(week_start, week_end)
            metrics['growth'] = growth_metrics

            # Cache the data for format methods
            self._cached_report_data = {
                'metrics': metrics,
                'week_start': week_start,
                'week_end': week_end
            }

            # Generate insights
            insights = self._generate_insights(metrics)

            log_info("Weekly report generated successfully")

            return {
                "success": True,
                "metrics": metrics,
                "insights": insights,
                "period": {
                    "start": week_start.isoformat(),
                    "end": week_end.isoformat()
                }
            }

        except Exception as e:
            log_error(f"Error generating weekly report: {e}")
            return {
                "success": False,
                "metrics": {},
                "insights": [],
                "period": {},
                "error": str(e)
            }

    def _collect_metrics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect all metrics for the report period.

        Args:
            start_date: Start of the reporting period
            end_date: End of the reporting period

        Returns:
            Dict containing all collected metrics
        """
        metrics = {
            "posts": self._collect_post_metrics(start_date, end_date),
            "analytics": self._collect_analytics_metrics(start_date, end_date),
            "videos": self._collect_video_metrics(start_date, end_date),
            "scheduled": self._collect_scheduled_posts(end_date),
        }

        return metrics

    def _collect_post_metrics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect metrics from social_posts table.

        Args:
            start_date: Start of the reporting period
            end_date: End of the reporting period

        Returns:
            Dict containing post metrics
        """
        try:
            # Query all posts created in the date range
            all_posts_result = self.supabase_client.table('social_posts').select(
                'id, post_type, caption_text, published_time, status, platform, created_at'
            ).gte(
                'created_at', start_date.isoformat()
            ).lte(
                'created_at', end_date.isoformat()
            ).execute()

            all_posts = all_posts_result.data if all_posts_result.data else []

            # Filter by status
            published_posts = [p for p in all_posts if p.get('status') == 'published']
            failed_posts = [p for p in all_posts if p.get('status') == 'failed']

            log_info(f"Found {len(all_posts)} total posts, {len(published_posts)} published, {len(failed_posts)} failed in the reporting period")

            return {
                "total_posts_created": len(all_posts),
                "total_posts_published": len(published_posts),
                "total_posts_failed": len(failed_posts),
                "posts_by_type": self._group_by_field(published_posts, 'post_type'),
                "posts_by_platform": self._group_by_field(published_posts, 'platform'),
                "posts": published_posts
            }

        except Exception as e:
            log_error(f"Error collecting post metrics: {e}")
            return {
                "total_posts_created": 0,
                "total_posts_published": 0,
                "total_posts_failed": 0,
                "posts_by_type": {},
                "posts_by_platform": {},
                "posts": []
            }

    def _collect_analytics_metrics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect metrics from social_analytics table.

        Args:
            start_date: Start of the reporting period
            end_date: End of the reporting period

        Returns:
            Dict containing analytics metrics
        """
        try:
            # Get post IDs from the period
            posts_result = self.supabase_client.table('social_posts').select(
                'id'
            ).eq(
                'status', 'published'
            ).gte(
                'published_time', start_date.isoformat()
            ).lte(
                'published_time', end_date.isoformat()
            ).execute()

            post_ids = [p['id'] for p in posts_result.data] if posts_result.data else []

            if not post_ids:
                log_info("No published posts found, skipping analytics collection")
                return self._empty_analytics_metrics()

            # Query analytics for these posts
            analytics_result = self.supabase_client.table('social_analytics').select(
                'post_id, likes, comments, shares, reach, impressions, clicks, engagement_rate'
            ).in_(
                'post_id', post_ids
            ).execute()

            analytics = analytics_result.data if analytics_result.data else []

            log_info(f"Found analytics for {len(analytics)} posts")

            # Calculate aggregated metrics
            total_reach = sum(a.get('reach', 0) for a in analytics)
            total_impressions = sum(a.get('impressions', 0) for a in analytics)
            total_likes = sum(a.get('likes', 0) for a in analytics)
            total_comments = sum(a.get('comments', 0) for a in analytics)
            total_shares = sum(a.get('shares', 0) for a in analytics)
            total_clicks = sum(a.get('clicks', 0) for a in analytics)
            total_engagement = total_likes + total_comments + total_shares

            # Calculate average engagement rate
            engagement_rates = [a.get('engagement_rate', 0) for a in analytics if a.get('engagement_rate')]
            avg_engagement_rate = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0

            # Find top and worst performers
            top_posts, worst_post = self._find_top_worst_performers(analytics)

            return {
                "total_reach": total_reach,
                "total_impressions": total_impressions,
                "total_likes": total_likes,
                "total_comments": total_comments,
                "total_shares": total_shares,
                "total_clicks": total_clicks,
                "total_engagement": total_engagement,
                "avg_engagement_rate": round(avg_engagement_rate, 2),
                "top_performers": top_posts,
                "worst_performer": worst_post,
                "analytics_count": len(analytics)
            }

        except Exception as e:
            log_error(f"Error collecting analytics metrics: {e}")
            return self._empty_analytics_metrics()

    def _collect_video_metrics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect metrics from generated_videos table.

        Args:
            start_date: Start of the reporting period
            end_date: End of the reporting period

        Returns:
            Dict containing video metrics
        """
        try:
            # Query generated videos in the date range
            result = self.supabase_client.table('generated_videos').select(
                'id, video_id, video_url, status, created_at'
            ).gte(
                'created_at', start_date.isoformat()
            ).lte(
                'created_at', end_date.isoformat()
            ).execute()

            videos = result.data if result.data else []

            log_info(f"Found {len(videos)} generated videos in the reporting period")

            # Count by status
            completed_videos = [v for v in videos if v.get('status') == 'completed']

            # Get video posts from social_posts
            video_posts_result = self.supabase_client.table('social_posts').select(
                'completion_rate, avg_watch_time, video_url, video_duration'
            ).eq(
                'post_type', 'video'
            ).eq(
                'status', 'published'
            ).gte(
                'published_time', start_date.isoformat()
            ).lte(
                'published_time', end_date.isoformat()
            ).execute()

            video_posts = video_posts_result.data if video_posts_result.data else []

            # Calculate video metrics
            completion_rates = [v.get('completion_rate', 0) for v in video_posts if v.get('completion_rate')]
            avg_completion_rate = sum(completion_rates) / len(completion_rates) if completion_rates else 0

            watch_times = [v.get('avg_watch_time', 0) for v in video_posts if v.get('avg_watch_time')]
            avg_watch_time = sum(watch_times) / len(watch_times) if watch_times else 0

            # Calculate total video duration
            durations = [v.get('video_duration', 0) for v in video_posts if v.get('video_duration')]
            total_video_duration = sum(durations) if durations else 0

            return {
                "videos_generated": len(videos),
                "videos_completed": len(completed_videos),
                "videos_published": len(video_posts),
                "total_video_duration": round(total_video_duration, 2),
                "avg_completion_rate": round(avg_completion_rate, 2),
                "avg_watch_time": round(avg_watch_time, 2),
                "total_video_views": 0  # Placeholder - would need view tracking
            }

        except Exception as e:
            log_error(f"Error collecting video metrics: {e}")
            return {
                "videos_generated": 0,
                "videos_completed": 0,
                "videos_published": 0,
                "avg_completion_rate": 0,
                "avg_watch_time": 0,
                "total_video_views": 0
            }

    def _collect_scheduled_posts(self, end_date: datetime) -> Dict[str, Any]:
        """
        Collect information about upcoming scheduled posts.

        Args:
            end_date: Reference date for calculating next week

        Returns:
            Dict containing scheduled post information
        """
        try:
            # Query scheduled posts for the next 7 days
            next_week_start = end_date
            next_week_end = end_date + timedelta(days=7)

            result = self.supabase_client.table('social_posts').select(
                'id, scheduled_time, post_type'
            ).eq(
                'status', 'scheduled'
            ).gte(
                'scheduled_time', next_week_start.isoformat()
            ).lte(
                'scheduled_time', next_week_end.isoformat()
            ).execute()

            scheduled_posts = result.data if result.data else []

            log_info(f"Found {len(scheduled_posts)} scheduled posts for next week")

            return {
                "next_week_scheduled": len(scheduled_posts),
                "scheduled_by_type": self._group_by_field(scheduled_posts, 'post_type')
            }

        except Exception as e:
            log_error(f"Error collecting scheduled posts: {e}")
            return {
                "next_week_scheduled": 0,
                "scheduled_by_type": {}
            }

    def _find_top_worst_performers(
        self,
        analytics: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Find top 3 and worst performing posts based on engagement rate.

        Args:
            analytics: List of analytics records

        Returns:
            Tuple of (top_performers, worst_performer)
        """
        if not analytics:
            return [], None

        # Sort by engagement rate
        sorted_analytics = sorted(
            analytics,
            key=lambda x: x.get('engagement_rate', 0),
            reverse=True
        )

        # Get top 3
        top_performers = []
        for i, record in enumerate(sorted_analytics[:3]):
            # Get post details
            post_id = record.get('post_id')
            post_details = self._get_post_details(post_id)

            top_performers.append({
                **record,
                **post_details
            })

        # Get worst performer
        worst_performer = None
        if len(sorted_analytics) > 0:
            worst_record = sorted_analytics[-1]
            post_id = worst_record.get('post_id')
            post_details = self._get_post_details(post_id)

            worst_performer = {
                **worst_record,
                **post_details
            }

        return top_performers, worst_performer

    def _get_post_details(self, post_id: str) -> Dict[str, Any]:
        """
        Get post details for a given post ID.

        Args:
            post_id: Post UUID

        Returns:
            Dict containing post details
        """
        try:
            result = self.supabase_client.table('social_posts').select(
                'caption_text, post_type, platform, published_time'
            ).eq(
                'id', post_id
            ).single().execute()

            if result.data:
                return {
                    'post_caption': result.data.get('caption_text', '')[:100],  # First 100 chars
                    'post_type': result.data.get('post_type', ''),
                    'platform': result.data.get('platform', ''),
                    'published_time': result.data.get('published_time', '')
                }

        except Exception as e:
            log_debug(f"Error getting post details for {post_id}: {e}")

        return {
            'post_caption': '',
            'post_type': '',
            'platform': '',
            'published_time': ''
        }

    def _group_by_field(
        self,
        items: List[Dict[str, Any]],
        field: str
    ) -> Dict[str, int]:
        """
        Group items by a specific field and count them.

        Args:
            items: List of items to group
            field: Field name to group by

        Returns:
            Dict mapping field values to counts
        """
        grouped = {}
        for item in items:
            value = item.get(field, 'unknown')
            grouped[value] = grouped.get(value, 0) + 1
        return grouped

    def _empty_analytics_metrics(self) -> Dict[str, Any]:
        """Return empty analytics metrics structure."""
        return {
            "total_reach": 0,
            "total_impressions": 0,
            "total_likes": 0,
            "total_comments": 0,
            "total_shares": 0,
            "total_clicks": 0,
            "total_engagement": 0,
            "avg_engagement_rate": 0,
            "top_performers": [],
            "worst_performer": None,
            "analytics_count": 0
        }

    # ================================================================
    # FORMATTING METHODS
    # ================================================================

    def _format_text(
        self,
        metrics: Dict[str, Any],
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """
        Format metrics as plain text (suitable for WhatsApp/console).

        Args:
            metrics: Collected metrics
            start_date: Start of reporting period
            end_date: End of reporting period

        Returns:
            Formatted text report
        """
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append(f"📊 REFILOE MARKETING - WEEKLY REPORT")
        lines.append(f"Week of {start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}")
        lines.append("=" * 60)
        lines.append("")

        # Post Metrics
        lines.append("📝 CONTENT PUBLISHED")
        lines.append("-" * 60)
        posts = metrics.get('posts', {})
        lines.append(f"• Total Posts Published: {posts.get('total_posts', 0)}")

        posts_by_type = posts.get('posts_by_type', {})
        if posts_by_type:
            lines.append("• Posts by Type:")
            for ptype, count in posts_by_type.items():
                lines.append(f"  - {ptype}: {count}")
        lines.append("")

        # Analytics Metrics
        lines.append("📈 PERFORMANCE METRICS")
        lines.append("-" * 60)
        analytics = metrics.get('analytics', {})
        lines.append(f"• Total Reach: {analytics.get('total_reach', 0):,}")
        lines.append(f"• Total Impressions: {analytics.get('total_impressions', 0):,}")
        lines.append(f"• Total Engagement: {analytics.get('total_engagement', 0):,}")
        lines.append(f"  - Likes: {analytics.get('total_likes', 0):,}")
        lines.append(f"  - Comments: {analytics.get('total_comments', 0):,}")
        lines.append(f"  - Shares: {analytics.get('total_shares', 0):,}")
        lines.append(f"• Average Engagement Rate: {analytics.get('avg_engagement_rate', 0):.2f}%")
        lines.append("")

        # Top Performers
        top_performers = analytics.get('top_performers', [])
        if top_performers:
            lines.append("🏆 TOP PERFORMING POSTS")
            lines.append("-" * 60)
            for i, post in enumerate(top_performers, 1):
                lines.append(f"{i}. Engagement Rate: {post.get('engagement_rate', 0):.2f}%")
                lines.append(f"   Reach: {post.get('reach', 0):,} | Likes: {post.get('likes', 0)} | Comments: {post.get('comments', 0)} | Shares: {post.get('shares', 0)}")
                caption = post.get('post_caption', '')
                if caption:
                    lines.append(f"   Caption: {caption}...")
                lines.append("")

        # Worst Performer
        worst = analytics.get('worst_performer')
        if worst:
            lines.append("⚠️  LOWEST PERFORMING POST")
            lines.append("-" * 60)
            lines.append(f"Engagement Rate: {worst.get('engagement_rate', 0):.2f}%")
            lines.append(f"Reach: {worst.get('reach', 0):,} | Likes: {worst.get('likes', 0)} | Comments: {worst.get('comments', 0)}")
            caption = worst.get('post_caption', '')
            if caption:
                lines.append(f"Caption: {caption}...")
            lines.append("")

        # Video Metrics
        videos = metrics.get('videos', {})
        if videos.get('videos_generated', 0) > 0:
            lines.append("🎥 VIDEO PERFORMANCE")
            lines.append("-" * 60)
            lines.append(f"• Videos Generated: {videos.get('videos_generated', 0)}")
            lines.append(f"• Videos Published: {videos.get('videos_published', 0)}")
            lines.append(f"• Average Completion Rate: {videos.get('avg_completion_rate', 0):.2f}%")
            lines.append(f"• Average Watch Time: {videos.get('avg_watch_time', 0):.1f}s")
            lines.append("")

        # Insights and Recommendations
        lines.append("💡 INSIGHTS & RECOMMENDATIONS")
        lines.append("-" * 60)
        insights = self._generate_insights(metrics)
        for insight in insights:
            lines.append(f"• {insight}")
        lines.append("")

        # Next Week Preview
        scheduled = metrics.get('scheduled', {})
        lines.append("📅 NEXT WEEK PREVIEW")
        lines.append("-" * 60)
        lines.append(f"• Scheduled Posts: {scheduled.get('next_week_scheduled', 0)}")

        scheduled_by_type = scheduled.get('scheduled_by_type', {})
        if scheduled_by_type:
            lines.append("• Scheduled by Type:")
            for stype, count in scheduled_by_type.items():
                lines.append(f"  - {stype}: {count}")
        lines.append("")

        lines.append("=" * 60)
        lines.append(f"Generated: {datetime.now(self.sa_tz).strftime('%Y-%m-%d %H:%M:%S SAST')}")
        lines.append("=" * 60)

        return "\n".join(lines)

    def _format_html(
        self,
        metrics: Dict[str, Any],
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """
        Format metrics as HTML (suitable for web dashboard).

        Args:
            metrics: Collected metrics
            start_date: Start of reporting period
            end_date: End of reporting period

        Returns:
            Formatted HTML report
        """
        posts = metrics.get('posts', {})
        analytics = metrics.get('analytics', {})
        videos = metrics.get('videos', {})
        scheduled = metrics.get('scheduled', {})

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Report - {start_date.strftime('%b %d')} to {end_date.strftime('%b %d, %Y')}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2em;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 1.2em;
            opacity: 0.9;
        }}
        .section {{
            background: white;
            padding: 25px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            margin-top: 0;
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }}
        .metric-label {{
            font-size: 0.9em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .top-post {{
            background: #e8f5e9;
            padding: 15px;
            margin: 10px 0;
            border-radius: 6px;
            border-left: 4px solid #4caf50;
        }}
        .worst-post {{
            background: #fff3e0;
            padding: 15px;
            margin: 10px 0;
            border-radius: 6px;
            border-left: 4px solid #ff9800;
        }}
        .insight {{
            background: #e3f2fd;
            padding: 12px 15px;
            margin: 8px 0;
            border-radius: 6px;
            border-left: 4px solid #2196f3;
        }}
        .footer {{
            text-align: center;
            color: #666;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
        .emoji {{
            font-size: 1.5em;
            margin-right: 10px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Refiloe Marketing - Weekly Report</h1>
        <p>Week of {start_date.strftime('%B %d')} - {end_date.strftime('%B %d, %Y')}</p>
    </div>

    <div class="section">
        <h2>📈 Performance Overview</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Posts Published</div>
                <div class="metric-value">{posts.get('total_posts', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Reach</div>
                <div class="metric-value">{analytics.get('total_reach', 0):,}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Engagement</div>
                <div class="metric-value">{analytics.get('total_engagement', 0):,}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Engagement Rate</div>
                <div class="metric-value">{analytics.get('avg_engagement_rate', 0):.1f}%</div>
            </div>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Likes</div>
                <div class="metric-value">{analytics.get('total_likes', 0):,}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Comments</div>
                <div class="metric-value">{analytics.get('total_comments', 0):,}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Shares</div>
                <div class="metric-value">{analytics.get('total_shares', 0):,}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Impressions</div>
                <div class="metric-value">{analytics.get('total_impressions', 0):,}</div>
            </div>
        </div>
    </div>
"""

        # Top Performers
        top_performers = analytics.get('top_performers', [])
        if top_performers:
            html += """
    <div class="section">
        <h2>🏆 Top Performing Posts</h2>
"""
            for i, post in enumerate(top_performers, 1):
                caption = post.get('post_caption', 'No caption')[:150]
                html += f"""
        <div class="top-post">
            <strong>#{i} - Engagement Rate: {post.get('engagement_rate', 0):.2f}%</strong><br>
            Reach: {post.get('reach', 0):,} | Likes: {post.get('likes', 0)} | Comments: {post.get('comments', 0)} | Shares: {post.get('shares', 0)}<br>
            <em>{caption}...</em>
        </div>
"""
            html += "    </div>\n"

        # Worst Performer
        worst = analytics.get('worst_performer')
        if worst:
            caption = worst.get('post_caption', 'No caption')[:150]
            html += f"""
    <div class="section">
        <h2>⚠️ Lowest Performing Post</h2>
        <div class="worst-post">
            <strong>Engagement Rate: {worst.get('engagement_rate', 0):.2f}%</strong><br>
            Reach: {worst.get('reach', 0):,} | Likes: {worst.get('likes', 0)} | Comments: {worst.get('comments', 0)}<br>
            <em>{caption}...</em>
        </div>
    </div>
"""

        # Video Performance
        if videos.get('videos_generated', 0) > 0:
            html += f"""
    <div class="section">
        <h2>🎥 Video Performance</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Videos Generated</div>
                <div class="metric-value">{videos.get('videos_generated', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Videos Published</div>
                <div class="metric-value">{videos.get('videos_published', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Completion Rate</div>
                <div class="metric-value">{videos.get('avg_completion_rate', 0):.1f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Watch Time</div>
                <div class="metric-value">{videos.get('avg_watch_time', 0):.1f}s</div>
            </div>
        </div>
    </div>
"""

        # Insights
        insights = self._generate_insights(metrics)
        if insights:
            html += """
    <div class="section">
        <h2>💡 Insights & Recommendations</h2>
"""
            for insight in insights:
                html += f'        <div class="insight">{insight}</div>\n'
            html += "    </div>\n"

        # Next Week Preview
        html += f"""
    <div class="section">
        <h2>📅 Next Week Preview</h2>
        <p><strong>{scheduled.get('next_week_scheduled', 0)} posts</strong> scheduled for the upcoming week.</p>
"""

        scheduled_by_type = scheduled.get('scheduled_by_type', {})
        if scheduled_by_type:
            html += "        <ul>\n"
            for stype, count in scheduled_by_type.items():
                html += f"            <li>{stype}: {count}</li>\n"
            html += "        </ul>\n"

        html += "    </div>\n"

        # Footer
        html += f"""
    <div class="footer">
        <p>Generated on {datetime.now(self.sa_tz).strftime('%Y-%m-%d at %H:%M:%S SAST')}</p>
        <p>Refiloe Marketing System</p>
    </div>
</body>
</html>
"""
        return html

    def _format_json(
        self,
        metrics: Dict[str, Any],
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """
        Format metrics as JSON (suitable for API).

        Args:
            metrics: Collected metrics
            start_date: Start of reporting period
            end_date: End of reporting period

        Returns:
            Formatted JSON string
        """
        report_data = {
            "report_metadata": {
                "generated_at": datetime.now(self.sa_tz).isoformat(),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "report_type": "weekly"
            },
            "summary": {
                "posts_published": metrics.get('posts', {}).get('total_posts', 0),
                "total_reach": metrics.get('analytics', {}).get('total_reach', 0),
                "total_engagement": metrics.get('analytics', {}).get('total_engagement', 0),
                "avg_engagement_rate": metrics.get('analytics', {}).get('avg_engagement_rate', 0),
                "videos_generated": metrics.get('videos', {}).get('videos_generated', 0),
                "next_week_scheduled": metrics.get('scheduled', {}).get('next_week_scheduled', 0)
            },
            "posts": metrics.get('posts', {}),
            "analytics": metrics.get('analytics', {}),
            "videos": metrics.get('videos', {}),
            "scheduled": metrics.get('scheduled', {}),
            "insights": self._generate_insights(metrics)
        }

        return json.dumps(report_data, indent=2)

    def _calculate_growth_metrics(
        self,
        week_start: datetime,
        week_end: datetime
    ) -> Dict[str, Any]:
        """
        Calculate week-over-week growth metrics.

        Args:
            week_start: Start of current week
            week_end: End of current week

        Returns:
            Dict containing growth metrics and comparisons
        """
        try:
            # Calculate previous week period
            prev_week_end = week_start - timedelta(seconds=1)
            prev_week_start = prev_week_end - timedelta(days=7)

            log_info(f"Calculating growth metrics: comparing {week_start.date()}-{week_end.date()} to {prev_week_start.date()}-{prev_week_end.date()}")

            # Get metrics for previous week
            prev_metrics = self._collect_metrics(prev_week_start, prev_week_end)

            # Get current week metrics from cache
            curr_metrics = self._cached_report_data.get('metrics', {}) if self._cached_report_data else {}

            growth = {}

            # Compare posts
            curr_posts = curr_metrics.get('posts', {}).get('total_posts_published', 0)
            prev_posts = prev_metrics.get('posts', {}).get('total_posts_published', 0)
            growth['posts_change'] = self._calculate_percentage_change(curr_posts, prev_posts)
            growth['posts_significant'] = abs(growth['posts_change']) > 20

            # Compare engagement
            curr_engagement = curr_metrics.get('analytics', {}).get('total_engagement', 0)
            prev_engagement = prev_metrics.get('analytics', {}).get('total_engagement', 0)
            growth['engagement_change'] = self._calculate_percentage_change(curr_engagement, prev_engagement)
            growth['engagement_significant'] = abs(growth['engagement_change']) > 20

            # Compare reach
            curr_reach = curr_metrics.get('analytics', {}).get('total_reach', 0)
            prev_reach = prev_metrics.get('analytics', {}).get('total_reach', 0)
            growth['reach_change'] = self._calculate_percentage_change(curr_reach, prev_reach)
            growth['reach_significant'] = abs(growth['reach_change']) > 20

            # Compare engagement rate
            curr_rate = curr_metrics.get('analytics', {}).get('avg_engagement_rate', 0)
            prev_rate = prev_metrics.get('analytics', {}).get('avg_engagement_rate', 0)
            growth['engagement_rate_change'] = self._calculate_percentage_change(curr_rate, prev_rate)
            growth['engagement_rate_significant'] = abs(growth['engagement_rate_change']) > 20

            # Compare videos
            curr_videos = curr_metrics.get('videos', {}).get('videos_published', 0)
            prev_videos = prev_metrics.get('videos', {}).get('videos_published', 0)
            growth['videos_change'] = self._calculate_percentage_change(curr_videos, prev_videos)
            growth['videos_significant'] = abs(growth['videos_change']) > 20

            log_info(f"Growth metrics calculated successfully")
            return growth

        except Exception as e:
            log_error(f"Error calculating growth metrics: {e}")
            return {
                'posts_change': 0,
                'engagement_change': 0,
                'reach_change': 0,
                'engagement_rate_change': 0,
                'videos_change': 0,
                'posts_significant': False,
                'engagement_significant': False,
                'reach_significant': False,
                'engagement_rate_significant': False,
                'videos_significant': False
            }

    def _calculate_percentage_change(self, current: float, previous: float) -> float:
        """Calculate percentage change between two values."""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)

    def _generate_insights(self, metrics: Dict[str, Any]) -> List[str]:
        """
        Generate insights and recommendations based on metrics.

        Args:
            metrics: Collected metrics

        Returns:
            List of insight strings
        """
        insights = []

        posts = metrics.get('posts', {})
        analytics = metrics.get('analytics', {})
        videos = metrics.get('videos', {})
        scheduled = metrics.get('scheduled', {})
        growth = metrics.get('growth', {})

        total_posts = posts.get('total_posts', 0)
        avg_engagement = analytics.get('avg_engagement_rate', 0)
        total_reach = analytics.get('total_reach', 0)
        next_week_scheduled = scheduled.get('next_week_scheduled', 0)

        # Publishing frequency insight
        if total_posts < 5:
            insights.append(f"Publishing frequency is low ({total_posts} posts this week). Consider increasing to 7-10 posts per week for better audience engagement.")
        elif total_posts > 15:
            insights.append(f"High publishing frequency ({total_posts} posts). Monitor engagement rates to ensure quality isn't being sacrificed for quantity.")

        # Engagement rate insight
        if avg_engagement > 5:
            insights.append(f"Excellent engagement rate of {avg_engagement:.1f}%! Your audience is highly engaged with your content.")
        elif avg_engagement > 2:
            insights.append(f"Good engagement rate of {avg_engagement:.1f}%. Continue focusing on content that resonates with your audience.")
        elif avg_engagement > 0:
            insights.append(f"Engagement rate of {avg_engagement:.1f}% has room for improvement. Consider testing different content formats and posting times.")

        # Reach insight
        if total_reach > 0:
            avg_reach_per_post = total_reach / total_posts if total_posts > 0 else 0
            insights.append(f"Average reach per post: {avg_reach_per_post:,.0f}. Focus on increasing reach through hashtags and optimal posting times.")

        # Video performance insight
        videos_published = videos.get('videos_published', 0)
        if videos_published > 0:
            completion_rate = videos.get('avg_completion_rate', 0)
            if completion_rate > 70:
                insights.append(f"Video completion rate of {completion_rate:.1f}% is excellent! Viewers are watching most of your videos.")
            elif completion_rate > 50:
                insights.append(f"Video completion rate of {completion_rate:.1f}% is good. Consider making videos slightly shorter to increase completion.")
            elif completion_rate > 0:
                insights.append(f"Video completion rate of {completion_rate:.1f}% suggests viewers aren't finishing videos. Try shorter, more engaging content.")

        # Content pipeline insight
        if next_week_scheduled < 3:
            insights.append(f"⚠️ Low content pipeline: Only {next_week_scheduled} posts scheduled for next week. Generate more content to maintain consistency.")
        elif next_week_scheduled >= 7:
            insights.append(f"✅ Strong content pipeline: {next_week_scheduled} posts scheduled for next week. Great planning!")

        # Top performer insight
        top_performers = analytics.get('top_performers', [])
        if top_performers:
            top_post = top_performers[0]
            top_type = top_post.get('post_type', 'content')
            insights.append(f"Your top performing post was a {top_type} post with {top_post.get('engagement_rate', 0):.1f}% engagement. Consider creating more similar content.")

        # Growth insights
        if growth:
            # Engagement growth
            engagement_change = growth.get('engagement_change', 0)
            if growth.get('engagement_significant'):
                direction = "up" if engagement_change > 0 else "down"
                insights.append(f"🔥 Significant change: Engagement is {direction} {abs(engagement_change):.0f}% compared to last week!")

            # Reach growth
            reach_change = growth.get('reach_change', 0)
            if growth.get('reach_significant'):
                direction = "increased" if reach_change > 0 else "decreased"
                insights.append(f"📊 Reach has {direction} by {abs(reach_change):.0f}% compared to last week.")

        return insights

    # ================================================================
    # PUBLIC API METHODS
    # ================================================================

    def format_for_whatsapp(self) -> str:
        """
        Format report for WhatsApp (concise, under 4000 characters).

        Returns:
            Formatted WhatsApp message string
        """
        if not self._cached_report_data:
            log_error("No report data available. Call generate_report() first.")
            return "Error: No report data available"

        metrics = self._cached_report_data['metrics']
        week_start = self._cached_report_data['week_start']
        week_end = self._cached_report_data['week_end']
        insights = self._generate_insights(metrics)

        posts = metrics.get('posts', {})
        analytics = metrics.get('analytics', {})
        videos = metrics.get('videos', {})
        scheduled = metrics.get('scheduled', {})
        growth = metrics.get('growth', {})

        # Build concise WhatsApp message
        lines = []
        lines.append("📊 *REFILOE WEEKLY REPORT*")
        lines.append(f"Week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")

        # Content Published
        lines.append("📱 *CONTENT PUBLISHED*")
        lines.append(f"• Posts: {posts.get('total_posts_published', 0)}")
        lines.append(f"• Videos: {videos.get('videos_published', 0)}")
        lines.append(f"• Reach: {analytics.get('total_reach', 0):,}")
        lines.append("")

        # Engagement
        lines.append("💬 *ENGAGEMENT*")
        lines.append(f"• Total: {analytics.get('total_engagement', 0):,}")
        lines.append(f"• Rate: {analytics.get('avg_engagement_rate', 0):.1f}%")
        lines.append(f"• Comments: {analytics.get('total_comments', 0):,}")

        # Show growth if significant
        if growth.get('engagement_significant'):
            change = growth.get('engagement_change', 0)
            emoji = "📈" if change > 0 else "📉"
            lines.append(f"{emoji} {'+' if change > 0 else ''}{change:.0f}% vs last week")
        lines.append("")

        # Top Performer
        top_performers = analytics.get('top_performers', [])
        if top_performers:
            top = top_performers[0]
            lines.append("🏆 *TOP PERFORMER*")
            caption = top.get('post_caption', '')[:60]
            lines.append(f'"{caption}..."')
            lines.append(f"Engagement: {top.get('engagement_rate', 0):.1f}% | Reach: {top.get('reach', 0):,}")
            lines.append("")

        # Week Highlights
        lines.append("📈 *WEEK HIGHLIGHTS*")
        for insight in insights[:3]:  # Top 3 insights only
            # Remove emojis if they make it too long
            clean_insight = insight
            lines.append(f"• {clean_insight}")
        lines.append("")

        # Dashboard link
        dashboard_url = os.getenv('DASHBOARD_URL', 'https://refiloe-marketing.com')
        lines.append("🔗 *Full Dashboard:*")
        lines.append(dashboard_url)

        message = "\n".join(lines)

        # Ensure under 4000 characters
        if len(message) > 4000:
            # Trim insights if needed
            lines = []
            lines.append("📊 *REFILOE WEEKLY REPORT*")
            lines.append(f"Week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("")
            lines.append("📱 *CONTENT*")
            lines.append(f"Posts: {posts.get('total_posts_published', 0)} | Videos: {videos.get('videos_published', 0)}")
            lines.append(f"Reach: {analytics.get('total_reach', 0):,}")
            lines.append("")
            lines.append("💬 *ENGAGEMENT*")
            lines.append(f"Total: {analytics.get('total_engagement', 0):,} | Rate: {analytics.get('avg_engagement_rate', 0):.1f}%")
            lines.append("")
            lines.append("🔗 Full Dashboard:")
            lines.append(dashboard_url)
            message = "\n".join(lines)

        log_info(f"WhatsApp report formatted ({len(message)} characters)")
        return message

    def format_for_html(self) -> str:
        """
        Format report for HTML web dashboard.

        Returns:
            Formatted HTML string
        """
        if not self._cached_report_data:
            log_error("No report data available. Call generate_report() first.")
            return "<p>Error: No report data available</p>"

        metrics = self._cached_report_data['metrics']
        week_start = self._cached_report_data['week_start']
        week_end = self._cached_report_data['week_end']

        return self._format_html(metrics, week_start, week_end)

    def format_for_json(self) -> str:
        """
        Format report for JSON API consumption.

        Returns:
            Formatted JSON string
        """
        if not self._cached_report_data:
            log_error("No report data available. Call generate_report() first.")
            return json.dumps({"error": "No report data available"})

        metrics = self._cached_report_data['metrics']
        week_start = self._cached_report_data['week_start']
        week_end = self._cached_report_data['week_end']

        return self._format_json(metrics, week_start, week_end)

    def get_insights(self) -> List[str]:
        """
        Get actionable insights from the generated report.

        Returns:
            List of insight strings
        """
        if not self._cached_report_data:
            log_error("No report data available. Call generate_report() first.")
            return []

        metrics = self._cached_report_data['metrics']
        return self._generate_insights(metrics)


def generate_weekly_report(
    supabase_client,
    week_start: Optional[datetime] = None,
    week_end: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Convenience function to generate a weekly report.

    Args:
        supabase_client: Supabase client instance
        week_start: Start date for the report period (defaults to 7 days ago)
        week_end: End date for the report period (defaults to now)

    Returns:
        Dict containing report data and metrics
    """
    generator = WeeklyReportGenerator(supabase_client)
    return generator.generate_report(week_start=week_start, week_end=week_end)


def run_weekly_report(supabase_client) -> Dict[str, Any]:
    """
    Scheduled job function to generate and send weekly report via WhatsApp.

    This function should be called by a scheduler (e.g., cron job, APScheduler)
    to automatically generate and send weekly reports.

    Args:
        supabase_client: Supabase client instance

    Returns:
        Dict containing:
            - success: bool
            - report_generated: bool
            - whatsapp_sent: bool
            - message_id: str (if sent successfully)
            - error: str (if failed)
    """
    try:
        log_info("Starting scheduled weekly report generation")

        # Generate the weekly report
        generator = WeeklyReportGenerator(supabase_client)
        result = generator.generate_report()

        if not result.get('success'):
            error_msg = result.get('error', 'Unknown error generating report')
            log_error(f"Failed to generate weekly report: {error_msg}")
            return {
                'success': False,
                'report_generated': False,
                'whatsapp_sent': False,
                'error': error_msg
            }

        log_info("Weekly report generated successfully")

        # Format for WhatsApp
        whatsapp_message = generator.format_for_whatsapp()

        if not whatsapp_message or whatsapp_message.startswith("Error:"):
            log_error("Failed to format report for WhatsApp")
            return {
                'success': False,
                'report_generated': True,
                'whatsapp_sent': False,
                'error': 'Failed to format WhatsApp message'
            }

        # Send via WhatsApp
        notifier = WhatsAppNotifier()
        send_result = notifier.send_weekly_report(whatsapp_message)

        if send_result.get('success'):
            log_info(f"Weekly report sent successfully via WhatsApp - Message ID: {send_result.get('message_id')}")
            return {
                'success': True,
                'report_generated': True,
                'whatsapp_sent': True,
                'message_id': send_result.get('message_id'),
                'period': result.get('period', {})
            }
        else:
            error_msg = send_result.get('error', 'Unknown error sending WhatsApp message')
            log_error(f"Failed to send weekly report via WhatsApp: {error_msg}")
            return {
                'success': False,
                'report_generated': True,
                'whatsapp_sent': False,
                'error': error_msg
            }

    except Exception as e:
        log_error(f"Unexpected error in run_weekly_report: {str(e)}")
        return {
            'success': False,
            'report_generated': False,
            'whatsapp_sent': False,
            'error': str(e)
        }
