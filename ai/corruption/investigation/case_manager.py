"""
Investigation Case Manager for nabavkidata corruption detection.

Provides CRUD operations for investigation cases, including:
- Case lifecycle management (create, update, close, archive)
- Tender and entity attachment/removal
- Evidence collection and note-taking
- Activity timeline and dashboard stats

All methods accept an asyncpg pool and use `async with pool.acquire()`.

Author: nabavkidata.com
Date: 2026-02-19
Phase: 4.2 - Investigation Case Management
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Valid enum values for validation
VALID_STATUSES = {'open', 'in_progress', 'review', 'closed', 'archived'}
VALID_PRIORITIES = {'low', 'medium', 'high', 'critical'}
VALID_TENDER_ROLES = {'suspect', 'reference', 'control'}
VALID_ENTITY_ROLES = {'suspect', 'witness', 'victim', 'reference'}
VALID_ENTITY_TYPES = {'company', 'institution', 'person'}
VALID_EVIDENCE_TYPES = {'flag', 'anomaly', 'relationship', 'document', 'manual'}
VALID_SEVERITIES = {'low', 'medium', 'high', 'critical'}


def _row_to_dict(row) -> dict:
    """Convert an asyncpg Record to a JSON-serializable dict."""
    if row is None:
        return {}
    d = dict(row)
    for key, value in d.items():
        if isinstance(value, datetime):
            d[key] = value.isoformat()
        elif hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, list, dict)):
            d[key] = str(value)
        # Handle JSONB columns returned as strings
        if isinstance(value, str) and key in ('metadata', 'details'):
            try:
                d[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def _rows_to_list(rows) -> list:
    """Convert a list of asyncpg Records to JSON-serializable dicts."""
    return [_row_to_dict(row) for row in rows]


class CaseManager:
    """
    Manages investigation cases for corruption detection.

    All methods are async and accept an asyncpg connection pool as their
    first argument. Database connections are acquired and released within
    each method via `async with pool.acquire() as conn:`.
    """

    async def create_case(
        self,
        pool,
        title: str,
        description: Optional[str] = None,
        priority: str = 'medium',
        assigned_to: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> dict:
        """
        Create a new investigation case.

        Args:
            pool: asyncpg connection pool
            title: Case title (required)
            description: Case description
            priority: low, medium, high, critical (default: medium)
            assigned_to: Username of assigned analyst
            created_by: Username of case creator

        Returns:
            Dict with the created case data including case_id.

        Raises:
            ValueError: If priority is not a valid value.
        """
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority '{priority}'. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}")

        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO investigation_cases
                    (title, description, status, priority, assigned_to, created_by)
                VALUES ($1, $2, 'open', $3, $4, $5)
                RETURNING case_id, title, description, status, priority,
                          assigned_to, created_by, total_risk_value,
                          tender_count, entity_count, evidence_count,
                          created_at, updated_at
            """, title, description, priority, assigned_to, created_by)

            case = _row_to_dict(row)

            # Log the creation activity
            await conn.execute("""
                INSERT INTO case_activity_log
                    (case_id, action, actor, new_value, details)
                VALUES ($1, 'created', $2, $3, $4)
            """,
                case['case_id'],
                created_by,
                f"Case created: {title}",
                json.dumps({"priority": priority, "assigned_to": assigned_to}),
            )

            logger.info(f"Created investigation case {case['case_id']}: {title}")
            return case

    async def get_case(self, pool, case_id: int) -> dict:
        """
        Get full investigation case details with attached tenders, entities,
        and evidence count.

        Args:
            pool: asyncpg connection pool
            case_id: The case ID to retrieve

        Returns:
            Dict with case data, attached tenders, entities, and evidence count.
            Returns empty dict if case not found.
        """
        async with pool.acquire() as conn:
            # Fetch the case
            case_row = await conn.fetchrow("""
                SELECT case_id, title, description, status, priority,
                       assigned_to, created_by, total_risk_value,
                       tender_count, entity_count, evidence_count,
                       created_at, updated_at
                FROM investigation_cases
                WHERE case_id = $1
            """, case_id)

            if not case_row:
                return {}

            case = _row_to_dict(case_row)

            # Fetch attached tenders with their risk scores
            tender_rows = await conn.fetch("""
                SELECT ct.id, ct.case_id, ct.tender_id, ct.role, ct.notes,
                       ct.added_at,
                       t.title AS tender_title,
                       t.procuring_entity,
                       t.winner,
                       t.estimated_value_mkd,
                       t.status AS tender_status,
                       COALESCE(trs.risk_score, 0) AS risk_score,
                       COALESCE(trs.risk_level, 'minimal') AS risk_level,
                       COALESCE(trs.flag_count, 0) AS flag_count
                FROM case_tenders ct
                LEFT JOIN tenders t ON ct.tender_id = t.tender_id
                LEFT JOIN tender_risk_scores trs ON ct.tender_id = trs.tender_id
                WHERE ct.case_id = $1
                ORDER BY ct.added_at DESC
            """, case_id)

            # Fetch attached entities
            entity_rows = await conn.fetch("""
                SELECT id, case_id, entity_id, entity_type, entity_name,
                       role, added_at
                FROM case_entities
                WHERE case_id = $1
                ORDER BY added_at DESC
            """, case_id)

            # Fetch evidence count by type
            evidence_summary_rows = await conn.fetch("""
                SELECT evidence_type, COUNT(*) AS count,
                       MAX(severity) AS max_severity
                FROM case_evidence
                WHERE case_id = $1
                GROUP BY evidence_type
                ORDER BY count DESC
            """, case_id)

            # Fetch recent notes (last 5)
            note_rows = await conn.fetch("""
                SELECT note_id, author, content, created_at
                FROM case_notes
                WHERE case_id = $1
                ORDER BY created_at DESC
                LIMIT 5
            """, case_id)

            case['tenders'] = _rows_to_list(tender_rows)
            case['entities'] = _rows_to_list(entity_rows)
            case['evidence_summary'] = _rows_to_list(evidence_summary_rows)
            case['recent_notes'] = _rows_to_list(note_rows)

            # Compute aggregated risk value from attached tenders
            total_risk = sum(
                float(t.get('estimated_value_mkd') or 0)
                for t in case['tenders']
                if t.get('role') == 'suspect'
            )
            case['computed_risk_value'] = total_risk

            return case

    async def list_cases(
        self,
        pool,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[dict], int]:
        """
        List investigation cases with pagination and optional filters.

        Args:
            pool: asyncpg connection pool
            status: Filter by case status
            priority: Filter by priority level
            assigned_to: Filter by assigned analyst
            offset: Pagination offset
            limit: Page size (max 100)

        Returns:
            Tuple of (list of case dicts, total count).
        """
        if status and status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}")
        if priority and priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority '{priority}'. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}")

        async with pool.acquire() as conn:
            # Build dynamic WHERE clause
            conditions = []
            params: list = []
            param_idx = 1

            if status:
                conditions.append(f"status = ${param_idx}")
                params.append(status)
                param_idx += 1

            if priority:
                conditions.append(f"priority = ${param_idx}")
                params.append(priority)
                param_idx += 1

            if assigned_to:
                conditions.append(f"assigned_to = ${param_idx}")
                params.append(assigned_to)
                param_idx += 1

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # Count total
            count_query = f"SELECT COUNT(*) FROM investigation_cases {where_clause}"
            total = await conn.fetchval(count_query, *params)

            # Fetch paginated results
            data_query = f"""
                SELECT case_id, title, description, status, priority,
                       assigned_to, created_by, total_risk_value,
                       tender_count, entity_count, evidence_count,
                       created_at, updated_at
                FROM investigation_cases
                {where_clause}
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    updated_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
            """
            params.extend([limit, offset])

            rows = await conn.fetch(data_query, *params)
            cases = _rows_to_list(rows)

            return cases, total

    async def update_case(
        self,
        pool,
        case_id: int,
        updates: Dict[str, Any],
        actor: Optional[str] = None,
    ) -> dict:
        """
        Update case fields (status, priority, assigned_to, title, description).
        Logs each change to the activity log.

        Args:
            pool: asyncpg connection pool
            case_id: The case to update
            updates: Dict of field->value to update
            actor: Username performing the update

        Returns:
            Updated case dict.

        Raises:
            ValueError: If case not found or invalid field values.
        """
        allowed_fields = {'status', 'priority', 'assigned_to', 'title', 'description'}
        filtered = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered:
            raise ValueError(f"No valid fields to update. Allowed: {', '.join(sorted(allowed_fields))}")

        if 'status' in filtered and filtered['status'] not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{filtered['status']}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}")
        if 'priority' in filtered and filtered['priority'] not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority '{filtered['priority']}'. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}")

        async with pool.acquire() as conn:
            # Get current values for activity logging
            current = await conn.fetchrow("""
                SELECT status, priority, assigned_to, title, description
                FROM investigation_cases
                WHERE case_id = $1
            """, case_id)

            if not current:
                raise ValueError(f"Case {case_id} not found")

            # Build dynamic SET clause
            set_parts = []
            params: list = []
            param_idx = 1

            for field, value in filtered.items():
                set_parts.append(f"{field} = ${param_idx}")
                params.append(value)
                param_idx += 1

            set_parts.append(f"updated_at = NOW()")

            set_clause = ", ".join(set_parts)
            params.append(case_id)

            row = await conn.fetchrow(f"""
                UPDATE investigation_cases
                SET {set_clause}
                WHERE case_id = ${param_idx}
                RETURNING case_id, title, description, status, priority,
                          assigned_to, created_by, total_risk_value,
                          tender_count, entity_count, evidence_count,
                          created_at, updated_at
            """, *params)

            if not row:
                raise ValueError(f"Case {case_id} not found")

            # Log each changed field
            for field, new_value in filtered.items():
                old_value = current[field]
                if str(old_value) != str(new_value):
                    action = f"{field}_changed"
                    await conn.execute("""
                        INSERT INTO case_activity_log
                            (case_id, action, actor, old_value, new_value, details)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                        case_id,
                        action,
                        actor,
                        str(old_value) if old_value is not None else None,
                        str(new_value) if new_value is not None else None,
                        json.dumps({"field": field}),
                    )

            logger.info(f"Updated case {case_id}: {list(filtered.keys())}")
            return _row_to_dict(row)

    async def attach_tender(
        self,
        pool,
        case_id: int,
        tender_id: str,
        role: str = 'suspect',
        notes: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> dict:
        """
        Attach a tender to an investigation case.

        Args:
            pool: asyncpg connection pool
            case_id: The case to attach to
            tender_id: The tender ID to attach
            role: suspect, reference, or control
            notes: Optional notes about this tender's relevance
            actor: Username performing the action

        Returns:
            Dict with the attachment record.

        Raises:
            ValueError: If role is invalid or tender already attached.
        """
        if role not in VALID_TENDER_ROLES:
            raise ValueError(f"Invalid role '{role}'. Must be one of: {', '.join(sorted(VALID_TENDER_ROLES))}")

        async with pool.acquire() as conn:
            # Verify case exists
            case_exists = await conn.fetchval(
                "SELECT 1 FROM investigation_cases WHERE case_id = $1", case_id
            )
            if not case_exists:
                raise ValueError(f"Case {case_id} not found")

            try:
                row = await conn.fetchrow("""
                    INSERT INTO case_tenders (case_id, tender_id, role, notes)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, case_id, tender_id, role, notes, added_at
                """, case_id, tender_id, role, notes)
            except Exception as e:
                if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
                    raise ValueError(f"Tender {tender_id} is already attached to case {case_id}")
                raise

            # Update tender count on the case
            await conn.execute("""
                UPDATE investigation_cases
                SET tender_count = (
                    SELECT COUNT(*) FROM case_tenders WHERE case_id = $1
                ), updated_at = NOW()
                WHERE case_id = $1
            """, case_id)

            # Log activity
            await conn.execute("""
                INSERT INTO case_activity_log
                    (case_id, action, actor, new_value, details)
                VALUES ($1, 'tender_added', $2, $3, $4)
            """,
                case_id,
                actor,
                tender_id,
                json.dumps({"role": role, "notes": notes}),
            )

            logger.info(f"Attached tender {tender_id} to case {case_id} as {role}")
            return _row_to_dict(row)

    async def remove_tender(
        self,
        pool,
        case_id: int,
        tender_id: str,
        actor: Optional[str] = None,
    ) -> bool:
        """
        Remove a tender from an investigation case.

        Args:
            pool: asyncpg connection pool
            case_id: The case to remove from
            tender_id: The tender ID to remove
            actor: Username performing the action

        Returns:
            True if tender was removed, False if it wasn't attached.
        """
        async with pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM case_tenders
                WHERE case_id = $1 AND tender_id = $2
            """, case_id, tender_id)

            removed = result.split()[-1] != '0'

            if removed:
                # Update tender count
                await conn.execute("""
                    UPDATE investigation_cases
                    SET tender_count = (
                        SELECT COUNT(*) FROM case_tenders WHERE case_id = $1
                    ), updated_at = NOW()
                    WHERE case_id = $1
                """, case_id)

                # Log activity
                await conn.execute("""
                    INSERT INTO case_activity_log
                        (case_id, action, actor, old_value, details)
                    VALUES ($1, 'tender_removed', $2, $3, '{}')
                """, case_id, actor, tender_id)

                logger.info(f"Removed tender {tender_id} from case {case_id}")

            return removed

    async def attach_entity(
        self,
        pool,
        case_id: int,
        entity_id: str,
        entity_type: str,
        entity_name: Optional[str] = None,
        role: str = 'suspect',
        actor: Optional[str] = None,
    ) -> dict:
        """
        Attach an entity (company, institution, person) to a case.

        Args:
            pool: asyncpg connection pool
            case_id: The case to attach to
            entity_id: Unique identifier for the entity
            entity_type: company, institution, or person
            entity_name: Human-readable entity name
            role: suspect, witness, victim, or reference
            actor: Username performing the action

        Returns:
            Dict with the attachment record.

        Raises:
            ValueError: If entity_type or role is invalid.
        """
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}")
        if role not in VALID_ENTITY_ROLES:
            raise ValueError(f"Invalid role '{role}'. Must be one of: {', '.join(sorted(VALID_ENTITY_ROLES))}")

        async with pool.acquire() as conn:
            # Verify case exists
            case_exists = await conn.fetchval(
                "SELECT 1 FROM investigation_cases WHERE case_id = $1", case_id
            )
            if not case_exists:
                raise ValueError(f"Case {case_id} not found")

            try:
                row = await conn.fetchrow("""
                    INSERT INTO case_entities
                        (case_id, entity_id, entity_type, entity_name, role)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id, case_id, entity_id, entity_type, entity_name,
                              role, added_at
                """, case_id, entity_id, entity_type, entity_name, role)
            except Exception as e:
                if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
                    raise ValueError(
                        f"Entity {entity_id} ({entity_type}) is already attached to case {case_id}"
                    )
                raise

            # Update entity count
            await conn.execute("""
                UPDATE investigation_cases
                SET entity_count = (
                    SELECT COUNT(*) FROM case_entities WHERE case_id = $1
                ), updated_at = NOW()
                WHERE case_id = $1
            """, case_id)

            # Log activity
            await conn.execute("""
                INSERT INTO case_activity_log
                    (case_id, action, actor, new_value, details)
                VALUES ($1, 'entity_added', $2, $3, $4)
            """,
                case_id,
                actor,
                entity_name or entity_id,
                json.dumps({
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                    "role": role,
                }),
            )

            logger.info(f"Attached entity {entity_id} ({entity_type}) to case {case_id}")
            return _row_to_dict(row)

    async def add_evidence(
        self,
        pool,
        case_id: int,
        evidence_type: str,
        source_module: Optional[str],
        source_id: Optional[str],
        description: str,
        severity: str = 'medium',
        metadata: Optional[dict] = None,
        actor: Optional[str] = None,
    ) -> dict:
        """
        Add an evidence item to an investigation case.

        Args:
            pool: asyncpg connection pool
            case_id: The case to add evidence to
            evidence_type: flag, anomaly, relationship, document, or manual
            source_module: Module that produced this evidence (corruption, collusion, etc.)
            source_id: ID of the source record (flag_id, etc.)
            description: Human-readable description of the evidence
            severity: low, medium, high, or critical
            metadata: Additional structured data (stored as JSONB)
            actor: Username adding the evidence

        Returns:
            Dict with the created evidence record.

        Raises:
            ValueError: If evidence_type or severity is invalid.
        """
        if evidence_type not in VALID_EVIDENCE_TYPES:
            raise ValueError(f"Invalid evidence_type '{evidence_type}'. Must be one of: {', '.join(sorted(VALID_EVIDENCE_TYPES))}")
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"Invalid severity '{severity}'. Must be one of: {', '.join(sorted(VALID_SEVERITIES))}")

        async with pool.acquire() as conn:
            # Verify case exists
            case_exists = await conn.fetchval(
                "SELECT 1 FROM investigation_cases WHERE case_id = $1", case_id
            )
            if not case_exists:
                raise ValueError(f"Case {case_id} not found")

            row = await conn.fetchrow("""
                INSERT INTO case_evidence
                    (case_id, evidence_type, source_module, source_id,
                     description, severity, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                RETURNING evidence_id, case_id, evidence_type, source_module,
                          source_id, description, severity, metadata, added_at
            """,
                case_id,
                evidence_type,
                source_module,
                source_id,
                description,
                severity,
                json.dumps(metadata or {}),
            )

            # Update evidence count
            await conn.execute("""
                UPDATE investigation_cases
                SET evidence_count = (
                    SELECT COUNT(*) FROM case_evidence WHERE case_id = $1
                ), updated_at = NOW()
                WHERE case_id = $1
            """, case_id)

            # Log activity
            await conn.execute("""
                INSERT INTO case_activity_log
                    (case_id, action, actor, new_value, details)
                VALUES ($1, 'evidence_added', $2, $3, $4)
            """,
                case_id,
                actor,
                description[:200],
                json.dumps({
                    "evidence_type": evidence_type,
                    "source_module": source_module,
                    "severity": severity,
                }),
            )

            logger.info(f"Added {evidence_type} evidence to case {case_id}")
            return _row_to_dict(row)

    async def add_note(
        self,
        pool,
        case_id: int,
        author: str,
        content: str,
    ) -> dict:
        """
        Add an analyst note to an investigation case.

        Args:
            pool: asyncpg connection pool
            case_id: The case to add a note to
            author: Username of the note author
            content: Note content text

        Returns:
            Dict with the created note record.

        Raises:
            ValueError: If case not found or content is empty.
        """
        if not content or not content.strip():
            raise ValueError("Note content cannot be empty")

        async with pool.acquire() as conn:
            # Verify case exists
            case_exists = await conn.fetchval(
                "SELECT 1 FROM investigation_cases WHERE case_id = $1", case_id
            )
            if not case_exists:
                raise ValueError(f"Case {case_id} not found")

            row = await conn.fetchrow("""
                INSERT INTO case_notes (case_id, author, content)
                VALUES ($1, $2, $3)
                RETURNING note_id, case_id, author, content, created_at
            """, case_id, author, content.strip())

            # Update case timestamp
            await conn.execute("""
                UPDATE investigation_cases
                SET updated_at = NOW()
                WHERE case_id = $1
            """, case_id)

            # Log activity
            await conn.execute("""
                INSERT INTO case_activity_log
                    (case_id, action, actor, new_value, details)
                VALUES ($1, 'note_added', $2, $3, '{}')
            """, case_id, author, content.strip()[:200])

            logger.info(f"Added note to case {case_id} by {author}")
            return _row_to_dict(row)

    async def get_timeline(
        self,
        pool,
        case_id: int,
        limit: int = 50,
    ) -> list:
        """
        Get the activity timeline for an investigation case.

        Args:
            pool: asyncpg connection pool
            case_id: The case to get timeline for
            limit: Maximum number of entries (default 50)

        Returns:
            List of activity log entries ordered by created_at DESC.
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT log_id, case_id, action, actor, old_value,
                       new_value, details, created_at
                FROM case_activity_log
                WHERE case_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, case_id, limit)

            return _rows_to_list(rows)

    async def get_dashboard(self, pool) -> dict:
        """
        Get investigation dashboard summary statistics.

        Returns a dict with:
        - total_cases: Total number of investigation cases
        - by_status: Count of cases per status
        - by_priority: Count of cases per priority
        - recent_activity: Last 10 activity log entries across all cases
        - open_cases_count: Number of non-closed/non-archived cases
        - assigned_analysts: List of analysts with assigned case counts

        Args:
            pool: asyncpg connection pool

        Returns:
            Dashboard summary dict.
        """
        async with pool.acquire() as conn:
            # Total cases
            total = await conn.fetchval("SELECT COUNT(*) FROM investigation_cases")

            # Cases by status
            status_rows = await conn.fetch("""
                SELECT status, COUNT(*) as count
                FROM investigation_cases
                GROUP BY status
                ORDER BY count DESC
            """)
            by_status = {row['status']: row['count'] for row in status_rows}

            # Cases by priority
            priority_rows = await conn.fetch("""
                SELECT priority, COUNT(*) as count
                FROM investigation_cases
                GROUP BY priority
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END
            """)
            by_priority = {row['priority']: row['count'] for row in priority_rows}

            # Open (non-closed, non-archived) case count
            open_count = await conn.fetchval("""
                SELECT COUNT(*) FROM investigation_cases
                WHERE status NOT IN ('closed', 'archived')
            """)

            # Total evidence and tenders across all cases
            totals_row = await conn.fetchrow("""
                SELECT
                    COALESCE(SUM(tender_count), 0) AS total_tenders,
                    COALESCE(SUM(entity_count), 0) AS total_entities,
                    COALESCE(SUM(evidence_count), 0) AS total_evidence
                FROM investigation_cases
            """)

            # Assigned analysts with case counts
            analyst_rows = await conn.fetch("""
                SELECT assigned_to, COUNT(*) as case_count
                FROM investigation_cases
                WHERE assigned_to IS NOT NULL
                  AND status NOT IN ('closed', 'archived')
                GROUP BY assigned_to
                ORDER BY case_count DESC
            """)
            assigned_analysts = [
                {"analyst": row['assigned_to'], "case_count": row['case_count']}
                for row in analyst_rows
            ]

            # Recent activity across all cases
            activity_rows = await conn.fetch("""
                SELECT cal.log_id, cal.case_id, cal.action, cal.actor,
                       cal.old_value, cal.new_value, cal.details, cal.created_at,
                       ic.title AS case_title
                FROM case_activity_log cal
                JOIN investigation_cases ic ON cal.case_id = ic.case_id
                ORDER BY cal.created_at DESC
                LIMIT 10
            """)
            recent_activity = _rows_to_list(activity_rows)

            return {
                "total_cases": total,
                "open_cases_count": open_count,
                "by_status": by_status,
                "by_priority": by_priority,
                "total_tenders_attached": totals_row['total_tenders'],
                "total_entities_attached": totals_row['total_entities'],
                "total_evidence_items": totals_row['total_evidence'],
                "assigned_analysts": assigned_analysts,
                "recent_activity": recent_activity,
            }
