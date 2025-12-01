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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pytz

from utils.logger import log_debug, log_error, log_info, log_warning


SA_TIMEZONE = pytz.timezone("Africa/Johannesburg")


class WeeklyReportGenerator:
    """Generates comprehensive weekly performance reports for social media content."""

    def __init__(self, supabase_client):
        """
        Initialize the weekly report generator.

        Args:
            supabase_client: Supabase client instance for database queries
        """
        self.db = supabase_client
        self.sa_tz = SA_TIMEZONE

    def generate_report(
        self,
        end_date: Optional[datetime] = None,
        output_format: str = "text"
    ) -> Dict[str, Any]:
        """
        Generate a weekly report for the past 7 days.

        Args:
            end_date: End date for the report period (defaults to now)
            output_format: Output format - 'text', 'html', or 'json'

        Returns:
            Dict containing:
                - success: bool
                - report: str (formatted report based on output_format)
                - data: dict (raw data used to generate the report)
                - error: str (if success is False)
        """
        try:
            # Determine date range
            if end_date is None:
                end_date = datetime.now(self.sa_tz)
            else:
                # Ensure end_date is timezone-aware
                if end_date.tzinfo is None:
                    end_date = self.sa_tz.localize(end_date)
                else:
                    end_date = end_date.astimezone(self.sa_tz)

            start_date = end_date - timedelta(days=7)

            log_info(f"Generating weekly report from {start_date.date()} to {end_date.date()}")

            # Collect metrics from all sources
            metrics = self._collect_metrics(start_date, end_date)

            # Generate formatted report
            if output_format == "json":
                report = self._format_json(metrics, start_date, end_date)
            elif output_format == "html":
                report = self._format_html(metrics, start_date, end_date)
            else:  # Default to text
                report = self._format_text(metrics, start_date, end_date)

            log_info("Weekly report generated successfully")

            return {
                "success": True,
                "report": report,
                "data": metrics,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }

        except Exception as e:
            log_error(f"Error generating weekly report: {e}")
            return {
                "success": False,
                "report": "",
                "data": {},
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
            # Query published posts in the date range
            result = self.db.table('social_posts').select(
                'id, post_type, caption_text, published_time, status, platform'
            ).eq(
                'status', 'published'
            ).gte(
                'published_time', start_date.isoformat()
            ).lte(
                'published_time', end_date.isoformat()
            ).execute()

            posts = result.data if result.data else []

            log_info(f"Found {len(posts)} published posts in the reporting period")

            return {
                "total_posts": len(posts),
                "posts_by_type": self._group_by_field(posts, 'post_type'),
                "posts_by_platform": self._group_by_field(posts, 'platform'),
                "posts": posts
            }

        except Exception as e:
            log_error(f"Error collecting post metrics: {e}")
            return {
                "total_posts": 0,
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
            posts_result = self.db.table('social_posts').select(
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
            analytics_result = self.db.table('social_analytics').select(
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
            result = self.db.table('generated_videos').select(
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
            video_posts_result = self.db.table('social_posts').select(
                'completion_rate, avg_watch_time, video_url'
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

            return {
                "videos_generated": len(videos),
                "videos_completed": len(completed_videos),
                "videos_published": len(video_posts),
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

            result = self.db.table('social_posts').select(
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
            result = self.db.table('social_posts').select(
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

        return insights


def generate_weekly_report(
    supabase_client,
    end_date: Optional[datetime] = None,
    output_format: str = "text"
) -> Dict[str, Any]:
    """
    Convenience function to generate a weekly report.

    Args:
        supabase_client: Supabase client instance
        end_date: End date for the report period (defaults to now)
        output_format: Output format - 'text', 'html', or 'json'

    Returns:
        Dict containing report data and formatted output
    """
    generator = WeeklyReportGenerator(supabase_client)
    return generator.generate_report(end_date=end_date, output_format=output_format)
