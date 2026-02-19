"""
Corruption Detection Integration for RAG Query Pipeline

This file contains the code additions needed to integrate corruption detection
into the existing RAG system at /Users/tamsar/Downloads/nabavkidata/ai/rag_query.py

INTEGRATION INSTRUCTIONS:
========================

1. Add the CORRUPTION_QUERY_PATTERNS list after line 38 (after logger initialization)
2. Add the is_corruption_query() function after the existing helper functions (around line 340)
3. Add all the corruption-related methods to the RAGQueryPipeline class before the
   batch_query() method (insert around line 5560, before batch_query)
4. Modify the generate_answer() method in RAGQueryPipeline to add corruption query
   detection at the beginning (see MODIFICATION section at the end)

"""
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# SECTION 1: Add after line 38 (after logger initialization)
# ============================================================================

CORRUPTION_QUERY_PATTERNS = [
    # Macedonian patterns
    r'сомнител(ен|ни|на|но)',      # suspicious
    r'корупци(ја|ски|ско|ја|је)',   # corruption
    r'наместен(и|а|о)?',            # rigged
    r'ризик(от|ови)?',              # risk
    r'црвен(и)?\s+знам(е|иња)',    # red flag(s)
    r'нерегуларн(о|и|а)',           # irregular
    r'измам(а|и)',                  # fraud
    r'злоупотреб(а|и)',             # abuse
    r'непрозирн(о|ост)',            # non-transparent
    r'конфликт\s+на\s+интерес',     # conflict of interest
    r'еден\s+понудувач',            # single bidder
    r'повторлив(и)?\s+победник',    # repeat winner
    r'ценовн(а|и)\s+аномалиј',      # price anomaly
    r'индикатор(и)?\s+(за|на)\s+корупциј', # corruption indicator(s)
    r'проблематичн(и|а|о)',         # problematic

    # English patterns
    r'suspicious',
    r'corrupt(ion|ed)?',
    r'rigged',
    r'red\s+flag(s)?',
    r'anomal(y|ies|ous)',
    r'fraud(ulent)?',
    r'abuse',
    r'irregular(ity|ities)?',
    r'non-transparent',
    r'conflict\s+of\s+interest',
    r'single\s+bidd(er|ing)',
    r'repeat\s+winner',
    r'price\s+anomal',
    r'corruption\s+indicator',
    r'problematic',
]


# ============================================================================
# SECTION 2: Add this function after existing helper functions (around line 340)
# ============================================================================

def is_corruption_query(question: str) -> bool:
    """
    Detect if the query is asking about corruption, suspicious patterns,
    or red flags in tenders.

    Args:
        question: User's question text

    Returns:
        True if query is corruption-related
    """
    if not question:
        return False

    question_lower = question.lower()

    # Check against all corruption patterns
    for pattern in CORRUPTION_QUERY_PATTERNS:
        if re.search(pattern, question_lower):
            logger.info(f"Detected corruption query (pattern: {pattern})")
            return True

    return False


# ============================================================================
# SECTION 3: Methods to add to RAGQueryPipeline class (before batch_query)
# These are standalone functions that should be converted to methods
# by adding 'self' as first parameter when integrating into the class
# ============================================================================

def translate_flag_type(flag_type: str) -> str:
    """
    Translate flag type from English to Macedonian.

    Args:
        flag_type: English flag type

    Returns:
        Macedonian translation
    """
    translations = {
        'single_bidder': 'Еден понудувач',
        'repeat_winner': 'Повторлив победник',
        'price_anomaly': 'Ценовна аномалија',
        'bid_clustering': 'Кластерирање на понуди',
        'short_deadline': 'Краток рок',
        'high_amendment_count': 'Многу измени на договорот',
        'unusual_timing': 'Необична временска рамка',
        'missing_documentation': 'Недостасува документација',
        'specification_tailoring': 'Насочени спецификации',
        'related_parties': 'Поврзани страни',
        'unrealistic_estimates': 'Нереални проценки',
        'late_qualification': 'Доцна квалификација',
        'high_amendments': 'Многу амандмани',
        'spec_rigging': 'Наместени спецификации',
        'related_companies': 'Поврзани компании',
    }

    return translations.get(flag_type, flag_type.replace('_', ' ').title())


def generate_corruption_response_sync(flagged_tenders: List[Dict]) -> str:
    """
    Generate a comprehensive response about corruption risks in Macedonian.

    Args:
        flagged_tenders: List of tenders with corruption flags

    Returns:
        Formatted response in Macedonian
    """
    total_analyzed = len(flagged_tenders)

    # Severity emoji mapping
    severity_emoji = {
        'critical': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🟢'
    }

    # Build response
    response_parts = []

    # Header
    response_parts.append(
        f"# Анализа на ризик од корупција\n\n"
        f"Анализирав **{total_analyzed} тендери** со високи индикатори за ризик од корупција.\n"
    )

    # Summary statistics
    critical_count = sum(1 for t in flagged_tenders if t.get('max_severity') == 'critical')
    high_count = sum(1 for t in flagged_tenders if t.get('max_severity') == 'high')
    medium_count = sum(1 for t in flagged_tenders if t.get('max_severity') == 'medium')

    response_parts.append(f"\n## Преглед по сериозност:\n")
    if critical_count > 0:
        response_parts.append(f"- 🔴 **Критични**: {critical_count} тендери\n")
    if high_count > 0:
        response_parts.append(f"- 🟠 **Високи**: {high_count} тендери\n")
    if medium_count > 0:
        response_parts.append(f"- 🟡 **Средни**: {medium_count} тендери\n")

    # Top flagged tenders (show top 10)
    response_parts.append(f"\n## Топ ризични тендери:\n\n")

    for i, tender in enumerate(flagged_tenders[:10], 1):
        severity = tender.get('max_severity', 'medium')
        emoji = severity_emoji.get(severity, '🟡')

        tender_id = tender.get('tender_id', 'N/A')
        title = tender.get('title') or 'Без наслов'
        institution = tender.get('institution') or 'N/A'
        winner = tender.get('winner') or 'N/A'
        risk_score = tender.get('total_score', 0)
        flag_count = tender.get('flag_count', 0)

        # Truncate long titles
        if len(title) > 80:
            title = title[:77] + "..."

        response_parts.append(
            f"### {i}. {emoji} {title}\n\n"
            f"- **Тендер ID**: `{tender_id}`\n"
            f"- **Институција**: {institution}\n"
            f"- **Победник**: {winner}\n"
            f"- **Ризик скор**: {risk_score}/100\n"
            f"- **Број на знамиња**: {flag_count}\n"
        )

        # Show flag types
        flags = tender.get('flags', [])
        if flags:
            response_parts.append(f"- **Детектирани проблеми**:\n")
            flag_types_shown = set()
            for flag in flags[:5]:  # Show top 5 flags per tender
                flag_type = flag.get('type', 'unknown') if isinstance(flag, dict) else str(flag)
                flag_severity = flag.get('severity', 'medium') if isinstance(flag, dict) else 'medium'
                flag_score = flag.get('score', 0) if isinstance(flag, dict) else 0

                # Translate flag types to Macedonian
                flag_type_mk = translate_flag_type(flag_type)

                if flag_type not in flag_types_shown:
                    flag_emoji = severity_emoji.get(flag_severity, '🟡')
                    response_parts.append(
                        f"  - {flag_emoji} {flag_type_mk} (скор: {flag_score})\n"
                    )
                    flag_types_shown.add(flag_type)

        response_parts.append("\n")

    # Footer with recommendations
    response_parts.append(
        f"\n## Препораки:\n\n"
        f"1. **Приоритет**: Фокусирајте се на критичните случаи (🔴) првенствено\n"
        f"2. **Анализа**: Детално проверете ги тендерите со повеќе знамиња\n"
        f"3. **Следење**: Следете ги институциите и компаниите со повторливи шеми\n"
        f"4. **Документација**: Зачувајте ги доказите за понатамошна истрага\n\n"
        f"_Ова е автоматска анализа базирана на статистички индикатори. "
        f"Потребна е дополнителна истрага за да се потврди корупција._\n"
    )

    return ''.join(response_parts)


# ============================================================================
# SQL QUERIES for fetching corruption data
# ============================================================================

GET_FLAGGED_TENDERS_QUERY = """
WITH tender_flags AS (
    SELECT
        cf.tender_id,
        COUNT(*) as flag_count,
        SUM(cf.score) as total_score,
        MAX(cf.severity) as max_severity,
        ARRAY_AGG(
            jsonb_build_object(
                'type', cf.flag_type,
                'severity', cf.severity,
                'score', cf.score,
                'evidence', cf.evidence,
                'detected_at', cf.detected_at
            )
        ) as flags
    FROM corruption_flags cf
    WHERE cf.false_positive = FALSE
    GROUP BY cf.tender_id
)
SELECT
    t.tender_id,
    t.title,
    t.procuring_entity,
    t.winner,
    t.estimated_value_mkd,
    t.contract_value_mkd,
    t.status,
    t.published_date,
    tf.flag_count,
    tf.total_score,
    tf.max_severity,
    tf.flags
FROM tender_flags tf
JOIN tenders t ON t.tender_id = tf.tender_id
ORDER BY tf.total_score DESC, tf.flag_count DESC
LIMIT $1
"""

GET_TENDER_RISK_ANALYSIS_QUERY = """
SELECT
    t.tender_id,
    t.title,
    t.procuring_entity,
    t.winner,
    t.estimated_value_mkd,
    t.contract_value_mkd,
    t.num_bidders,
    t.status,
    t.published_date,
    t.deadline,
    t.cpv_code,
    ARRAY_AGG(
        jsonb_build_object(
            'flag_type', cf.flag_type,
            'severity', cf.severity,
            'score', cf.score,
            'evidence', cf.evidence,
            'detected_at', cf.detected_at,
            'reviewed', cf.reviewed,
            'review_notes', cf.review_notes
        )
    ) as flags,
    COUNT(cf.flag_id) as flag_count,
    SUM(cf.score) as total_risk_score
FROM tenders t
LEFT JOIN corruption_flags cf ON t.tender_id = cf.tender_id
    AND cf.false_positive = FALSE
WHERE t.tender_id = $1
GROUP BY t.tender_id
"""

GET_RISKY_INSTITUTIONS_QUERY = """
WITH institution_flags AS (
    SELECT
        t.procuring_entity,
        COUNT(DISTINCT t.tender_id) as total_tenders,
        COUNT(DISTINCT cf.tender_id) as flagged_tenders,
        COUNT(cf.flag_id) as total_flags,
        SUM(cf.score) as total_risk_score,
        AVG(cf.score) as avg_flag_score,
        ARRAY_AGG(DISTINCT cf.flag_type) as flag_types
    FROM tenders t
    LEFT JOIN corruption_flags cf ON t.tender_id = cf.tender_id
        AND cf.false_positive = FALSE
    WHERE t.procuring_entity IS NOT NULL
    GROUP BY t.procuring_entity
    HAVING COUNT(DISTINCT cf.tender_id) > 0
)
SELECT
    procuring_entity,
    total_tenders,
    flagged_tenders,
    ROUND(100.0 * flagged_tenders / NULLIF(total_tenders, 0), 2) as flag_rate,
    total_flags,
    total_risk_score,
    ROUND(avg_flag_score, 2) as avg_flag_score,
    flag_types
FROM institution_flags
ORDER BY total_risk_score DESC, flag_rate DESC
LIMIT $1
"""

GET_RISKY_COMPANIES_QUERY = """
WITH company_flags AS (
    SELECT
        t.winner,
        COUNT(DISTINCT t.tender_id) as total_wins,
        COUNT(DISTINCT cf.tender_id) as flagged_wins,
        COUNT(cf.flag_id) as total_flags,
        SUM(cf.score) as total_risk_score,
        SUM(t.contract_value_mkd) as total_contract_value,
        ARRAY_AGG(DISTINCT cf.flag_type) as flag_types,
        COUNT(DISTINCT t.procuring_entity) as institutions_count
    FROM tenders t
    LEFT JOIN corruption_flags cf ON t.tender_id = cf.tender_id
        AND cf.false_positive = FALSE
    WHERE t.winner IS NOT NULL
        AND (t.status = 'awarded' OR t.status = 'completed')
    GROUP BY t.winner
    HAVING COUNT(DISTINCT cf.tender_id) > 0
)
SELECT
    winner,
    total_wins,
    flagged_wins,
    ROUND(100.0 * flagged_wins / NULLIF(total_wins, 0), 2) as flag_rate,
    total_flags,
    total_risk_score,
    total_contract_value,
    institutions_count,
    flag_types
FROM company_flags
ORDER BY total_risk_score DESC, flag_rate DESC
LIMIT $1
"""


# ============================================================================
# SECTION 4: MODIFICATION to existing generate_answer() method
# Add this check at the very beginning of the generate_answer() method
# (around line 3562, right after the logger.info line)
# ============================================================================

"""
MODIFICATION TO EXISTING generate_answer() METHOD:
==================================================

In the RAGQueryPipeline.generate_answer() method, add this code block right
after line 3562 (after the logger.info statement):

        # Check if this is a corruption-related query
        if is_corruption_query(question):
            logger.info("Routing to corruption query handler...")
            return await self.handle_corruption_query(question, limit=20)

This will route corruption queries to the specialized handler before
attempting the standard LLM-driven agent approach.
"""
