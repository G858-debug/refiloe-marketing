"""Content Pipeline Health Monitor

This module provides health monitoring and alerting for the content pipeline,
tracking post statuses, scheduled content, and video generation metrics.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pytz

from utils.logger import log_error, log_info, log_warning

try:  # Package-local import
    from .database import SocialMediaDatabase
except ImportError:  # Fallback when modules are at project root
    from database import SocialMediaDatabase


class ContentPipelineMonitor:
    """Monitor and alert on content pipeline health metrics."""

    # Alert thresholds
    MIN_DAYS_SCHEDULED = 3
    MAX_PENDING_APPROVAL = 10
    VIDEO_FAILURE_THRESHOLD = 0.20  # 20%

    def __init__(self, supabase_client: Any):
        """Initialize the content pipeline monitor.

        Args:
            supabase_client: Supabase client instance
        """
        self.db = SocialMediaDatabase(supabase_client)
        self.supabase = supabase_client
        self.sa_tz = pytz.timezone('Africa/Johannesburg')

    # ============================================
    # CONTENT PIPELINE HEALTH CHECKS
    # ============================================

    def check_pipeline_health(self) -> Dict[str, Any]:
        """Check overall content pipeline health.

        Returns:
            Dict containing:
                - pending_approval_count: Number of posts awaiting approval
                - scheduled_count: Number of posts scheduled for next 7 days
                - content_gaps: List of dates with insufficient content
                - video_failure_rate: Percentage of failed video generations
                - status: Overall pipeline status (healthy/warning/critical)
                - alerts: List of alert messages
        """
        log_info("Checking content pipeline health...")

        # Count pending approval posts
        pending_count = self._count_pending_approval_posts()

        # Count scheduled posts for next 7 days
        scheduled_count, daily_schedule = self._count_scheduled_posts_next_7_days()

        # Identify content gaps
        content_gaps = self._identify_content_gaps(daily_schedule)

        # Calculate video generation failure rate
        video_failure_rate = self._calculate_video_failure_rate()

        # Generate alerts based on thresholds
        alerts = self._generate_alerts(
            pending_count=pending_count,
            scheduled_count=scheduled_count,
            content_gaps=content_gaps,
            video_failure_rate=video_failure_rate
        )

        # Determine overall status
        status = self._determine_pipeline_status(alerts)

        health_report = {
            'pending_approval_count': pending_count,
            'scheduled_count': scheduled_count,
            'scheduled_days_coverage': len([d for d in daily_schedule.values() if d > 0]),
            'content_gaps': content_gaps,
            'video_failure_rate': video_failure_rate,
            'status': status,
            'alerts': alerts,
            'checked_at': datetime.now(self.sa_tz).isoformat()
        }

        log_info(f"Pipeline health check complete: {status} status with {len(alerts)} alerts")
        return health_report

    def _count_pending_approval_posts(self) -> int:
        """Count posts pending approval.

        Returns:
            Number of posts with status 'pending_approval'
        """
        try:
            result = self.supabase.table('social_posts').select(
                'id', count='exact'
            ).eq('status', 'pending_approval').execute()

            count = result.count if hasattr(result, 'count') else len(result.data or [])
            log_info(f"Found {count} posts pending approval")
            return count
        except Exception as e:
            log_error(f"Error counting pending approval posts: {str(e)}")
            return 0

    def _count_scheduled_posts_next_7_days(self) -> Tuple[int, Dict[str, int]]:
        """Count scheduled posts for the next 7 days.

        Returns:
            Tuple of (total_count, daily_schedule_dict)
            where daily_schedule_dict maps date strings to post counts
        """
        try:
            now = datetime.now(self.sa_tz)
            start_time = now
            end_time = now + timedelta(days=7)

            result = self.supabase.table('social_posts').select('*').eq(
                'status', 'scheduled'
            ).gte(
                'scheduled_time', start_time.isoformat()
            ).lte(
                'scheduled_time', end_time.isoformat()
            ).order('scheduled_time').execute()

            posts = result.data if result.data else []

            # Group by date
            daily_schedule = {}
            for i in range(7):
                date_key = (start_time + timedelta(days=i)).strftime('%Y-%m-%d')
                daily_schedule[date_key] = 0

            for post in posts:
                scheduled_time_str = post.get('scheduled_time')
                if scheduled_time_str:
                    try:
                        # Parse ISO format datetime
                        scheduled_dt = datetime.fromisoformat(
                            scheduled_time_str.replace('Z', '+00:00')
                        )
                        if scheduled_dt.tzinfo is None:
                            scheduled_dt = self.sa_tz.localize(scheduled_dt)
                        else:
                            scheduled_dt = scheduled_dt.astimezone(self.sa_tz)

                        date_key = scheduled_dt.strftime('%Y-%m-%d')
                        if date_key in daily_schedule:
                            daily_schedule[date_key] += 1
                    except (ValueError, AttributeError) as e:
                        log_warning(f"Could not parse scheduled_time: {scheduled_time_str}: {e}")

            total_count = len(posts)
            log_info(f"Found {total_count} scheduled posts in next 7 days")
            return total_count, daily_schedule

        except Exception as e:
            log_error(f"Error counting scheduled posts: {str(e)}")
            return 0, {}

    def _identify_content_gaps(self, daily_schedule: Dict[str, int]) -> List[str]:
        """Identify dates with no or insufficient scheduled content.

        Args:
            daily_schedule: Dictionary mapping date strings to post counts

        Returns:
            List of date strings with content gaps
        """
        content_gaps = []

        for date_str, count in daily_schedule.items():
            if count == 0:
                content_gaps.append(date_str)

        if content_gaps:
            log_warning(f"Content gaps identified for {len(content_gaps)} days: {content_gaps}")

        return content_gaps

    def _calculate_video_failure_rate(self, days: int = 7) -> float:
        """Calculate the video generation failure rate.

        Args:
            days: Number of days to look back for video generation attempts

        Returns:
            Failure rate as a percentage (0-100)
        """
        try:
            cutoff_date = datetime.now(self.sa_tz) - timedelta(days=days)

            # Count total video posts created in the period
            total_result = self.supabase.table('social_posts').select(
                'id', count='exact'
            ).eq('post_type', 'video').gte(
                'created_at', cutoff_date.isoformat()
            ).execute()

            total_videos = total_result.count if hasattr(total_result, 'count') else len(total_result.data or [])

            if total_videos == 0:
                return 0.0

            # Count failed video posts (status = 'failed' or video_url is null)
            # Failed posts might have status 'failed' or be in draft with no video_url
            failed_result = self.supabase.table('social_posts').select(
                'id', count='exact'
            ).eq('post_type', 'video').gte(
                'created_at', cutoff_date.isoformat()
            ).is_('video_url', 'null').execute()

            failed_videos = failed_result.count if hasattr(failed_result, 'count') else len(failed_result.data or [])

            # Also check for explicitly failed status
            failed_status_result = self.supabase.table('social_posts').select(
                'id', count='exact'
            ).eq('post_type', 'video').eq('status', 'failed').gte(
                'created_at', cutoff_date.isoformat()
            ).execute()

            failed_status_count = failed_status_result.count if hasattr(failed_status_result, 'count') else len(failed_status_result.data or [])

            # Total failures is the sum, but avoid double counting
            # by taking the max of the two (since a failed status post might also have null video_url)
            total_failures = max(failed_videos, failed_status_count)

            failure_rate = (total_failures / total_videos) * 100

            log_info(f"Video failure rate: {failure_rate:.2f}% ({total_failures}/{total_videos} in last {days} days)")
            return round(failure_rate, 2)

        except Exception as e:
            log_error(f"Error calculating video failure rate: {str(e)}")
            return 0.0

    # ============================================
    # ALERT GENERATION
    # ============================================

    def _generate_alerts(
        self,
        pending_count: int,
        scheduled_count: int,
        content_gaps: List[str],
        video_failure_rate: float
    ) -> List[Dict[str, Any]]:
        """Generate alerts based on pipeline metrics.

        Args:
            pending_count: Number of posts pending approval
            scheduled_count: Number of scheduled posts
            content_gaps: List of dates with content gaps
            video_failure_rate: Video generation failure rate

        Returns:
            List of alert dictionaries with 'severity', 'type', and 'message'
        """
        alerts = []

        # Check scheduled content coverage
        days_with_content = 7 - len(content_gaps)
        if days_with_content < self.MIN_DAYS_SCHEDULED:
            alerts.append({
                'severity': 'critical',
                'type': 'insufficient_scheduled_content',
                'message': f'Only {days_with_content} days of content scheduled (minimum: {self.MIN_DAYS_SCHEDULED} days)',
                'recommended_action': 'Generate and schedule more content immediately'
            })

        # Check pending approval backlog
        if pending_count > self.MAX_PENDING_APPROVAL:
            alerts.append({
                'severity': 'warning',
                'type': 'pending_approval_backlog',
                'message': f'{pending_count} posts pending approval (threshold: {self.MAX_PENDING_APPROVAL})',
                'recommended_action': 'Review and approve or reject pending posts'
            })

        # Check content gaps
        if len(content_gaps) > 0:
            alerts.append({
                'severity': 'warning' if len(content_gaps) <= 2 else 'critical',
                'type': 'content_gaps',
                'message': f'{len(content_gaps)} days with no scheduled content: {", ".join(content_gaps[:3])}{"..." if len(content_gaps) > 3 else ""}',
                'recommended_action': f'Schedule content for dates: {", ".join(content_gaps)}'
            })

        # Check video failure rate
        if video_failure_rate > self.VIDEO_FAILURE_THRESHOLD * 100:
            alerts.append({
                'severity': 'critical',
                'type': 'high_video_failure_rate',
                'message': f'Video generation failure rate at {video_failure_rate}% (threshold: {self.VIDEO_FAILURE_THRESHOLD * 100}%)',
                'recommended_action': 'Investigate HeyGen API issues or configuration problems'
            })

        return alerts

    def _determine_pipeline_status(self, alerts: List[Dict[str, Any]]) -> str:
        """Determine overall pipeline status based on alerts.

        Args:
            alerts: List of alert dictionaries

        Returns:
            Status string: 'healthy', 'warning', or 'critical'
        """
        if not alerts:
            return 'healthy'

        severities = [alert['severity'] for alert in alerts]

        if 'critical' in severities:
            return 'critical'
        elif 'warning' in severities:
            return 'warning'

        return 'healthy'

    # ============================================
    # DETAILED METRICS
    # ============================================

    def get_content_counts_by_status(self) -> Dict[str, int]:
        """Get count of posts grouped by status.

        Returns:
            Dictionary mapping status to count
        """
        try:
            result = self.supabase.table('social_posts').select('status').execute()

            posts = result.data if result.data else []

            status_counts = {}
            for post in posts:
                status = post.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1

            log_info(f"Content counts by status: {status_counts}")
            return status_counts

        except Exception as e:
            log_error(f"Error getting content counts by status: {str(e)}")
            return {}

    def get_next_7_days_coverage(self) -> Dict[str, Any]:
        """Get detailed coverage for the next 7 days.

        Returns:
            Dictionary with daily breakdown of scheduled content
        """
        try:
            _, daily_schedule = self._count_scheduled_posts_next_7_days()

            now = datetime.now(self.sa_tz)
            coverage = {
                'days': [],
                'total_posts': sum(daily_schedule.values()),
                'days_with_content': len([c for c in daily_schedule.values() if c > 0]),
                'days_without_content': len([c for c in daily_schedule.values() if c == 0])
            }

            for i in range(7):
                date_obj = now + timedelta(days=i)
                date_str = date_obj.strftime('%Y-%m-%d')
                day_name = date_obj.strftime('%A')

                coverage['days'].append({
                    'date': date_str,
                    'day_name': day_name,
                    'post_count': daily_schedule.get(date_str, 0),
                    'has_content': daily_schedule.get(date_str, 0) > 0
                })

            return coverage

        except Exception as e:
            log_error(f"Error getting 7-day coverage: {str(e)}")
            return {'days': [], 'total_posts': 0, 'days_with_content': 0, 'days_without_content': 7}

    def get_recommended_actions(self, health_report: Dict[str, Any]) -> List[str]:
        """Generate recommended actions based on health report.

        Args:
            health_report: Health report from check_pipeline_health()

        Returns:
            List of recommended action strings
        """
        actions = []

        # Extract unique recommended actions from alerts
        for alert in health_report.get('alerts', []):
            action = alert.get('recommended_action')
            if action and action not in actions:
                actions.append(action)

        # Add proactive recommendations
        if health_report.get('status') == 'healthy':
            actions.append('Pipeline is healthy. Continue monitoring regularly.')

        if health_report.get('pending_approval_count', 0) > 0:
            if 'Review and approve or reject pending posts' not in actions:
                actions.append(f"Review {health_report['pending_approval_count']} pending post(s)")

        return actions


__all__ = ["ContentPipelineMonitor"]
