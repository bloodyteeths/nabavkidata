"""
Evidence Linker for nabavkidata corruption investigation cases.

Collects and synthesizes evidence from multiple corruption detection modules
to build a comprehensive evidence chain narrative for investigation cases.

Sources aggregated:
- corruption_flags: Individual corruption indicators per tender
- tender_risk_scores: Aggregated risk scores per tender
- company_relationships: Known company relationships (collusion indicators)
- gnn_predictions_cache: GNN-based collusion risk predictions
- entity_temporal_profiles: Temporal risk trend analysis per entity

Author: nabavkidata.com
Date: 2026-02-19
Phase: 4.2 - Investigation Case Management & Evidence Synthesis
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _safe_json(value) -> Any:
    """Safely parse JSONB values that may arrive as strings from asyncpg."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _format_datetime(value) -> Optional[str]:
    """Convert datetime to ISO string if not None."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


def _format_value_mkd(value) -> str:
    """Format a monetary value in MKD for narrative text."""
    if value is None:
        return "непознато"
    try:
        v = float(value)
        if v >= 1_000_000:
            return f"{v / 1_000_000:.1f}M MKD"
        elif v >= 1_000:
            return f"{v / 1_000:.0f}K MKD"
        else:
            return f"{v:.0f} MKD"
    except (ValueError, TypeError):
        return str(value)


class EvidenceLinker:
    """
    Builds comprehensive evidence chains for investigation cases by
    aggregating data from all corruption detection modules.

    The build_evidence_chain method returns a structured dict with:
    - tenders: Detailed info on all attached tenders
    - entities: Info on all attached entities with risk data
    - flags: All corruption flags for attached tenders
    - relationships: Known relationships between attached entities
    - timeline: Temporal risk patterns for attached entities
    - narrative_summary: Auto-generated text describing the evidence
    """

    async def build_evidence_chain(self, pool, case_id: int) -> dict:
        """
        Collect ALL evidence for a case from multiple modules and build
        a structured evidence chain with auto-generated narrative.

        Args:
            pool: asyncpg connection pool
            case_id: The investigation case ID

        Returns:
            Dict with keys: tenders, entities, flags, relationships,
            timeline, evidence_items, narrative_summary.

        Raises:
            ValueError: If case not found.
        """
        async with pool.acquire() as conn:
            # ----------------------------------------------------------
            # 1. Verify case exists and fetch basic info
            # ----------------------------------------------------------
            case_row = await conn.fetchrow("""
                SELECT case_id, title, description, status, priority
                FROM investigation_cases
                WHERE case_id = $1
            """, case_id)

            if not case_row:
                raise ValueError(f"Case {case_id} not found")

            case_title = case_row['title']
            case_priority = case_row['priority']

            # ----------------------------------------------------------
            # 2. Fetch attached tenders with full details
            # ----------------------------------------------------------
            tender_rows = await conn.fetch("""
                SELECT
                    ct.tender_id, ct.role, ct.notes AS case_notes,
                    t.title, t.procuring_entity, t.winner,
                    t.estimated_value_mkd, t.status,
                    t.published_date, t.deadline_date,
                    COALESCE(trs.risk_score, 0) AS risk_score,
                    COALESCE(trs.risk_level, 'minimal') AS risk_level,
                    COALESCE(trs.flag_count, 0) AS flag_count
                FROM case_tenders ct
                LEFT JOIN tenders t ON ct.tender_id = t.tender_id
                LEFT JOIN tender_risk_scores trs ON ct.tender_id = trs.tender_id
                WHERE ct.case_id = $1
                ORDER BY trs.risk_score DESC NULLS LAST
            """, case_id)

            tenders = []
            tender_ids = []
            for row in tender_rows:
                t = dict(row)
                for k, v in t.items():
                    if isinstance(v, datetime):
                        t[k] = v.isoformat()
                    elif hasattr(v, '__str__') and not isinstance(v, (str, int, float, bool, list, dict)):
                        t[k] = str(v)
                tenders.append(t)
                tender_ids.append(row['tender_id'])

            # ----------------------------------------------------------
            # 3. Fetch attached entities with risk data
            # ----------------------------------------------------------
            entity_rows = await conn.fetch("""
                SELECT entity_id, entity_type, entity_name, role
                FROM case_entities
                WHERE case_id = $1
                ORDER BY role, entity_name
            """, case_id)

            entities = []
            entity_names = []
            for row in entity_rows:
                e = dict(row)
                entity_names.append(row['entity_name'] or row['entity_id'])
                entities.append(e)

            # ----------------------------------------------------------
            # 4. Fetch corruption flags for all attached tenders
            # ----------------------------------------------------------
            flags = []
            if tender_ids:
                flag_rows = await conn.fetch("""
                    SELECT cf.flag_id, cf.tender_id, cf.flag_type,
                           cf.severity, cf.score, cf.evidence,
                           cf.description, cf.detected_at,
                           cf.reviewed, cf.false_positive
                    FROM corruption_flags cf
                    WHERE cf.tender_id = ANY($1)
                      AND cf.false_positive = FALSE
                    ORDER BY cf.score DESC, cf.detected_at DESC
                """, tender_ids)

                for row in flag_rows:
                    f = dict(row)
                    f['flag_id'] = str(f['flag_id'])
                    f['evidence'] = _safe_json(f.get('evidence'))
                    if isinstance(f.get('detected_at'), datetime):
                        f['detected_at'] = f['detected_at'].isoformat()
                    flags.append(f)

            # ----------------------------------------------------------
            # 5. Fetch relationships between attached entities
            # ----------------------------------------------------------
            relationships = []
            if entity_names:
                # Search for relationships where any attached entity is
                # company_a or company_b
                try:
                    rel_rows = await conn.fetch("""
                        SELECT relationship_id, company_a, company_b,
                               relationship_type, confidence, evidence,
                               source, discovered_at, verified
                        FROM company_relationships
                        WHERE company_a = ANY($1) OR company_b = ANY($1)
                        ORDER BY confidence DESC
                    """, entity_names)

                    for row in rel_rows:
                        r = dict(row)
                        r['relationship_id'] = str(r['relationship_id'])
                        r['evidence'] = _safe_json(r.get('evidence'))
                        if isinstance(r.get('discovered_at'), datetime):
                            r['discovered_at'] = r['discovered_at'].isoformat()
                        relationships.append(r)
                except Exception as e:
                    # company_relationships table may not exist yet
                    logger.debug(f"Could not fetch company_relationships: {e}")

            # Also try GNN predictions for entity risk
            gnn_risks = {}
            if entity_names:
                try:
                    gnn_rows = await conn.fetch("""
                        SELECT company_name, risk_probability, risk_level,
                               cluster_id
                        FROM gnn_predictions_cache
                        WHERE company_name = ANY($1)
                    """, entity_names)

                    for row in gnn_rows:
                        gnn_risks[row['company_name']] = {
                            "risk_probability": row['risk_probability'],
                            "risk_level": row['risk_level'],
                            "cluster_id": row['cluster_id'],
                        }
                except Exception as e:
                    logger.debug(f"Could not fetch GNN predictions: {e}")

            # Enrich entities with GNN risk data
            for entity in entities:
                name = entity.get('entity_name') or entity.get('entity_id')
                if name in gnn_risks:
                    entity['gnn_risk'] = gnn_risks[name]

            # ----------------------------------------------------------
            # 6. Fetch temporal profiles for attached entities
            # ----------------------------------------------------------
            timeline_data = []
            if entity_names:
                try:
                    temporal_rows = await conn.fetch("""
                        SELECT entity_name, entity_type, trajectory,
                               trajectory_confidence, trajectory_description,
                               trajectory_recommendation, change_points,
                               risk_trend_slope, risk_volatility,
                               tender_count, period_start, period_end,
                               computed_at
                        FROM entity_temporal_profiles
                        WHERE entity_name = ANY($1)
                        ORDER BY risk_trend_slope DESC NULLS LAST
                    """, entity_names)

                    for row in temporal_rows:
                        t = dict(row)
                        t['change_points'] = _safe_json(t.get('change_points'))
                        for k in ('period_start', 'period_end', 'computed_at'):
                            if isinstance(t.get(k), datetime):
                                t[k] = t[k].isoformat()
                            elif t.get(k) is not None:
                                t[k] = str(t[k])
                        timeline_data.append(t)
                except Exception as e:
                    logger.debug(f"Could not fetch temporal profiles: {e}")

            # ----------------------------------------------------------
            # 7. Fetch manually added evidence items
            # ----------------------------------------------------------
            evidence_rows = await conn.fetch("""
                SELECT evidence_id, evidence_type, source_module,
                       source_id, description, severity, metadata,
                       added_at
                FROM case_evidence
                WHERE case_id = $1
                ORDER BY added_at DESC
            """, case_id)

            evidence_items = []
            for row in evidence_rows:
                ev = dict(row)
                ev['metadata'] = _safe_json(ev.get('metadata'))
                if isinstance(ev.get('added_at'), datetime):
                    ev['added_at'] = ev['added_at'].isoformat()
                evidence_items.append(ev)

            # ----------------------------------------------------------
            # 8. Build the narrative summary
            # ----------------------------------------------------------
            narrative = self._build_narrative(
                case_title=case_title,
                case_priority=case_priority,
                tenders=tenders,
                entities=entities,
                flags=flags,
                relationships=relationships,
                timeline_data=timeline_data,
                evidence_items=evidence_items,
            )

            return {
                "case_id": case_id,
                "case_title": case_title,
                "tenders": tenders,
                "entities": entities,
                "flags": flags,
                "relationships": relationships,
                "timeline": timeline_data,
                "evidence_items": evidence_items,
                "narrative_summary": narrative,
            }

    def _build_narrative(
        self,
        case_title: str,
        case_priority: str,
        tenders: List[dict],
        entities: List[dict],
        flags: List[dict],
        relationships: List[dict],
        timeline_data: List[dict],
        evidence_items: List[dict],
    ) -> str:
        """
        Auto-generate a narrative summary describing the evidence chain.

        The narrative describes the key findings in plain language, including:
        - Number of tenders and entities involved
        - Most frequent flag types and their severities
        - Risk score ranges
        - Known entity relationships
        - Temporal risk patterns
        - Manually added evidence summary
        """
        parts: List[str] = []

        # ---- Overview ----
        suspect_tenders = [t for t in tenders if t.get('role') == 'suspect']
        suspect_entities = [e for e in entities if e.get('role') == 'suspect']

        parts.append(
            f"Investigation \"{case_title}\" (priority: {case_priority}) "
            f"involves {len(suspect_tenders)} suspect tender(s) "
            f"and {len(suspect_entities)} suspect entity/entities."
        )

        # ---- Tender details ----
        if suspect_tenders:
            risk_scores = [t.get('risk_score', 0) for t in suspect_tenders]
            min_risk = min(risk_scores) if risk_scores else 0
            max_risk = max(risk_scores) if risk_scores else 0

            total_value = sum(
                float(t.get('estimated_value_mkd') or 0)
                for t in suspect_tenders
            )

            if min_risk == max_risk:
                score_text = f"risk score of {min_risk}"
            else:
                score_text = f"risk scores ranging from {min_risk} to {max_risk}"

            parts.append(
                f"The suspect tenders have {score_text} "
                f"with a combined estimated value of {_format_value_mkd(total_value)}."
            )

            # List procuring entities and winners
            procurers = set(
                t.get('procuring_entity', 'unknown')
                for t in suspect_tenders
                if t.get('procuring_entity')
            )
            winners = set(
                t.get('winner', 'unknown')
                for t in suspect_tenders
                if t.get('winner')
            )
            if procurers:
                parts.append(
                    f"Procuring entities: {', '.join(sorted(procurers))}."
                )
            if winners:
                parts.append(
                    f"Winners: {', '.join(sorted(winners))}."
                )

        # ---- Flag summary ----
        if flags:
            flag_type_counts: Dict[str, int] = {}
            severity_counts: Dict[str, int] = {}
            for f in flags:
                ft = f.get('flag_type', 'unknown')
                sv = f.get('severity', 'medium')
                flag_type_counts[ft] = flag_type_counts.get(ft, 0) + 1
                severity_counts[sv] = severity_counts.get(sv, 0) + 1

            # Sort by count descending
            top_flags = sorted(flag_type_counts.items(), key=lambda x: -x[1])[:5]
            flag_desc = ", ".join(
                f"{count} {ftype.replace('_', ' ')}" for ftype, count in top_flags
            )
            parts.append(
                f"A total of {len(flags)} corruption flag(s) detected: {flag_desc}."
            )

            critical_count = severity_counts.get('critical', 0)
            high_count = severity_counts.get('high', 0)
            if critical_count or high_count:
                parts.append(
                    f"Severity breakdown includes {critical_count} critical "
                    f"and {high_count} high-severity flag(s)."
                )
        else:
            parts.append("No corruption flags detected for the attached tenders.")

        # ---- Entity relationships ----
        if relationships:
            rel_types = set(r.get('relationship_type', '') for r in relationships)
            high_conf = [r for r in relationships if (r.get('confidence') or 0) >= 70]
            parts.append(
                f"{len(relationships)} entity relationship(s) found "
                f"(types: {', '.join(sorted(rel_types))}). "
                f"{len(high_conf)} have confidence >= 70%."
            )

        # ---- GNN collusion risk ----
        gnn_entities = [e for e in entities if e.get('gnn_risk')]
        if gnn_entities:
            high_gnn = [
                e for e in gnn_entities
                if (e['gnn_risk'].get('risk_probability') or 0) >= 0.6
            ]
            if high_gnn:
                names = ", ".join(
                    e.get('entity_name') or e.get('entity_id')
                    for e in high_gnn
                )
                parts.append(
                    f"GNN collusion analysis flagged {len(high_gnn)} "
                    f"entity/entities with elevated risk: {names}."
                )

        # ---- Temporal patterns ----
        if timeline_data:
            escalating = [
                t for t in timeline_data
                if t.get('trajectory') in ('escalating', 'stable_high')
            ]
            if escalating:
                esc_names = ", ".join(t.get('entity_name', '?') for t in escalating)
                parts.append(
                    f"Temporal analysis shows escalating or stable-high risk "
                    f"trajectory for: {esc_names}."
                )
            else:
                trajectories = set(t.get('trajectory', '?') for t in timeline_data)
                parts.append(
                    f"Temporal profiles available for {len(timeline_data)} "
                    f"entity/entities (trajectories: {', '.join(sorted(trajectories))})."
                )

        # ---- Manual evidence ----
        if evidence_items:
            ev_types = {}
            for ev in evidence_items:
                et = ev.get('evidence_type', 'unknown')
                ev_types[et] = ev_types.get(et, 0) + 1
            ev_desc = ", ".join(f"{c} {t}" for t, c in sorted(ev_types.items(), key=lambda x: -x[1]))
            parts.append(
                f"Additionally, {len(evidence_items)} evidence item(s) "
                f"have been manually collected: {ev_desc}."
            )

        return " ".join(parts)
