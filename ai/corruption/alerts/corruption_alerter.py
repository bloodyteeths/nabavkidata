"""
Corruption Alert Engine

Evaluates tenders against user alert subscriptions and generates alerts.
This is the core engine for the Phase 4.4 real-time corruption alert pipeline.

Usage:
    alerter = CorruptionAlerter()
    # Evaluate a single tender
    alerts = await alerter.evaluate_tender(pool, tender_id)
    # Evaluate all new tenders since last run
    summary = await alerter.evaluate_new_tenders(pool)
    # Get user alerts
    alerts, total = await alerter.get_user_alerts(pool, user_id)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any

from .alert_rules import create_rule, severity_meets_threshold, AVAILABLE_RULES

logger = logging.getLogger(__name__)


class CorruptionAlerter:
    """Evaluates tenders against alert subscriptions and generates alerts."""

    # ------------------------------------------------------------------ #
    # TENDER DATA ENRICHMENT
    # ------------------------------------------------------------------ #

    async def _fetch_tender_data(self, conn, tender_id: str) -> Optional[dict]:
        """Fetch enriched tender data needed for rule evaluation.

        Joins tenders, tender_risk_scores, and corruption_flags to build
        a complete picture of the tender's risk profile.

        Args:
            conn: asyncpg connection.
            tender_id: The tender identifier (e.g., '12345/2025').

        Returns:
            Dict with all fields needed by rule evaluate(), or None if
            the tender does not exist.
        """
        row = await conn.fetchrow("""
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.winner,
                t.actual_value_mkd,
                t.estimated_value_mkd,
                t.publication_date,
                t.status,
                COALESCE(trs.risk_score, 0) AS risk_score,
                COALESCE(trs.risk_level, 'minimal') AS risk_level,
                COALESCE(trs.flag_count, 0) AS flag_count
            FROM tenders t
            LEFT JOIN tender_risk_scores trs ON t.tender_id = trs.tender_id
            WHERE t.tender_id = $1
        """, tender_id)

        if not row:
            return None

        data = dict(row)

        # Fetch individual flag types for this tender
        flag_rows = await conn.fetch("""
            SELECT DISTINCT flag_type
            FROM corruption_flags
            WHERE tender_id = $1 AND false_positive = FALSE
        """, tender_id)
        data['flags'] = [r['flag_type'] for r in flag_rows]

        # Fetch flag details (type, severity, score) for richer evaluation
        detail_rows = await conn.fetch("""
            SELECT flag_type, severity, score
            FROM corruption_flags
            WHERE tender_id = $1 AND false_positive = FALSE
            ORDER BY score DESC
        """, tender_id)
        data['flag_details'] = [dict(r) for r in detail_rows]

        # Compute repeat_win_count: how many times this winner has won
        # from this same institution (including this tender)
        winner = data.get('winner')
        institution = data.get('procuring_entity')
        if winner and institution:
            repeat_count = await conn.fetchval("""
                SELECT COUNT(*)
                FROM tenders
                WHERE winner = $1
                  AND procuring_entity = $2
                  AND status = 'awarded'
            """, winner, institution)
            data['repeat_win_count'] = repeat_count or 0
        else:
            data['repeat_win_count'] = 0

        # Compute risk_trend for the procuring entity or winner
        # Look at the last 10 tenders from the same institution and compute trend
        entity_for_trend = institution or winner
        if entity_for_trend:
            history_rows = await conn.fetch("""
                SELECT trs.risk_score
                FROM tenders t
                JOIN tender_risk_scores trs ON t.tender_id = trs.tender_id
                WHERE t.procuring_entity = $1
                ORDER BY t.publication_date DESC NULLS LAST
                LIMIT 10
            """, entity_for_trend)
            scores = [r['risk_score'] for r in history_rows if r['risk_score'] is not None]
            data['risk_history'] = scores

            if len(scores) >= 3:
                # Compare average of first half vs second half
                mid = len(scores) // 2
                # scores are ordered newest first, so recent = scores[:mid], older = scores[mid:]
                recent_avg = sum(scores[:mid]) / mid if mid > 0 else 0
                older_avg = sum(scores[mid:]) / (len(scores) - mid) if (len(scores) - mid) > 0 else 0

                if recent_avg > older_avg + 5:
                    data['risk_trend'] = 'increasing'
                elif recent_avg < older_avg - 5:
                    data['risk_trend'] = 'decreasing'
                else:
                    data['risk_trend'] = 'stable'
            else:
                data['risk_trend'] = 'stable'
        else:
            data['risk_history'] = []
            data['risk_trend'] = 'stable'

        return data

    # ------------------------------------------------------------------ #
    # SUBSCRIPTION FETCHING
    # ------------------------------------------------------------------ #

    async def _fetch_active_subscriptions(self, conn) -> List[dict]:
        """Fetch all active alert subscriptions.

        Returns:
            List of subscription dicts with subscription_id, user_id,
            rule_type, rule_config, severity_filter.
        """
        rows = await conn.fetch("""
            SELECT
                subscription_id,
                user_id,
                rule_type,
                rule_config,
                severity_filter
            FROM corruption_alert_subscriptions
            WHERE active = TRUE
        """)
        result = []
        for row in rows:
            sub = dict(row)
            # Parse JSONB rule_config
            rc = sub.get('rule_config')
            if isinstance(rc, str):
                try:
                    sub['rule_config'] = json.loads(rc) if rc else {}
                except (json.JSONDecodeError, TypeError):
                    sub['rule_config'] = {}
            elif not isinstance(rc, dict):
                sub['rule_config'] = {}
            result.append(sub)
        return result

    # ------------------------------------------------------------------ #
    # DEDUPLICATION
    # ------------------------------------------------------------------ #

    async def _alert_exists(self, conn, user_id: str, tender_id: str, rule_type: str) -> bool:
        """Check if an alert already exists for this user+tender+rule combination.

        Prevents duplicate alerts when the same tender is evaluated multiple times.
        """
        exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM corruption_alert_log
                WHERE user_id = $1 AND tender_id = $2 AND rule_type = $3
            )
        """, user_id, tender_id, rule_type)
        return bool(exists)

    # ------------------------------------------------------------------ #
    # ALERT INSERTION
    # ------------------------------------------------------------------ #

    async def _insert_alert(self, conn, subscription_id: int, user_id: str,
                            tender_id: str, rule_type: str, severity: str,
                            title: str, details: dict) -> Optional[int]:
        """Insert a new alert into corruption_alert_log.

        Returns:
            The new alert_id, or None if insertion failed.
        """
        try:
            alert_id = await conn.fetchval("""
                INSERT INTO corruption_alert_log
                    (subscription_id, user_id, tender_id, rule_type, severity, title, details)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                RETURNING alert_id
            """, subscription_id, user_id, tender_id, rule_type, severity,
                title, json.dumps(details, default=str))
            return alert_id
        except Exception as e:
            logger.error(f"Failed to insert alert for user={user_id} tender={tender_id}: {e}")
            return None

    # ------------------------------------------------------------------ #
    # SINGLE TENDER EVALUATION
    # ------------------------------------------------------------------ #

    async def evaluate_tender(self, pool, tender_id: str) -> List[dict]:
        """Evaluate a single tender against all active subscriptions.

        Steps:
          1. Fetch enriched tender data (risk score, flags, values, patterns).
          2. Fetch all active subscriptions.
          3. For each subscription, create the rule from config, evaluate.
          4. Deduplicate (skip if user+tender+rule already alerted).
          5. Insert new alerts into corruption_alert_log.
          6. Return list of generated alerts.

        Args:
            pool: asyncpg connection pool.
            tender_id: Tender identifier.

        Returns:
            List of dicts with keys: alert_id, user_id, tender_id, rule_type,
            severity, title, details.
        """
        async with pool.acquire() as conn:
            tender_data = await self._fetch_tender_data(conn, tender_id)
            if not tender_data:
                logger.debug(f"Tender {tender_id} not found, skipping evaluation")
                return []

            subscriptions = await self._fetch_active_subscriptions(conn)
            if not subscriptions:
                return []

            generated = []
            for sub in subscriptions:
                rule_type = sub['rule_type']
                if rule_type not in AVAILABLE_RULES:
                    logger.warning(f"Unknown rule_type '{rule_type}' in subscription {sub['subscription_id']}")
                    continue

                try:
                    rule = create_rule(rule_type, sub['rule_config'])
                except ValueError as e:
                    logger.warning(f"Cannot create rule for subscription {sub['subscription_id']}: {e}")
                    continue

                result = rule.evaluate(tender_data)
                if result is None:
                    continue

                alert_severity = result.get('severity', rule.default_severity)

                # Check severity filter: only alert if severity meets threshold
                severity_filter = sub.get('severity_filter')
                if severity_filter and not severity_meets_threshold(alert_severity, severity_filter):
                    continue

                # Deduplicate
                if await self._alert_exists(conn, sub['user_id'], tender_id, rule_type):
                    continue

                alert_id = await self._insert_alert(
                    conn,
                    subscription_id=sub['subscription_id'],
                    user_id=sub['user_id'],
                    tender_id=tender_id,
                    rule_type=rule_type,
                    severity=alert_severity,
                    title=result['title'],
                    details=result.get('details', {}),
                )

                if alert_id is not None:
                    generated.append({
                        'alert_id': alert_id,
                        'user_id': sub['user_id'],
                        'tender_id': tender_id,
                        'rule_type': rule_type,
                        'severity': alert_severity,
                        'title': result['title'],
                        'details': result.get('details', {}),
                    })

            return generated

    # ------------------------------------------------------------------ #
    # BATCH EVALUATION (NEW TENDERS)
    # ------------------------------------------------------------------ #

    async def evaluate_new_tenders(self, pool, since: datetime = None) -> dict:
        """Evaluate all tenders with risk scores since the last evaluation run.

        Steps:
          1. Get last evaluation timestamp from corruption_alert_state.
          2. Fetch tender_ids with risk scores analyzed since that timestamp.
          3. Evaluate each tender.
          4. Update corruption_alert_state with current timestamp.

        Args:
            pool: asyncpg connection pool.
            since: Optional override for the start timestamp. If None, uses
                   the stored last_evaluation timestamp from DB.

        Returns:
            Summary dict: {
                evaluated: int,
                alerts_generated: int,
                by_rule_type: {rule_type: count},
                since: str,
                until: str,
                errors: int,
            }
        """
        run_start = datetime.utcnow()

        async with pool.acquire() as conn:
            # Step 1: Get last evaluation timestamp
            if since is None:
                last_eval_str = await conn.fetchval("""
                    SELECT value FROM corruption_alert_state WHERE key = 'last_evaluation'
                """)
                if last_eval_str:
                    try:
                        since = datetime.fromisoformat(last_eval_str)
                    except (ValueError, TypeError):
                        since = datetime(2020, 1, 1)
                else:
                    since = datetime(2020, 1, 1)

            # Step 2: Fetch tender_ids with risk scores updated since last evaluation
            tender_rows = await conn.fetch("""
                SELECT tender_id
                FROM tender_risk_scores
                WHERE last_analyzed >= $1
                ORDER BY last_analyzed ASC
            """, since)

        tender_ids = [r['tender_id'] for r in tender_rows]
        logger.info(f"Alert evaluation: {len(tender_ids)} tenders to evaluate since {since.isoformat()}")

        summary = {
            'evaluated': 0,
            'alerts_generated': 0,
            'by_rule_type': {},
            'since': since.isoformat(),
            'until': run_start.isoformat(),
            'errors': 0,
        }

        # Step 3: Evaluate each tender
        for tid in tender_ids:
            try:
                alerts = await self.evaluate_tender(pool, tid)
                summary['evaluated'] += 1
                summary['alerts_generated'] += len(alerts)
                for alert in alerts:
                    rt = alert['rule_type']
                    summary['by_rule_type'][rt] = summary['by_rule_type'].get(rt, 0) + 1
            except Exception as e:
                logger.error(f"Error evaluating tender {tid}: {e}")
                summary['errors'] += 1

        # Step 4: Update last evaluation timestamp
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO corruption_alert_state (key, value, updated_at)
                VALUES ('last_evaluation', $1, NOW())
                ON CONFLICT (key) DO UPDATE SET value = $1, updated_at = NOW()
            """, run_start.isoformat())

        logger.info(
            f"Alert evaluation complete: {summary['evaluated']} evaluated, "
            f"{summary['alerts_generated']} alerts generated, "
            f"{summary['errors']} errors"
        )
        return summary

    # ------------------------------------------------------------------ #
    # USER ALERTS
    # ------------------------------------------------------------------ #

    async def get_user_alerts(
        self,
        pool,
        user_id: str,
        unread_only: bool = False,
        severity: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[dict], int]:
        """Get paginated alerts for a user.

        Args:
            pool: asyncpg connection pool.
            user_id: The user's identifier.
            unread_only: If True, only return unread alerts.
            severity: Optional severity filter (e.g., 'high').
            page: Page number (1-based).
            page_size: Number of alerts per page.

        Returns:
            Tuple of (list of alert dicts, total count).
        """
        async with pool.acquire() as conn:
            # Build WHERE clause
            conditions = ["user_id = $1"]
            params: list = [user_id]
            param_idx = 1

            if unread_only:
                conditions.append("read = FALSE")

            if severity:
                param_idx += 1
                conditions.append(f"severity = ${param_idx}")
                params.append(severity)

            where_clause = " AND ".join(conditions)

            # Count total
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM corruption_alert_log WHERE {where_clause}",
                *params
            )

            # Fetch page
            offset = (page - 1) * page_size
            param_idx += 1
            limit_param = param_idx
            param_idx += 1
            offset_param = param_idx

            rows = await conn.fetch(
                f"""
                SELECT
                    alert_id,
                    subscription_id,
                    user_id,
                    tender_id,
                    rule_type,
                    severity,
                    title,
                    details,
                    read,
                    read_at,
                    created_at
                FROM corruption_alert_log
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ${limit_param} OFFSET ${offset_param}
                """,
                *params, page_size, offset
            )

            alerts = []
            for row in rows:
                alert = dict(row)
                # Parse JSONB details
                details = alert.get('details')
                if isinstance(details, str):
                    try:
                        alert['details'] = json.loads(details) if details else {}
                    except (json.JSONDecodeError, TypeError):
                        alert['details'] = {}
                elif not isinstance(details, dict):
                    alert['details'] = {}

                # Convert datetime fields to ISO strings for JSON serialization
                for dt_field in ('read_at', 'created_at'):
                    if isinstance(alert.get(dt_field), datetime):
                        alert[dt_field] = alert[dt_field].isoformat()

                alerts.append(alert)

            return alerts, total or 0

    # ------------------------------------------------------------------ #
    # MARK READ
    # ------------------------------------------------------------------ #

    async def mark_read(self, pool, alert_id: int, user_id: str) -> bool:
        """Mark an alert as read.

        Args:
            pool: asyncpg connection pool.
            alert_id: The alert to mark.
            user_id: The user who owns the alert (security check).

        Returns:
            True if the alert was found and updated, False otherwise.
        """
        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE corruption_alert_log
                SET read = TRUE, read_at = NOW()
                WHERE alert_id = $1 AND user_id = $2 AND read = FALSE
            """, alert_id, user_id)
            # asyncpg returns 'UPDATE N' where N is rows affected
            return result == 'UPDATE 1'

    # ------------------------------------------------------------------ #
    # MARK ALL READ
    # ------------------------------------------------------------------ #

    async def mark_all_read(self, pool, user_id: str) -> int:
        """Mark all unread alerts as read for a user.

        Returns:
            Number of alerts marked as read.
        """
        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE corruption_alert_log
                SET read = TRUE, read_at = NOW()
                WHERE user_id = $1 AND read = FALSE
            """, user_id)
            # Parse 'UPDATE N' to get count
            try:
                return int(result.split()[-1])
            except (ValueError, IndexError):
                return 0

    # ------------------------------------------------------------------ #
    # STATISTICS
    # ------------------------------------------------------------------ #

    async def get_stats(self, pool, user_id: str = None) -> dict:
        """Get alert statistics.

        If user_id is provided, returns stats scoped to that user.
        Otherwise returns global alert stats.

        Args:
            pool: asyncpg connection pool.
            user_id: Optional user identifier for scoped stats.

        Returns:
            Dict with keys: total_alerts, unread_count, by_severity,
            by_rule_type, recent_24h, recent_7d, subscriptions_count.
        """
        async with pool.acquire() as conn:
            if user_id:
                # User-scoped stats
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM corruption_alert_log WHERE user_id = $1",
                    user_id
                )
                unread = await conn.fetchval(
                    "SELECT COUNT(*) FROM corruption_alert_log WHERE user_id = $1 AND read = FALSE",
                    user_id
                )

                severity_rows = await conn.fetch("""
                    SELECT severity, COUNT(*) as cnt
                    FROM corruption_alert_log
                    WHERE user_id = $1
                    GROUP BY severity
                """, user_id)

                rule_rows = await conn.fetch("""
                    SELECT rule_type, COUNT(*) as cnt
                    FROM corruption_alert_log
                    WHERE user_id = $1
                    GROUP BY rule_type
                """, user_id)

                now = datetime.utcnow()
                recent_24h = await conn.fetchval("""
                    SELECT COUNT(*) FROM corruption_alert_log
                    WHERE user_id = $1 AND created_at >= $2
                """, user_id, now - timedelta(hours=24))

                recent_7d = await conn.fetchval("""
                    SELECT COUNT(*) FROM corruption_alert_log
                    WHERE user_id = $1 AND created_at >= $2
                """, user_id, now - timedelta(days=7))

                subs_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM corruption_alert_subscriptions
                    WHERE user_id = $1 AND active = TRUE
                """, user_id)
            else:
                # Global stats
                total = await conn.fetchval("SELECT COUNT(*) FROM corruption_alert_log")
                unread = await conn.fetchval(
                    "SELECT COUNT(*) FROM corruption_alert_log WHERE read = FALSE"
                )

                severity_rows = await conn.fetch("""
                    SELECT severity, COUNT(*) as cnt
                    FROM corruption_alert_log
                    GROUP BY severity
                """)

                rule_rows = await conn.fetch("""
                    SELECT rule_type, COUNT(*) as cnt
                    FROM corruption_alert_log
                    GROUP BY rule_type
                """)

                now = datetime.utcnow()
                recent_24h = await conn.fetchval("""
                    SELECT COUNT(*) FROM corruption_alert_log
                    WHERE created_at >= $1
                """, now - timedelta(hours=24))

                recent_7d = await conn.fetchval("""
                    SELECT COUNT(*) FROM corruption_alert_log
                    WHERE created_at >= $1
                """, now - timedelta(days=7))

                subs_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM corruption_alert_subscriptions
                    WHERE active = TRUE
                """)

            by_severity = {r['severity']: r['cnt'] for r in severity_rows}
            by_rule_type = {r['rule_type']: r['cnt'] for r in rule_rows}

            # Fetch last evaluation info
            last_eval = await conn.fetchrow("""
                SELECT value, updated_at
                FROM corruption_alert_state
                WHERE key = 'last_evaluation'
            """)

            return {
                'total_alerts': total or 0,
                'unread_count': unread or 0,
                'by_severity': by_severity,
                'by_rule_type': by_rule_type,
                'recent_24h': recent_24h or 0,
                'recent_7d': recent_7d or 0,
                'subscriptions_count': subs_count or 0,
                'last_evaluation': last_eval['value'] if last_eval else None,
                'last_evaluation_at': last_eval['updated_at'].isoformat() if last_eval and last_eval['updated_at'] else None,
            }
