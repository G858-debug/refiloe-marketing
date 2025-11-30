"""Avatar analytics utilities for performance tracking and reporting.

This module centralises avatar performance tracking, A/B experimentation
workflows, and weekly reporting with lightweight visualisation support.
"""

from __future__ import annotations

import os
import random
import re
import uuid
import base64
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import pytz
import yaml

from utils.logger import log_debug, log_error, log_info, log_warning


DateRange = Union[str, Tuple[datetime, datetime], List[datetime]]


@dataclass
class AvatarSelection:
    """Represents an avatar choice for an A/B test iteration."""

    avatar_id: str
    avatar_name: str
    is_exploration: bool
    candidate_pool: List[Dict[str, Any]]
    strategy: str


class AvatarAnalytics:
    """Facilitates avatar performance tracking and experimentation."""

    TABLE_NAME = "avatar_performance"
    AB_TEST_TABLE = "avatar_ab_test_results"

    def __init__(
        self,
        supabase_client: Any,
        config_path: Union[str, Path] = "social_media/avatar_config.yaml",
        db_conn_string: Optional[str] = None,
    ) -> None:
        self.db = supabase_client
        self.config_path = Path(config_path)
        self.sa_tz = pytz.timezone("Africa/Johannesburg")
        self.db_conn_string = (
            db_conn_string
            or os.getenv("SUPABASE_DB_URL")
            or os.getenv("DATABASE_URL")
        )
        self.avatar_name_map = self._load_avatar_metadata(self.config_path)

        self._ensure_tables()

    # ------------------------------------------------------------------
    # Public API - Core tracking methods
    # ------------------------------------------------------------------
    def record_avatar_use(
        self,
        avatar_id: str,
        content_id: Union[str, uuid.UUID],
        content_type: str,
        avatar_name: Optional[str] = None,
        performance_metrics: Optional[Dict[str, Any]] = None,
        ab_test_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Persist an avatar usage record.

        Args:
            avatar_id: Unique identifier for the avatar asset.
            content_id: Content UUID linked to this avatar usage.
            content_type: Category of content (e.g., "educational").
            avatar_name: Optional human-readable label for the avatar.
            performance_metrics: Optional metrics captured post-publication.
            ab_test_context: Optional metadata when captured via A/B testing.

        Returns:
            The UUID of the stored performance record, or None on failure.
        """

        if not self.db:
            log_warning("Supabase client is not configured; cannot record avatar usage.")
            return None

        metrics = performance_metrics.copy() if performance_metrics else {}

        views = int(metrics.get("views", 0) or 0)
        likes = int(metrics.get("likes", 0) or 0)
        comments = int(metrics.get("comments", 0) or 0)
        shares = int(metrics.get("shares", 0) or 0)
        reach = int(metrics.get("reach", 0) or 0)

        engagement_rate = metrics.get("engagement_rate")
        if engagement_rate is None:
            engagement_rate = self._calculate_engagement_rate(
                likes=likes,
                comments=comments,
                shares=shares,
                denominator=reach or views,
            )

        record_id = str(uuid.uuid4())
        resolved_name = self._resolve_avatar_name(avatar_id, avatar_name)

        payload = {
            "id": record_id,
            "avatar_id": avatar_id,
            "avatar_name": resolved_name,
            "content_id": str(content_id),
            "content_type": content_type,
            "engagement_rate": round(float(engagement_rate or 0), 4),
            "views": views,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "created_at": datetime.now(self.sa_tz).isoformat(),
            "metadata": metrics.get("metadata"),
        }

        try:
            # Insert into database (SupabaseRestClient.insert() already executes and returns ExecuteResult)
            result = self.db.table(self.TABLE_NAME).insert(payload)
            if result.data:
                log_info(
                    f"Recorded avatar performance entry for {avatar_id} on content {content_id}"
                )

                if ab_test_context:
                    self._record_ab_test_result(
                        performance_row=payload,
                        ab_test_context=ab_test_context,
                        metrics=metrics,
                        engagement_rate=engagement_rate,
                    )

                return record_id

            log_error("Failed to persist avatar performance record; Supabase returned no data.")
            return None

        except Exception as exc:  # pylint: disable=broad-except
            log_error(f"Error recording avatar usage: {exc}")
            return None

    def get_avatar_performance_stats(
        self, date_range: Optional[DateRange] = None
    ) -> Dict[str, Any]:
        """Aggregate avatar performance across a date range."""

        if not self.db:
            log_warning("Supabase client missing; returning empty stats.")
            return {}

        start_dt, end_dt = self._normalize_date_range(date_range)

        try:
            query = self.db.table(self.TABLE_NAME).select("*")
            if start_dt:
                query = query.gte("created_at", start_dt.isoformat())
            if end_dt:
                query = query.lte("created_at", end_dt.isoformat())

            response = query.execute()
            records: List[Dict[str, Any]] = response.data or []

        except Exception as exc:  # pylint: disable=broad-except
            log_error(f"Error fetching avatar performance stats: {exc}")
            return {}

        if not records:
            return {
                "period": {
                    "start": start_dt.isoformat() if start_dt else None,
                    "end": end_dt.isoformat() if end_dt else None,
                },
                "total_records": 0,
                "avatars": [],
                "content_types": [],
                "raw": [],
            }

        avatar_totals: Dict[str, Dict[str, Any]] = {}
        content_totals: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "content_type": "",
                "usage_count": 0,
                "total_views": 0,
                "total_likes": 0,
                "total_comments": 0,
                "total_shares": 0,
                "engagement_rates": [],
                "avatars": defaultdict(
                    lambda: {
                        "avatar_id": "",
                        "avatar_name": "",
                        "usage_count": 0,
                        "avg_engagement_rate": 0.0,
                    }
                ),
            }
        )

        overall_totals = {
            "usage_count": 0,
            "total_views": 0,
            "total_likes": 0,
            "total_comments": 0,
            "total_shares": 0,
            "engagement_rates": [],
        }

        for row in records:
            avatar_id = row.get("avatar_id")
            avatar_name = row.get("avatar_name") or self._resolve_avatar_name(avatar_id)
            content_type = row.get("content_type", "unknown")
            engagement_rate = float(row.get("engagement_rate") or 0.0)
            views = int(row.get("views") or 0)
            likes = int(row.get("likes") or 0)
            comments = int(row.get("comments") or 0)
            shares = int(row.get("shares") or 0)

            overall_totals["usage_count"] += 1
            overall_totals["total_views"] += views
            overall_totals["total_likes"] += likes
            overall_totals["total_comments"] += comments
            overall_totals["total_shares"] += shares
            overall_totals["engagement_rates"].append(engagement_rate)

            avatar_entry = avatar_totals.setdefault(
                avatar_id,
                {
                    "avatar_id": avatar_id,
                    "avatar_name": avatar_name,
                    "usage_count": 0,
                    "total_views": 0,
                    "total_likes": 0,
                    "total_comments": 0,
                    "total_shares": 0,
                    "engagement_rates": [],
                    "content_types": set(),
                },
            )

            avatar_entry["usage_count"] += 1
            avatar_entry["total_views"] += views
            avatar_entry["total_likes"] += likes
            avatar_entry["total_comments"] += comments
            avatar_entry["total_shares"] += shares
            avatar_entry["engagement_rates"].append(engagement_rate)
            avatar_entry.setdefault("content_types", set()).add(content_type)

            content_entry = content_totals[content_type]
            content_entry["content_type"] = content_type
            content_entry["usage_count"] += 1
            content_entry["total_views"] += views
            content_entry["total_likes"] += likes
            content_entry["total_comments"] += comments
            content_entry["total_shares"] += shares
            content_entry["engagement_rates"].append(engagement_rate)

            avatar_breakdown = content_entry["avatars"][avatar_id]
            avatar_breakdown["avatar_id"] = avatar_id
            avatar_breakdown["avatar_name"] = avatar_name
            avatar_breakdown["usage_count"] += 1
            current_avg = avatar_breakdown["avg_engagement_rate"]
            avatar_breakdown["avg_engagement_rate"] = self._rolling_average(
                current_avg, engagement_rate, avatar_breakdown["usage_count"]
            )

        avatars_summary = self._summarise_avatar_totals(avatar_totals.values())
        content_summary = self._summarise_content_totals(content_totals)

        return {
            "period": {
                "start": start_dt.isoformat() if start_dt else None,
                "end": end_dt.isoformat() if end_dt else None,
            },
            "total_records": len(records),
            "overall": self._finalise_overall_totals(overall_totals),
            "avatars": avatars_summary,
            "content_types": content_summary,
            "raw": records,
        }

    def get_best_performing_avatar(
        self, content_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Return the best performing avatar, optionally filtered by content type."""

        stats = self.get_avatar_performance_stats("30d")
        avatars = stats.get("avatars", [])
        if not avatars:
            return None

        if content_type:
            filtered = [
                entry
                for entry in avatars
                if content_type in entry.get("top_content_types", [])
            ]
            if filtered:
                return filtered[0]

        return avatars[0]

    def get_avatar_usage_distribution(self) -> Dict[str, Any]:
        """Return usage distribution data suitable for charting."""

        stats = self.get_avatar_performance_stats("30d")
        avatars = stats.get("avatars", [])
        content_types = stats.get("content_types", [])

        distribution = {
            "by_avatar": [
                {
                    "avatar_id": avatar["avatar_id"],
                    "avatar_name": avatar["avatar_name"],
                    "usage_count": avatar["usage_count"],
                    "total_views": avatar["total_views"],
                    "avg_engagement_rate": avatar["avg_engagement_rate"],
                }
                for avatar in avatars
            ],
            "by_content_type": [
                {
                    "content_type": content["content_type"],
                    "usage_count": content["usage_count"],
                    "total_views": content["total_views"],
                    "avg_engagement_rate": content["avg_engagement_rate"],
                }
                for content in content_types
            ],
        }

        log_debug(
            f"Generated avatar usage distribution payload: {distribution}"
        )
        return distribution

    # ------------------------------------------------------------------
    # Public API - A/B testing utilities
    # ------------------------------------------------------------------
    def select_avatar_for_ab_test(
        self, content_type: Optional[str] = None
    ) -> Optional[AvatarSelection]:
        """Select an avatar, exploring top performers 20% of the time."""

        stats = self.get_avatar_performance_stats("30d")
        avatars = stats.get("avatars", [])
        if not avatars:
            return None

        if content_type:
            avatars = [
                avatar
                for avatar in avatars
                if content_type in avatar.get("top_content_types", [])
            ] or avatars

        top_candidates = avatars[:2] if len(avatars) >= 2 else avatars[:1]
        if not top_candidates:
            return None

        explore = random.random() <= 0.2 and len(top_candidates) == 2
        selected = random.choice(top_candidates) if explore else top_candidates[0]

        selection = AvatarSelection(
            avatar_id=selected["avatar_id"],
            avatar_name=selected["avatar_name"],
            is_exploration=explore,
            candidate_pool=top_candidates,
            strategy="explore" if explore else "exploit",
        )

        log_info(
            f"Selected avatar {selection.avatar_id} ({selection.strategy} strategy) for content type {content_type or 'any'}"
        )

        return selection

    def generate_recommendations(
        self,
        content_type: Optional[str] = None,
        stats: Optional[Dict[str, Any]] = None,
        ab_tests: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Create actionable recommendations based on recent performance."""

        stats = stats or self.get_avatar_performance_stats("30d")
        avatars = stats.get("avatars", [])
        content_summary = stats.get("content_types", [])

        if ab_tests is None:
            ab_tests = self._fetch_ab_test_results(days=30, content_type=content_type)

        recommendations: List[str] = []

        if avatars:
            top_avatar = avatars[0]
            recommendations.append(
                (
                    f"Prioritise `{top_avatar['avatar_name']}` (ID: {top_avatar['avatar_id']}) "
                    f"? averaging {top_avatar['avg_engagement_rate']:.2f}% engagement across "
                    f"{top_avatar['usage_count']} uses."
                )
            )

        if content_summary:
            weak_content = min(
                content_summary,
                key=lambda entry: entry.get("avg_engagement_rate", 0.0),
            )
            recommendations.append(
                (
                    f"Consider avatar experiments for `{weak_content['content_type']}` "
                    f"content; engagement averages {weak_content['avg_engagement_rate']:.2f}% "
                    "which lags other categories."
                )
            )

        if ab_tests:
            summary = self._summarise_ab_tests(ab_tests)
            exploration_rate = summary.get("exploration_rate", 0.0) * 100
            dominant_avatar = summary.get("top_winner")
            if dominant_avatar:
                recommendations.append(
                    (
                        f"A/B testing favours `{dominant_avatar['avatar_name']}` with "
                        f"a win rate of {dominant_avatar['win_rate']:.1f}%. Keep this avatar as "
                        "the control in upcoming experiments."
                    )
                )
            recommendations.append(
                (
                    f"Maintain an exploration cadence around {exploration_rate:.1f}% to "
                    "continue validating challenger avatars."
                )
            )

        if not recommendations:
            recommendations.append(
                "Collect more avatar performance data to generate targeted recommendations."
            )

        return recommendations

    def generate_avatar_report(self) -> Dict[str, Any]:
        """Create a weekly avatar performance report with visualisations."""

        end_dt = datetime.now(self.sa_tz)
        start_dt = end_dt - timedelta(days=7)

        stats = self.get_avatar_performance_stats((start_dt, end_dt))
        ab_tests = self._fetch_ab_test_results(days=7)

        most_used = stats.get("avatars", [])[:5]
        best_by_content = stats.get("content_types", [])

        report = {
            "generated_at": end_dt.isoformat(),
            "period": {
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
            },
            "most_used_avatars": most_used,
            "best_performing_by_content_type": best_by_content,
            "recommendations": self.generate_recommendations(
                stats=stats, ab_tests=ab_tests
            ),
            "ab_test_summary": self._summarise_ab_tests(ab_tests),
            "visualizations": self._build_visualizations(stats),
            "totals": stats.get("overall", {}),
        }

        log_info(
            f"Generated avatar report covering {report['period']['start']} to {report['period']['end']}"
        )

        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_avatar_metadata(self, path: Path) -> Dict[str, str]:
        if not path.exists():
            log_warning(f"Avatar config file not found at {path}; using defaults.")
            return {}

        try:
            with path.open("r", encoding="utf-8") as descriptor:
                config = yaml.safe_load(descriptor) or {}
        except Exception as exc:  # pylint: disable=broad-except
            log_error(f"Failed to load avatar config: {exc}")
            return {}

        name_map: Dict[str, str] = {}

        platform_settings = config.get("platform_settings", {}) or {}
        for name, settings in platform_settings.items():
            avatar_id = settings.get("avatar_id") if isinstance(settings, dict) else None
            if avatar_id:
                name_map[avatar_id] = self._slugify(name)

        fallback = (
            config.get("fallback_options", {})
            .get("secondary_avatars", [])
        ) or []
        for entry in fallback:
            avatar_id = entry.get("avatar_id") if isinstance(entry, dict) else None
            differentiator = entry.get("differentiator", "") if isinstance(entry, dict) else ""
            if avatar_id:
                label = differentiator or entry.get("platform", "secondary")
                name_map[avatar_id] = self._slugify(label)

        return name_map

    def _resolve_avatar_name(self, avatar_id: str, avatar_name: Optional[str] = None) -> str:
        if avatar_name:
            return self._slugify(avatar_name)

        if avatar_id in self.avatar_name_map:
            return self.avatar_name_map[avatar_id]

        return self._slugify(avatar_id)

    def _slugify(self, text: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_")
        return cleaned.lower() or "avatar"

    def _ensure_tables(self) -> None:
        if not self.db_conn_string:
            log_warning(
                "No database connection string found; skipping avatar table provisioning.")
            return

        try:
            import psycopg2  # type: ignore

            with psycopg2.connect(self.db_conn_string, sslmode="require") as conn:
                conn.autocommit = True

                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                            id UUID PRIMARY KEY,
                            avatar_id TEXT NOT NULL,
                            avatar_name TEXT NOT NULL,
                            content_id UUID,
                            content_type TEXT,
                            engagement_rate DOUBLE PRECISION,
                            views INTEGER DEFAULT 0,
                            likes INTEGER DEFAULT 0,
                            comments INTEGER DEFAULT 0,
                            shares INTEGER DEFAULT 0,
                            metadata JSONB,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
                        );
                        """
                    )

                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_avatar_id ON {self.TABLE_NAME}(avatar_id);"
                    )
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_content_type ON {self.TABLE_NAME}(content_type);"
                    )
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.TABLE_NAME}_created_at ON {self.TABLE_NAME}(created_at DESC);"
                    )

                    cursor.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {self.AB_TEST_TABLE} (
                            id UUID PRIMARY KEY,
                            control_avatar_id TEXT,
                            control_avatar_name TEXT,
                            challenger_avatar_id TEXT,
                            challenger_avatar_name TEXT,
                            selected_avatar_id TEXT,
                            selected_avatar_name TEXT,
                            content_id UUID,
                            content_type TEXT,
                            strategy TEXT,
                            is_exploration BOOLEAN DEFAULT FALSE,
                            engagement_rate DOUBLE PRECISION,
                            views INTEGER DEFAULT 0,
                            likes INTEGER DEFAULT 0,
                            comments INTEGER DEFAULT 0,
                            shares INTEGER DEFAULT 0,
                            outcome TEXT,
                            metadata JSONB,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc', now())
                        );
                        """
                    )

                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.AB_TEST_TABLE}_content_type ON {self.AB_TEST_TABLE}(content_type);"
                    )
                    cursor.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{self.AB_TEST_TABLE}_created_at ON {self.AB_TEST_TABLE}(created_at DESC);"
                    )

            log_info("Ensured avatar analytics tables exist.")

        except ImportError:
            log_warning(
                "psycopg2 is not available; cannot auto-provision avatar analytics tables."
            )
        except Exception as exc:  # pylint: disable=broad-except
            log_error(f"Failed to provision avatar analytics tables: {exc}")

    def _calculate_engagement_rate(
        self,
        likes: int,
        comments: int,
        shares: int,
        denominator: int,
    ) -> float:
        if denominator <= 0:
            return 0.0
        engagement = likes + comments + shares
        return round((engagement / denominator) * 100, 4)

    def _rolling_average(
        self, current_average: float, new_value: float, total_samples: int
    ) -> float:
        if total_samples <= 0:
            return 0.0
        if total_samples == 1:
            return new_value
        return ((current_average * (total_samples - 1)) + new_value) / total_samples

    def _summarise_avatar_totals(
        self, avatar_entries: Iterable[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        summary: List[Dict[str, Any]] = []
        for entry in avatar_entries:
            engagement_rates = entry.get("engagement_rates", [])
            avg_engagement = (
                sum(engagement_rates) / len(engagement_rates)
                if engagement_rates
                else 0.0
            )
            summary.append(
                {
                    "avatar_id": entry["avatar_id"],
                    "avatar_name": entry["avatar_name"],
                    "usage_count": entry["usage_count"],
                    "total_views": entry["total_views"],
                    "total_likes": entry["total_likes"],
                    "total_comments": entry["total_comments"],
                    "total_shares": entry["total_shares"],
                    "avg_engagement_rate": round(avg_engagement, 4),
                    "top_content_types": sorted(entry.get("content_types", set())),
                }
            )

        summary.sort(key=lambda item: item.get("avg_engagement_rate", 0.0), reverse=True)
        return summary

    def _summarise_content_totals(
        self, content_totals: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        summary: List[Dict[str, Any]] = []
        for content_type, data in content_totals.items():
            engagement_rates = data.get("engagement_rates", [])
            avg_engagement = (
                sum(engagement_rates) / len(engagement_rates)
                if engagement_rates
                else 0.0
            )

            avatars = list(data.get("avatars", {}).values())
            avatars.sort(key=lambda item: item.get("avg_engagement_rate", 0.0), reverse=True)

            summary.append(
                {
                    "content_type": content_type,
                    "usage_count": data.get("usage_count", 0),
                    "total_views": data.get("total_views", 0),
                    "total_likes": data.get("total_likes", 0),
                    "total_comments": data.get("total_comments", 0),
                    "total_shares": data.get("total_shares", 0),
                    "avg_engagement_rate": round(avg_engagement, 4),
                    "top_avatars": avatars[:3],
                }
            )

        summary.sort(key=lambda item: item.get("avg_engagement_rate", 0.0), reverse=True)
        return summary

    def _finalise_overall_totals(self, totals: Dict[str, Any]) -> Dict[str, Any]:
        engagement_rates = totals.get("engagement_rates", [])
        avg_engagement = (
            sum(engagement_rates) / len(engagement_rates)
            if engagement_rates
            else 0.0
        )
        return {
            "usage_count": totals.get("usage_count", 0),
            "total_views": totals.get("total_views", 0),
            "total_likes": totals.get("total_likes", 0),
            "total_comments": totals.get("total_comments", 0),
            "total_shares": totals.get("total_shares", 0),
            "avg_engagement_rate": round(avg_engagement, 4),
        }

    def _fetch_ab_test_results(
        self, days: int = 30, content_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not self.db:
            return []

        start_dt = datetime.now(self.sa_tz) - timedelta(days=days)

        try:
            query = self.db.table(self.AB_TEST_TABLE).select("*")
            query = query.gte("created_at", start_dt.isoformat())
            if content_type:
                query = query.eq("content_type", content_type)

            result = query.execute()
            return result.data or []

        except Exception as exc:  # pylint: disable=broad-except
            log_error(f"Error fetching avatar A/B test results: {exc}")
            return []

    def _record_ab_test_result(
        self,
        performance_row: Dict[str, Any],
        ab_test_context: Dict[str, Any],
        metrics: Dict[str, Any],
        engagement_rate: float,
    ) -> None:
        if not self.db:
            return

        try:
            payload = {
                "id": str(uuid.uuid4()),
                "control_avatar_id": ab_test_context.get("control_avatar_id"),
                "control_avatar_name": ab_test_context.get("control_avatar_name"),
                "challenger_avatar_id": ab_test_context.get("challenger_avatar_id"),
                "challenger_avatar_name": ab_test_context.get("challenger_avatar_name"),
                "selected_avatar_id": performance_row.get("avatar_id"),
                "selected_avatar_name": performance_row.get("avatar_name"),
                "content_id": performance_row.get("content_id"),
                "content_type": performance_row.get("content_type"),
                "strategy": ab_test_context.get("strategy"),
                "is_exploration": bool(ab_test_context.get("is_exploration", False)),
                "engagement_rate": round(float(engagement_rate or 0), 4),
                "views": int(metrics.get("views", 0) or 0),
                "likes": int(metrics.get("likes", 0) or 0),
                "comments": int(metrics.get("comments", 0) or 0),
                "shares": int(metrics.get("shares", 0) or 0),
                "outcome": ab_test_context.get("outcome"),
                "metadata": ab_test_context.get("metadata"),
                "created_at": datetime.now(self.sa_tz).isoformat(),
            }

            # Insert into database (SupabaseRestClient.insert() already executes and returns ExecuteResult)
            result = self.db.table(self.AB_TEST_TABLE).insert(payload)
            if result.data:
                log_info(
                    f"Stored avatar A/B test result for content {performance_row.get('content_id')}"
                )
            else:
                log_warning("Supabase returned empty response when saving A/B result.")

        except Exception as exc:  # pylint: disable=broad-except
            log_error(f"Failed to save avatar A/B test result: {exc}")

    def _summarise_ab_tests(self, ab_tests: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not ab_tests:
            return {
                "total_runs": 0,
                "exploration_rate": 0.0,
                "top_winner": None,
                "average_engagement": 0.0,
            }

        total_runs = len(ab_tests)
        exploration_runs = sum(1 for entry in ab_tests if entry.get("is_exploration"))
        engagements = [
            float(entry.get("engagement_rate") or 0.0) for entry in ab_tests
        ]

        win_counts: Dict[str, Dict[str, Any]] = {}
        for entry in ab_tests:
            avatar_id = entry.get("selected_avatar_id")
            avatar_name = entry.get("selected_avatar_name") or avatar_id
            if not avatar_id:
                continue

            win_entry = win_counts.setdefault(
                avatar_id,
                {"avatar_id": avatar_id, "avatar_name": avatar_name, "wins": 0},
            )
            win_entry["wins"] += 1

        for win_entry in win_counts.values():
            win_entry["win_rate"] = (win_entry["wins"] / total_runs) * 100

        top_winner = (
            max(win_counts.values(), key=lambda entry: entry.get("win_rate", 0))
            if win_counts
            else None
        )

        return {
            "total_runs": total_runs,
            "exploration_rate": exploration_runs / total_runs if total_runs else 0.0,
            "average_engagement": sum(engagements) / len(engagements)
            if engagements
            else 0.0,
            "top_winner": top_winner,
        }

    def _build_visualizations(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        avatars = stats.get("avatars", [])
        content_types = stats.get("content_types", [])

        chart_data = {
            "avatar_usage": {
                "labels": [avatar["avatar_name"] for avatar in avatars],
                "values": [avatar["usage_count"] for avatar in avatars],
            },
            "avatar_engagement": {
                "labels": [avatar["avatar_name"] for avatar in avatars],
                "values": [avatar["avg_engagement_rate"] for avatar in avatars],
            },
            "content_type_engagement": {
                "labels": [c["content_type"] for c in content_types],
                "values": [c["avg_engagement_rate"] for c in content_types],
            },
        }

        visualizations = {"chart_data": chart_data}

        try:
            import matplotlib.pyplot as plt  # type: ignore

            plt.switch_backend("Agg")

            if avatars:
                fig, ax = plt.subplots(figsize=(8, 4))
                ax.bar(
                    chart_data["avatar_usage"]["labels"],
                    chart_data["avatar_usage"]["values"],
                    color="#4B8BBE",
                )
                ax.set_title("Avatar Usage (Last Period)")
                ax.set_ylabel("Usage Count")
                ax.set_xlabel("Avatar")
                ax.tick_params(axis="x", rotation=45)
                usage_buffer = BytesIO()
                fig.tight_layout()
                fig.savefig(usage_buffer, format="png")
                plt.close(fig)
                usage_buffer.seek(0)
                visualizations["avatar_usage_chart"] = base64.b64encode(
                    usage_buffer.read()
                ).decode("utf-8")

            if content_types:
                fig, ax = plt.subplots(figsize=(8, 4))
                ax.bar(
                    chart_data["content_type_engagement"]["labels"],
                    chart_data["content_type_engagement"]["values"],
                    color="#306998",
                )
                ax.set_title("Engagement by Content Type")
                ax.set_ylabel("Avg Engagement Rate (%)")
                ax.set_xlabel("Content Type")
                ax.tick_params(axis="x", rotation=45)
                engagement_buffer = BytesIO()
                fig.tight_layout()
                fig.savefig(engagement_buffer, format="png")
                plt.close(fig)
                engagement_buffer.seek(0)
                visualizations["content_type_engagement_chart"] = base64.b64encode(
                    engagement_buffer.read()
                ).decode("utf-8")

        except ImportError:
            log_warning(
                "matplotlib not available; returning structured chart data without rendered images."
            )
        except Exception as exc:  # pylint: disable=broad-except
            log_error(f"Failed to generate avatar visualisations: {exc}")

        return visualizations

    def _normalize_date_range(
        self, date_range: Optional[DateRange]
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        end_dt = datetime.now(self.sa_tz)
        start_dt = end_dt - timedelta(days=30)

        if date_range is None:
            return start_dt, end_dt

        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_dt = self._ensure_datetime(date_range[0]) or start_dt
            end_dt = self._ensure_datetime(date_range[1]) or end_dt
            return start_dt, end_dt

        if isinstance(date_range, str):
            raw_value = date_range.strip()
            key = raw_value.lower()
            presets = {
                "7d": 7,
                "week": 7,
                "last_week": 7,
                "14d": 14,
                "30d": 30,
                "last_30_days": 30,
                "quarter": 90,
                "6m": 180,
                "year": 365,
            }
            if key in presets:
                days = presets[key]
                return end_dt - timedelta(days=days), end_dt

            parts: List[str] = []
            if re.search(r"\s+to\s+", raw_value, flags=re.IGNORECASE):
                parts = re.split(r"\s+to\s+", raw_value, maxsplit=1, flags=re.IGNORECASE)
            elif "/" in raw_value:
                parts = raw_value.split("/")
            elif "," in raw_value:
                parts = raw_value.split(",")

            if len(parts) == 2:
                start = self._ensure_datetime(parts[0]) or start_dt
                end = self._ensure_datetime(parts[1]) or end_dt
                return start, end

        return start_dt, end_dt

    def _ensure_datetime(self, value: Union[datetime, str, None]) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return self._ensure_timezone(value)

        try:
            parsed = datetime.fromisoformat(str(value))
            return self._ensure_timezone(parsed)
        except ValueError:
            return None

    def _ensure_timezone(self, dt_value: datetime) -> datetime:
        if dt_value.tzinfo is None:
            return self.sa_tz.localize(dt_value)
        return dt_value.astimezone(self.sa_tz)


__all__ = ["AvatarAnalytics", "AvatarSelection"]
