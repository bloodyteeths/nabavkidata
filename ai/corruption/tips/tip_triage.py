"""
Triage anonymous tips by extracting entities, matching to known data, and scoring credibility.

This module analyzes incoming whistleblower tips to:
1. Extract named entities (companies, institutions, people, tender IDs, monetary amounts)
2. Match extracted entities against the procurement database
3. Score tip credibility based on detail richness and specificity
4. Classify urgency and suggest next actions for analysts

The triage score (0-100) drives prioritization in the admin queue.
"""

import re
import logging
import math
from typing import List, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class TipTriageEngine:
    """Analyze and prioritize anonymous corruption tips."""

    # Common entity patterns in Macedonian text
    # Company legal form suffixes/prefixes
    COMPANY_PATTERNS = [
        r'(?:ДООЕЛ|ДОО|АД|ДПТУ)\s+[А-Яа-яЉЊЏљњџЃѓЌќЅѕЏЏ\w\s]{2,40}',
        r'[А-Яа-яЉЊЏљњџЃѓЌќЅѕ\w\s]{2,40}\s+(?:ДООЕЛ|ДОО|АД|ДПТУ)',
        r'"([^"]{2,60})"',  # quoted names
        r'\u201e([^\u201c]{2,60})\u201c',  # Macedonian-style quotes
    ]

    MONEY_PATTERN = r'(\d[\d.,]+)\s*(?:МКД|денари|EUR|евра|евро|\$|долари)'
    TENDER_ID_PATTERN = r'(\d{1,6}/\d{4})'
    DATE_PATTERN = r'(\d{1,2}\.\d{1,2}\.\d{4})'
    PERSON_NAME_PATTERN = r'([А-ЯЉЊЏЃЌЅа-яљњџѓќѕ][а-яљњџѓќѕ]{1,20})\s+([А-ЯЉЊЏЃЌЅа-яљњџѓќѕ][а-яљњџѓќѕ]{1,20}(?:ски|ска|ов|ова|ев|ева|ић|ич)?)'

    # Category-specific keywords for enhanced detection
    CATEGORY_KEYWORDS = {
        'bid_rigging': [
            'договор', 'договорено', 'намештено', 'намештена', 'договорка',
            'ист(?:и|е) понуд', 'идентичн', 'копи', 'ротаци',
            'координирано', 'поделен', 'поделба', 'фиктивн',
        ],
        'bribery': [
            'подмит', 'мито', 'поткуп', 'кеш', 'готовина', 'плати',
            'провизија', 'kickback', 'комисија', 'награда',
        ],
        'conflict_of_interest': [
            'конфликт', 'интерес', 'роднин', 'фамилија', 'сопруг',
            'сопруж', 'брат', 'сестра', 'татко', 'мајка', 'син',
            'ќерка', 'свршен', 'поврзан', 'сопственик', 'директор',
        ],
        'fraud': [
            'измама', 'фалсификат', 'лажн', 'невистинит', 'документ',
            'фактур', 'понуд', 'сертификат', 'лиценц', 'нелегалн',
        ],
    }

    # High-urgency keywords that boost triage score
    HIGH_URGENCY_KEYWORDS = [
        'итно', 'веднаш', 'сега', 'тековно', 'во тек',
        'рок', 'истекува', 'милион', 'корупција', 'криминал',
    ]

    async def triage(self, pool, description: str, category: str = 'general',
                     evidence_urls: List[str] = None) -> dict:
        """Analyze a tip and produce triage results.

        Args:
            pool: asyncpg connection pool
            description: The tip text submitted by the whistleblower
            category: Corruption category (bid_rigging, bribery, conflict_of_interest, fraud, other)
            evidence_urls: Optional list of URLs pointing to evidence

        Returns:
            dict with triage_score, urgency, extracted_entities, matched_tender_ids,
            matched_entity_ids, category_analysis, suggested_actions,
            detail_richness, specificity_score
        """
        if evidence_urls is None:
            evidence_urls = []

        # 1. Extract entities from text
        entities = self._extract_entities(description)

        # 2. Extract tender IDs, monetary amounts, dates
        tender_ids = re.findall(self.TENDER_ID_PATTERN, description)
        amounts = re.findall(self.MONEY_PATTERN, description)
        dates = re.findall(self.DATE_PATTERN, description)

        # 3. Match entities against known companies/institutions in DB
        matched_tenders, matched_entities = await self._match_to_database(
            pool, entities, tender_ids)

        # 4. Score credibility based on specificity
        detail_richness = self._score_detail_richness(
            description, entities, tender_ids, amounts, dates, evidence_urls)

        specificity = self._score_specificity(
            matched_tenders, matched_entities, amounts, dates)

        # 5. Compute overall triage score
        triage_score = self._compute_triage_score(
            detail_richness, specificity, len(matched_tenders),
            len(matched_entities), len(evidence_urls), category)

        # 6. Determine urgency
        urgency = self._classify_urgency(triage_score, category, amounts)

        # 7. Suggest actions
        suggestions = self._suggest_actions(
            matched_tenders, matched_entities, category, triage_score)

        return {
            'triage_score': round(triage_score, 1),
            'urgency': urgency,
            'extracted_entities': entities,
            'matched_tender_ids': matched_tenders,
            'matched_entity_ids': matched_entities,
            'category_analysis': self._analyze_category(category, description),
            'suggested_actions': suggestions,
            'detail_richness': round(detail_richness, 2),
            'specificity_score': round(specificity, 2),
        }

    def _extract_entities(self, text: str) -> List[dict]:
        """Extract company names, institution names, person names from text.

        Uses regex-based NER tailored for Macedonian procurement text.
        Returns a deduplicated list of entity dicts.
        """
        entities = []
        seen = set()

        # Extract company names (with Macedonian legal forms)
        for pattern in self.COMPANY_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                name = match.group(1) if match.lastindex else match.group(0)
                name = name.strip().strip('"').strip()
                if len(name) < 3 or name.lower() in seen:
                    continue
                seen.add(name.lower())
                entities.append({
                    'name': name,
                    'type': 'company',
                })

        # Extract person names (Cyrillic first-last name pairs)
        for match in re.finditer(self.PERSON_NAME_PATTERN, text):
            full_name = f"{match.group(1)} {match.group(2)}"
            if full_name.lower() in seen:
                continue
            # Filter out common Macedonian words that match the pattern
            stop_words = {
                'на', 'за', 'со', 'од', 'не', 'да', 'во', 'ке', 'се',
                'ова', 'тоа', 'тие', 'ние', 'вие', 'што', 'кои', 'или',
            }
            first_lower = match.group(1).lower()
            second_lower = match.group(2).lower()
            if first_lower in stop_words or second_lower in stop_words:
                continue
            # Person names should start with uppercase
            if not match.group(1)[0].isupper() or not match.group(2)[0].isupper():
                continue
            seen.add(full_name.lower())
            entities.append({
                'name': full_name,
                'type': 'person',
            })

        # Extract institution names -- common Macedonian government entity patterns
        institution_patterns = [
            r'(?:Општина|Министерство|Агенција|Фонд|Дирекција|Управа|Совет|Влада|Собрание)\s+(?:за\s+|на\s+)?[А-Яа-яЉЊЏљњџЃѓЌќЅѕ\w\s]{2,50}',
            r'(?:ЈП|ЈЗУ|ЈОУДГ|ЈКП|АД)\s+[А-Яа-яЉЊЏљњџЃѓЌќЅѕ\w\s\-]{2,50}',
        ]
        for pattern in institution_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                name = match.group(0).strip()
                if len(name) < 4 or name.lower() in seen:
                    continue
                seen.add(name.lower())
                entities.append({
                    'name': name,
                    'type': 'institution',
                })

        return entities

    async def _match_to_database(self, pool, entities: List[dict],
                                  tender_ids: List[str]) -> Tuple[List[str], List[str]]:
        """Match extracted entities and tender IDs to database records.

        Queries the tenders table for:
        - Exact tender_id matches
        - Fuzzy matches on contracting_authority and winner columns

        Returns:
            (matched_tender_ids, matched_entity_names)
        """
        matched_tenders = []
        matched_entities = []

        try:
            async with pool.acquire() as conn:
                # Match tender IDs directly
                if tender_ids:
                    rows = await conn.fetch(
                        """
                        SELECT DISTINCT tender_id
                        FROM tenders
                        WHERE tender_id = ANY($1::text[])
                        """,
                        tender_ids
                    )
                    matched_tenders = [row['tender_id'] for row in rows]

                # Match entity names against contracting_authority and winner
                company_and_inst_names = [
                    e['name'] for e in entities
                    if e['type'] in ('company', 'institution')
                ]

                for name in company_and_inst_names:
                    # Use ILIKE for case-insensitive partial matching
                    search_term = f"%{name}%"
                    row = await conn.fetchrow(
                        """
                        SELECT
                            COALESCE(
                                (SELECT contracting_authority FROM tenders
                                 WHERE contracting_authority ILIKE $1 LIMIT 1),
                                (SELECT winner FROM tenders
                                 WHERE winner ILIKE $1 LIMIT 1)
                            ) AS matched_name
                        """,
                        search_term
                    )
                    if row and row['matched_name']:
                        matched_entities.append(row['matched_name'])

                    # If the entity was not found in the text columns,
                    # also try tender_id lookups from tenders mentioning
                    # those entities
                    if name not in matched_entities:
                        extra_tenders = await conn.fetch(
                            """
                            SELECT DISTINCT tender_id FROM tenders
                            WHERE contracting_authority ILIKE $1
                               OR winner ILIKE $1
                            LIMIT 5
                            """,
                            search_term
                        )
                        for r in extra_tenders:
                            if r['tender_id'] not in matched_tenders:
                                matched_tenders.append(r['tender_id'])

        except Exception as e:
            logger.error(f"Database matching failed: {e}")
            # Return whatever we matched so far; don't crash triage

        return matched_tenders, matched_entities

    def _score_detail_richness(self, text: str, entities: List[dict],
                                tender_ids: List[str], amounts: List[str],
                                dates: List[str],
                                evidence_urls: List[str]) -> float:
        """Score how detailed the tip is (0-1).

        Factors:
        - Text length (longer = richer, with diminishing returns)
        - Number of unique entities mentioned
        - Specific tender IDs referenced
        - Monetary amounts cited
        - Dates mentioned
        - Evidence URLs provided
        """
        score = 0.0

        # Text length: logarithmic scale, max 0.25 at ~1000 chars
        if len(text) > 0:
            length_score = min(math.log(len(text) + 1) / math.log(1001), 1.0)
            score += 0.25 * length_score

        # Entity count: each entity up to 5 adds 0.03
        entity_score = min(len(entities) * 0.2, 1.0)
        score += 0.20 * entity_score

        # Tender IDs: very specific, high value
        tender_score = min(len(tender_ids) * 0.5, 1.0)
        score += 0.20 * tender_score

        # Monetary amounts: adds specificity
        amount_score = min(len(amounts) * 0.5, 1.0)
        score += 0.10 * amount_score

        # Dates: timeline adds credibility
        date_score = min(len(dates) * 0.33, 1.0)
        score += 0.10 * date_score

        # Evidence URLs: external proof
        evidence_score = min(len(evidence_urls) * 0.5, 1.0)
        score += 0.15 * evidence_score

        return min(score, 1.0)

    def _score_specificity(self, matched_tenders: List[str],
                            matched_entities: List[str],
                            amounts: List[str],
                            dates: List[str]) -> float:
        """Score how specific and verifiable the tip is (0-1).

        High specificity means the tip references real entities found in our database.
        This is the strongest credibility signal.
        """
        score = 0.0

        # Matched tenders in database: strongest signal
        if matched_tenders:
            tender_factor = min(len(matched_tenders) * 0.3, 1.0)
            score += 0.40 * tender_factor

        # Matched entity names in database
        if matched_entities:
            entity_factor = min(len(matched_entities) * 0.25, 1.0)
            score += 0.30 * entity_factor

        # Specific monetary amounts (verifiable)
        if amounts:
            score += 0.15 * min(len(amounts) * 0.5, 1.0)

        # Specific dates (verifiable timeline)
        if dates:
            score += 0.15 * min(len(dates) * 0.33, 1.0)

        return min(score, 1.0)

    def _compute_triage_score(self, detail_richness: float, specificity: float,
                               num_matched_tenders: int,
                               num_matched_entities: int,
                               num_evidence: int, category: str) -> float:
        """Compute overall triage score 0-100.

        Weighted formula:
        - 35% detail richness
        - 40% specificity (most important -- verifiable claims)
        - 15% evidence bonus
        - 10% category bonus (known high-risk categories score higher)
        """
        # Base score from detail and specificity
        base = (0.35 * detail_richness + 0.40 * specificity) * 100

        # Evidence bonus: each URL up to 3 adds points
        evidence_bonus = min(num_evidence, 3) * 5.0  # max 15

        # Category bonus: certain categories are inherently higher priority
        category_bonuses = {
            'bid_rigging': 8.0,
            'bribery': 7.0,
            'conflict_of_interest': 6.0,
            'fraud': 7.0,
            'other': 0.0,
            'general': 0.0,
        }
        cat_bonus = category_bonuses.get(category, 0.0)

        # Matched data bonus: verified connections to real data
        match_bonus = min(num_matched_tenders * 3.0 + num_matched_entities * 2.0, 15.0)

        total = base + evidence_bonus + cat_bonus + match_bonus

        # Clamp to 0-100
        return max(0.0, min(total, 100.0))

    def _classify_urgency(self, triage_score: float, category: str,
                           amounts: List[str]) -> str:
        """Classify urgency: low, medium, high, critical.

        Based on triage score thresholds, with category and amount overrides.
        """
        # Parse amounts to check for large sums
        has_large_amount = False
        for amount_str in amounts:
            try:
                cleaned = amount_str.replace('.', '').replace(',', '.')
                value = float(cleaned)
                # Over 1 million MKD or 50k EUR is considered large
                if value >= 1_000_000 or value >= 50_000:
                    has_large_amount = True
                    break
            except (ValueError, TypeError):
                continue

        # Score-based classification
        if triage_score >= 75:
            urgency = 'critical'
        elif triage_score >= 55:
            urgency = 'high'
        elif triage_score >= 30:
            urgency = 'medium'
        else:
            urgency = 'low'

        # Override: large amounts or bribery bump up urgency by one level
        if has_large_amount or category == 'bribery':
            upgrade_map = {
                'low': 'medium',
                'medium': 'high',
                'high': 'critical',
                'critical': 'critical',
            }
            urgency = upgrade_map[urgency]

        return urgency

    def _suggest_actions(self, matched_tenders: List[str],
                          matched_entities: List[str],
                          category: str, score: float) -> List[str]:
        """Generate suggested next actions for analysts."""
        actions = []

        # Always suggest initial review
        if score >= 50:
            actions.append('Prioritize for immediate analyst review')
        else:
            actions.append('Queue for standard review')

        # Tender-specific actions
        if matched_tenders:
            tender_list = ', '.join(matched_tenders[:5])
            actions.append(
                f'Cross-reference with tender records: {tender_list}'
            )
            actions.append('Run corruption risk analysis on matched tenders')

        # Entity-specific actions
        if matched_entities:
            entity_list = ', '.join(matched_entities[:3])
            actions.append(
                f'Investigate entity profiles: {entity_list}'
            )
            actions.append('Check for related flagged tenders involving these entities')

        # Category-specific actions
        if category == 'bid_rigging':
            actions.append('Run collusion detection analysis on mentioned companies')
            actions.append('Check bid patterns for identical or clustered bids')
        elif category == 'bribery':
            actions.append('Flag for anti-corruption unit review')
            actions.append('Check financial transaction patterns if available')
        elif category == 'conflict_of_interest':
            actions.append('Check ownership/management connections between entities')
            actions.append('Verify declared conflicts of interest in tender records')
        elif category == 'fraud':
            actions.append('Verify document authenticity for referenced tenders')
            actions.append('Cross-check entity certifications and licenses')

        # Evidence follow-up
        if score >= 30:
            actions.append('Request additional evidence if whistleblower checks back')

        # High-score escalation
        if score >= 75:
            actions.append('Consider escalation to State Commission for Prevention of Corruption')

        return actions

    def _analyze_category(self, category: str, text: str) -> str:
        """Brief analysis based on category, including keyword matching.

        Returns a human-readable summary of how the tip relates to its category.
        """
        text_lower = text.lower()

        # Count category-specific keyword matches
        keywords = self.CATEGORY_KEYWORDS.get(category, [])
        matched_keywords = []
        for kw in keywords:
            if re.search(kw, text_lower):
                matched_keywords.append(kw)

        # Count high-urgency keywords
        urgency_matches = []
        for kw in self.HIGH_URGENCY_KEYWORDS:
            if kw in text_lower:
                urgency_matches.append(kw)

        # Build analysis text
        category_labels = {
            'bid_rigging': 'Bid Rigging / Tender Manipulation',
            'bribery': 'Bribery / Corruption Payments',
            'conflict_of_interest': 'Conflict of Interest',
            'fraud': 'Fraud / Document Falsification',
            'other': 'General / Uncategorized',
            'general': 'General / Uncategorized',
        }

        label = category_labels.get(category, 'Unknown Category')
        parts = [f"Category: {label}."]

        if matched_keywords:
            parts.append(
                f"Found {len(matched_keywords)} category-relevant keyword(s) in the tip text, "
                f"supporting the {category} classification."
            )
        else:
            parts.append(
                f"No strong category-specific keywords detected. "
                f"The '{category}' classification is based on submitter selection."
            )

        if urgency_matches:
            parts.append(
                f"Urgency indicators present: tip contains {len(urgency_matches)} "
                f"time-sensitive or severity-related keyword(s)."
            )

        # Text complexity assessment
        word_count = len(text.split())
        if word_count >= 200:
            parts.append("The tip is highly detailed with a substantial narrative.")
        elif word_count >= 80:
            parts.append("The tip provides a moderate level of detail.")
        elif word_count >= 30:
            parts.append("The tip is brief but contains some actionable information.")
        else:
            parts.append("The tip is very brief; additional details would strengthen the case.")

        return ' '.join(parts)
