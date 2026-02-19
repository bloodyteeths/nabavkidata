"""
Follow-up Question Handler for RAG Query Pipeline

Handles conversational context to support follow-up questions like:
- "А за минатата година?" (And for last year?)
- "Покажи ми повеќе" (Show me more)
- "Што со 2023?" (What about 2023?)
"""

import re
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ============================================================================
# FOLLOW-UP QUESTION HANDLING
# ============================================================================

class FollowUpDetector:
    """
    Detects follow-up questions that require context from previous queries.

    Follow-up patterns:
    - "А за минатата година?" (And for last year?)
    - "Покажи ми повеќе" (Show me more)
    - "Што со 2023?" (What about 2023?)
    - "Исто но за..." (Same but for...)
    """

    # Patterns that indicate follow-up questions
    FOLLOWUP_PATTERNS = [
        # Macedonian - temporal shifts
        (r'^а\s+(за|во)', 'time_shift'),  # "А за..." (And for...)
        (r'минатата\s+година', 'time_shift'),  # Last year
        (r'оваа\s+година', 'time_shift'),  # This year
        (r'претходната', 'time_shift'),  # Previous one
        (r'следната', 'time_shift'),  # Next one
        (r'што\s+со\s+20\d{2}', 'time_shift'),  # What about 2023/2024
        (r'за\s+20\d{2}', 'time_shift'),  # For 2023/2024

        # Macedonian - more results
        (r'покажи.*повеќе', 'more_results'),  # Show more
        (r'уште\s+примери', 'more_results'),  # More examples
        (r'повеќе\s+(резултати|детали|информации)', 'more_results'),
        (r'^повеќе', 'more_results'),  # Just "more"

        # Macedonian - detail requests
        (r'детали\s+за', 'detail_request'),  # Details about
        (r'кажи\s+ми\s+повеќе\s+за', 'detail_request'),  # Tell me more about
        (r'што\s+е\s+со', 'detail_request'),  # What about

        # Macedonian - comparison
        (r'спореди\s+со', 'comparison'),  # Compare with
        (r'исто\s+(така|но)', 'comparison'),  # Same but/also
        (r'за\s+истата', 'comparison'),  # For the same

        # English - temporal shifts
        (r'^and\s+(for|in)', 'time_shift'),
        (r'last\s+year', 'time_shift'),
        (r'this\s+year', 'time_shift'),
        (r'previous', 'time_shift'),
        (r'next', 'time_shift'),
        (r'what\s+about\s+20\d{2}', 'time_shift'),

        # English - more results
        (r'show\s+more', 'more_results'),
        (r'more\s+(results|examples|details)', 'more_results'),
        (r'^more', 'more_results'),

        # English - detail requests
        (r'details?\s+(about|for)', 'detail_request'),
        (r'tell\s+me\s+more\s+about', 'detail_request'),

        # English - comparison
        (r'compare\s+(with|to)', 'comparison'),
        (r'same\s+but', 'comparison'),
        (r'also\s+for', 'comparison'),
    ]

    def is_followup(self, question: str) -> bool:
        """
        Check if question is a follow-up.

        Args:
            question: User's question

        Returns:
            True if this is a follow-up question
        """
        if not question:
            return False

        question_lower = question.lower().strip()

        # Short questions starting with certain patterns are likely follow-ups
        if len(question.split()) <= 5:
            for pattern, _ in self.FOLLOWUP_PATTERNS:
                if re.search(pattern, question_lower):
                    return True

        # Longer questions with follow-up indicators
        for pattern, _ in self.FOLLOWUP_PATTERNS:
            if re.search(pattern, question_lower):
                return True

        return False

    def get_followup_type(self, question: str) -> str:
        """
        Determine the type of follow-up question.

        Args:
            question: User's question

        Returns:
            One of: 'time_shift', 'more_results', 'detail_request', 'comparison', 'none'
        """
        if not question:
            return 'none'

        question_lower = question.lower().strip()

        for pattern, followup_type in self.FOLLOWUP_PATTERNS:
            if re.search(pattern, question_lower):
                return followup_type

        return 'none'


class QueryModifier:
    """
    Modifies queries based on follow-up question type.

    Handles:
    - Time shifts (last year, 2023, etc.)
    - More results (increase limit)
    - Detail requests (focus on specific entity)
    """

    def apply_time_shift(self, original_query: dict, question: str) -> dict:
        """
        Modify query for different time period.

        Args:
            original_query: The last successful query
            question: Current follow-up question

        Returns:
            Modified query with new time period
        """
        modified = original_query.copy()
        question_lower = question.lower()
        now = datetime.now()

        # Extract year from question
        year_match = re.search(r'\b(20\d{2})\b', question)
        if year_match:
            year = int(year_match.group(1))
            modified['date_from'] = f'{year}-01-01'
            modified['date_to'] = f'{year}-12-31'
            logger.info(f"[FOLLOWUP] Time shift to year {year}")
            return modified

        # "Last year" / "минатата година"
        if 'last year' in question_lower or 'минатата година' in question_lower:
            last_year = now.year - 1
            modified['date_from'] = f'{last_year}-01-01'
            modified['date_to'] = f'{last_year}-12-31'
            logger.info(f"[FOLLOWUP] Time shift to last year ({last_year})")
            return modified

        # "This year" / "оваа година"
        if 'this year' in question_lower or 'оваа година' in question_lower:
            modified['date_from'] = f'{now.year}-01-01'
            modified['date_to'] = f'{now.year}-12-31'
            logger.info(f"[FOLLOWUP] Time shift to this year ({now.year})")
            return modified

        # "Previous" / "претходната" - shift back one time period
        if 'previous' in question_lower or 'претходна' in question_lower:
            # If we have date filters, shift them back by same duration
            if 'date_from' in original_query and 'date_to' in original_query:
                try:
                    from_date = datetime.strptime(original_query['date_from'], '%Y-%m-%d')
                    to_date = datetime.strptime(original_query['date_to'], '%Y-%m-%d')
                    duration = to_date - from_date

                    new_to = from_date - timedelta(days=1)
                    new_from = new_to - duration

                    modified['date_from'] = new_from.strftime('%Y-%m-%d')
                    modified['date_to'] = new_to.strftime('%Y-%m-%d')
                    logger.info(f"[FOLLOWUP] Time shift to previous period: {modified['date_from']} to {modified['date_to']}")
                except Exception as e:
                    logger.warning(f"Failed to shift time period: {e}")

        return modified

    def increase_limit(self, original_query: dict, factor: int = 2) -> dict:
        """
        Increase result limit for 'show more' requests.

        Args:
            original_query: The last successful query
            factor: Multiplication factor for limit

        Returns:
            Modified query with increased limit
        """
        modified = original_query.copy()

        # Increase LIMIT in tool arguments
        # Most tools default to 15-20 results
        current_limit = modified.get('limit', 15)
        new_limit = min(current_limit * factor, 50)  # Cap at 50
        modified['limit'] = new_limit

        logger.info(f"[FOLLOWUP] Increasing limit from {current_limit} to {new_limit}")
        return modified

    def add_detail_fields(self, original_query: dict) -> dict:
        """
        Request more detailed information.

        Args:
            original_query: The last successful query

        Returns:
            Modified query requesting additional fields
        """
        modified = original_query.copy()
        modified['include_details'] = True
        logger.info(f"[FOLLOWUP] Adding detail fields to query")
        return modified


class LastQueryContext:
    """
    Stores context from the last successful query for follow-up handling.

    This is a simple in-memory storage. For production, consider:
    - Redis for distributed systems
    - Database for persistence
    - Session-based storage
    """

    def __init__(self):
        self._storage = {}  # user_id or session_id -> query context

    def store(self, session_id: str, context: dict):
        """
        Store query context for future follow-ups.

        Args:
            session_id: User/session identifier
            context: Dict with keys: tool_calls, result_count, timestamp
        """
        context['timestamp'] = datetime.now()
        self._storage[session_id] = context
        logger.info(f"[FOLLOWUP] Stored context for session {session_id}: {len(context.get('tool_calls', []))} tools")

    def get(self, session_id: str) -> Optional[dict]:
        """
        Retrieve last query context.

        Args:
            session_id: User/session identifier

        Returns:
            Query context dict or None
        """
        context = self._storage.get(session_id)
        if context:
            # Check if context is still fresh (within last 30 minutes)
            age = datetime.now() - context['timestamp']
            if age.total_seconds() > 1800:  # 30 minutes
                logger.info(f"[FOLLOWUP] Context too old ({age}), ignoring")
                return None
        return context

    def clear(self, session_id: str):
        """Clear context for session."""
        if session_id in self._storage:
            del self._storage[session_id]
            logger.info(f"[FOLLOWUP] Cleared context for session {session_id}")
