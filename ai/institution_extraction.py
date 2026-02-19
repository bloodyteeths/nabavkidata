"""
Institution name extraction functions for RAG query system.
These functions extract and normalize institution names from user queries.
"""

from typing import List, Dict, Optional
import re
import logging

logger = logging.getLogger(__name__)


def extract_institution_names(question: str, conversation_history: Optional[List[Dict]] = None) -> List[str]:
    """
    Extract institution/procuring entity names from user question.

    Handles:
    - Macedonian and English institution names
    - Common variations and abbreviations
    - Pronoun references to previously mentioned institutions

    Returns:
        List of institution name patterns to match against procuring_entity column
    """
    question_lower = question.lower()
    institutions = []

    # Check conversation history for institution context (pronoun resolution)
    if conversation_history:
        for turn in conversation_history[-3:]:  # Last 3 messages
            content = ""
            if 'question' in turn:
                content = str(turn.get('question', '')).lower()
            elif 'content' in turn and turn.get('role') == 'user':
                content = str(turn.get('content', '')).lower()

            # Extract institutions from previous messages
            if content:
                for pattern in get_institution_patterns():
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        # User is referring to this institution with pronouns
                        if any(word in question_lower for word in ['нивни', 'нивните', 'their', 'тие', 'they', 'it', 'тоа']):
                            institutions.extend(matches)

    # Direct institution mentions in current question
    for pattern in get_institution_patterns():
        matches = re.findall(pattern, question_lower, re.IGNORECASE)
        institutions.extend(matches)

    # Common institution keywords to expand
    institution_expansions = {
        'здравство': ['министерство за здравство', 'ministry of health', 'мз'],
        'ministry of health': ['министерство за здравство', 'здравство', 'мз'],
        'универзитет': ['универзитет', 'university', 'факултет'],
        'university': ['универзитет', 'универзитетск', 'university'],
        'болница': ['болница', 'hospital', 'клиника', 'клинички'],
        'hospital': ['болница', 'hospital', 'клиника', 'клинички'],
        'општина': ['општина', 'municipality', 'град'],
        'municipality': ['општина', 'municipality'],
        'скопје': ['скопје', 'skopje', 'град скопје'],
        'skopje': ['скопје', 'skopje', 'град скопје'],
        'министерство': ['министерство', 'ministry'],
        'ministry': ['министерство', 'ministry'],
        'агенција': ['агенција', 'agency'],
        'agency': ['агенција', 'agency'],
    }

    # Expand institution keywords
    expanded = []
    for inst in institutions:
        inst_lower = inst.lower()
        expanded.append(inst)
        for keyword, expansions in institution_expansions.items():
            if keyword in inst_lower:
                expanded.extend(expansions)

    # Deduplicate
    unique_institutions = list(dict.fromkeys(expanded))

    if unique_institutions:
        logger.info(f"Extracted institutions: {unique_institutions}")

    return unique_institutions


def get_institution_patterns() -> List[str]:
    """
    Get regex patterns for matching institution names in text.

    Returns:
        List of regex patterns for common institution types
    """
    return [
        # Ministries
        r'министерство\s+(?:за\s+)?[\wа-яѓѕјљњќџ\s]+',
        r'ministry\s+of\s+[\w\s]+',
        r'\bмз\b|\bмф\b|\bмвр\b|\bмтсп\b',  # Common abbreviations

        # Municipalities
        r'општина\s+[\wа-яѓѕјљњќџ\s]+',
        r'municipality\s+of\s+[\w\s]+',
        r'град\s+[\wа-яѓѕјљњќџ]+',
        r'city\s+of\s+\w+',

        # Hospitals/Healthcare
        r'[\wа-яѓѕјљњќџ\s]*болница[\wа-яѓѕјљњќџ\s]*',
        r'[\w\s]*hospital[\w\s]*',
        r'клиника[\wа-яѓѕјљњќџ\s]*',
        r'клинички\s+центар[\wа-яѓѕјљњќџ\s]*',
        r'здравствен\s+дом[\wа-яѓѕјљњќџ\s]*',

        # Universities/Schools
        r'универзитет[\wа-яѓѕјљњќџ\s]*',
        r'university[\w\s]*',
        r'факултет[\wа-яѓѕјљњќџ\s]*',
        r'faculty\s+of\s+[\w\s]+',
        r'оо?у\s+[„"]?[\wа-яѓѕјљњќџ\s]+[„"]?',  # Schools

        # Agencies
        r'агенција\s+(?:за\s+)?[\wа-яѓѕјљњќџ\s]+',
        r'agency\s+(?:for\s+)?[\w\s]+',

        # Other public institutions
        r'јавно\s+претпријатие[\wа-яѓѕјљњќџ\s]*',
        r'јп\s+[\wа-яѓѕјљњќџ\s]+',
        r'public\s+enterprise[\w\s]*',
    ]
