"""
Named Entity Recognition for Macedonian Procurement Documents

Extracts entities from tender document text using a two-pass approach:
1. Fast regex pass: monetary amounts, dates, legal references, tax IDs, IBANs
2. Gemini API pass: person names, organization names, locations

Entity Types:
- PERSON: Names of individuals (decision makers, representatives)
- ORG: Organization/company names
- MONEY: Monetary amounts (MKD, EUR, USD)
- DATE: Dates and time periods
- GPE: Geographic/political entities (cities, countries)
- TAX_ID: Company tax identifiers (EMBS, EDB)
- LEGAL_REF: Legal references (law numbers, regulations)
- IBAN: International Bank Account Numbers

Two-pass design:
- Regex pass is fast, deterministic, and free (for structured entities)
- LLM pass uses Gemini API for contextual entity extraction (names, orgs)
  and is only used in batch mode to control costs

Author: nabavkidata.com
License: Proprietary
"""

import re
import os
import json
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Entity:
    """A single extracted entity mention."""
    text: str
    type: str  # PERSON, ORG, MONEY, DATE, GPE, TAX_ID, LEGAL_REF, IBAN
    start: int = 0
    end: int = 0
    confidence: float = 1.0
    method: str = 'regex'  # 'regex' or 'llm'
    normalized: Optional[str] = None
    context: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractionResult:
    """Result of entity extraction from a document."""
    entities: List[Entity] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    text_length: int = 0
    method: str = 'regex'
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'entities': [e.to_dict() for e in self.entities],
            'summary': self.summary,
            'text_length': self.text_length,
            'method': self.method,
            'error': self.error,
        }


# ============================================================================
# COMPANY NAME SUFFIXES (for normalization)
# ============================================================================

# Macedonian company type suffixes to strip during normalization
COMPANY_SUFFIXES = [
    'ДООЕЛ', 'дооел', 'Дооел',
    'ДОО', 'доо', 'Доо',
    'АД', 'ад', 'Ад',
    'ДПТУ', 'дпту', 'Дпту',
    'ДПТУУ', 'дптуу',
    'ТП', 'тп', 'Тп',
    'ЈП', 'јп',
    'ЈПКД', 'јпкд',
    'ООД', 'оод',
    'ЛТД', 'лтд',
    'Ltd', 'LTD', 'ltd',
    'LLC', 'llc',
    'DOO', 'doo',
    'DOOEL', 'dooel',
    'AD', 'ad',
    'JSC', 'jsc',
    'SHPK', 'shpk',
    'SH.P.K.', 'sh.p.k.',
]

# Macedonian city names (for GPE detection in regex pass)
MACEDONIAN_CITIES = [
    'Скопје', 'Битола', 'Куманово', 'Прилеп', 'Тетово', 'Велес',
    'Охрид', 'Штип', 'Гостивар', 'Кочани', 'Струмица', 'Кавадарци',
    'Кичево', 'Гевгелија', 'Струга', 'Радовиш', 'Свети Николе',
    'Неготино', 'Делчево', 'Виница', 'Дебар', 'Крива Паланка',
    'Берово', 'Пробиштип', 'Ресен', 'Демир Хисар', 'Македонски Брод',
    'Валандово', 'Богданци', 'Крушево', 'Пехчево', 'Македонска Каменица',
    'Дебар', 'Кратово',
]

# Macedonian month names (for date regex)
MK_MONTHS = {
    'јануари': 1, 'февруари': 2, 'март': 3, 'април': 4,
    'мај': 5, 'јуни': 6, 'јули': 7, 'август': 8,
    'септември': 9, 'октомври': 10, 'ноември': 11, 'декември': 12,
}


# ============================================================================
# MAIN NER EXTRACTOR CLASS
# ============================================================================

class MacedonianNERExtractor:
    """
    Named Entity Recognition for Macedonian procurement documents.

    Uses a two-pass approach:
    1. Fast regex pass for structured entities (money, dates, tax IDs, etc.)
    2. Optional Gemini LLM pass for contextual entities (person names, orgs)

    Usage:
        extractor = MacedonianNERExtractor()

        # Regex-only extraction (fast, free)
        result = extractor.extract_entities(text, use_llm=False)

        # Full extraction with LLM (slower, costs API credits)
        result = await extractor.extract_entities(text, use_llm=True)
    """

    def __init__(self):
        self.patterns = self._compile_patterns()
        self._gemini_model = None

    # ========================================================================
    # REGEX PATTERNS
    # ========================================================================

    def _compile_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Compile all regex patterns for entity extraction."""
        patterns = {}

        # MONEY patterns - Macedonian denars, EUR, USD
        patterns['MONEY'] = [
            # "1,234,567.89 денари" or "1.234.567,89 ден."
            re.compile(
                r'(\d[\d.,]{0,20})\s*(денари|ден\.?|МКД|MKD)',
                re.UNICODE
            ),
            # EUR amounts
            re.compile(
                r'(\d[\d.,]{0,20})\s*(евра|EUR|€|еур)',
                re.UNICODE
            ),
            # USD amounts
            re.compile(
                r'(\d[\d.,]{0,20})\s*(долари|USD|\$|долар)',
                re.UNICODE
            ),
            # Currency before number
            re.compile(
                r'(EUR|€|\$|МКД|MKD)\s*(\d[\d.,]{0,20})',
                re.UNICODE
            ),
        ]

        # DATE patterns
        patterns['DATE'] = [
            # DD.MM.YYYY or DD/MM/YYYY
            re.compile(
                r'(\d{1,2})[./](\d{1,2})[./](\d{4})',
                re.UNICODE
            ),
            # YYYY-MM-DD (ISO format)
            re.compile(
                r'(\d{4})-(\d{1,2})-(\d{1,2})',
                re.UNICODE
            ),
            # "15 јануари 2024" (Macedonian month names)
            re.compile(
                r'(\d{1,2})\s*(?:\.?\s*)'
                r'(јануари|февруари|март|април|мај|јуни|јули|август'
                r'|септември|октомври|ноември|декември)'
                r'\s*(\d{4})',
                re.UNICODE | re.IGNORECASE
            ),
        ]

        # TAX_ID patterns
        patterns['TAX_ID'] = [
            # EMBS: 7-digit company registration number
            re.compile(
                r'ЕМБС[:\s]*(\d{7})',
                re.UNICODE
            ),
            re.compile(
                r'EMBS[:\s]*(\d{7})',
                re.UNICODE | re.IGNORECASE
            ),
            # EDB: tax identification number (2 letters + 7 digits + sometimes check digits)
            re.compile(
                r'ЕДБ[:\s]*([А-Я]{2}\d{7,13})',
                re.UNICODE
            ),
            re.compile(
                r'EDB[:\s]*([A-Z]{2}\d{7,13})',
                re.UNICODE | re.IGNORECASE
            ),
            # Standalone 13-digit Macedonian tax number (e.g. MK1234567890123)
            # Negative lookbehind for IBAN context (MK + 2digits + space/digits)
            re.compile(
                r'(?:МК|MK)(\d{13})(?!\s?\d{4})',
                re.UNICODE
            ),
        ]

        # LEGAL_REF patterns
        patterns['LEGAL_REF'] = [
            # "Закон за јавни набавки" and similar
            re.compile(
                r'Закон\s+за\s+[\w\s]{3,60}',
                re.UNICODE
            ),
            # "Службен весник на РМ/РСМ бр. 24/2019"
            re.compile(
                r'Службен\s+весник\s+(?:на\s+)?(?:РМ|РСМ|Република\s+(?:Северна\s+)?Македонија)'
                r'[,\s]*(?:бр\.?\s*\d+[/\d]*)',
                re.UNICODE
            ),
            # Article references: "член 62 став 1"
            re.compile(
                r'(?:член|чл\.?)\s*\d+(?:\s*(?:став|ст\.?)\s*\d+)?'
                r'(?:\s*(?:точка|т\.?)\s*\d+)?',
                re.UNICODE | re.IGNORECASE
            ),
            # Numbered decisions: "Одлука бр. 02-1234/2024"
            re.compile(
                r'(?:Одлука|Решение|Известување)\s+(?:бр\.?\s*)?[\d\-/]+',
                re.UNICODE
            ),
        ]

        # IBAN patterns
        patterns['IBAN'] = [
            re.compile(
                r'[A-Z]{2}\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{2,4}',
                re.UNICODE
            ),
            # Macedonian IBAN: MK07 ...
            re.compile(
                r'MK\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{2}',
                re.UNICODE
            ),
        ]

        # GPE patterns (city names in context)
        # Built from MACEDONIAN_CITIES list
        city_pattern = '|'.join(re.escape(city) for city in MACEDONIAN_CITIES)
        patterns['GPE'] = [
            re.compile(
                rf'(?:во|од|за|Општина|општина|град|Град)\s+({city_pattern})',
                re.UNICODE
            ),
            # Standalone city names preceded by common prepositions or comma
            re.compile(
                rf'(?:^|[\s,;(])\s*({city_pattern})\s*(?:[\s,;)]|$)',
                re.UNICODE | re.MULTILINE
            ),
        ]

        return patterns

    # ========================================================================
    # MAIN EXTRACTION METHOD
    # ========================================================================

    async def extract_entities(
        self,
        text: str,
        use_llm: bool = False,
        known_companies: Optional[List[str]] = None,
    ) -> ExtractionResult:
        """
        Extract all entity types from text.

        Args:
            text: Document text to extract entities from
            use_llm: Whether to use Gemini API for name/org extraction
            known_companies: Optional list of known company names for resolution

        Returns:
            ExtractionResult with entities list and summary counts
        """
        if not text or not text.strip():
            return ExtractionResult(error="Empty text provided")

        result = ExtractionResult(text_length=len(text))
        all_entities: List[Entity] = []

        # Pass 1: Regex extraction (always run)
        try:
            regex_entities = self.extract_regex_entities(text)
            all_entities.extend(regex_entities)
        except Exception as e:
            logger.error(f"Regex extraction failed: {e}")
            result.error = f"Regex extraction error: {str(e)}"

        # Pass 2: LLM extraction (optional)
        if use_llm:
            try:
                llm_entities = await self.extract_llm_entities(text)
                all_entities.extend(llm_entities)
                result.method = 'both'
            except Exception as e:
                logger.error(f"LLM extraction failed: {e}")
                if result.error:
                    result.error += f"; LLM extraction error: {str(e)}"
                else:
                    result.error = f"LLM extraction error: {str(e)}"
        else:
            result.method = 'regex'

        # Deduplicate and resolve entities
        resolved = self.resolve_entities(all_entities, known_companies)

        # Add context snippets
        for entity in resolved:
            if entity.start >= 0 and entity.end > 0:
                ctx_start = max(0, entity.start - 50)
                ctx_end = min(len(text), entity.end + 50)
                entity.context = text[ctx_start:ctx_end].replace('\n', ' ').strip()

        result.entities = resolved

        # Build summary
        summary: Dict[str, int] = {}
        for entity in resolved:
            summary[entity.type] = summary.get(entity.type, 0) + 1
        result.summary = summary

        return result

    # ========================================================================
    # REGEX-BASED EXTRACTION
    # ========================================================================

    def extract_regex_entities(self, text: str) -> List[Entity]:
        """
        Fast regex-based extraction for structured entities.

        Extracts:
        - MONEY: Monetary amounts with currency (MKD, EUR, USD)
        - DATE: Dates in various formats (DD.MM.YYYY, ISO, Macedonian months)
        - TAX_ID: EMBS (7-digit) and EDB tax identifiers
        - LEGAL_REF: Law references, article numbers, official gazette citations
        - IBAN: International bank account numbers
        - GPE: Geographic entities (Macedonian cities in context)

        Returns:
            List of Entity objects with positions and confidence scores
        """
        entities: List[Entity] = []

        for entity_type, pattern_list in self.patterns.items():
            for pattern in pattern_list:
                for match in pattern.finditer(text):
                    entity_text = match.group(0).strip()

                    # Skip very short or very long matches (likely noise)
                    if len(entity_text) < 2 or len(entity_text) > 200:
                        continue

                    # For GPE patterns, extract just the city name from group(1)
                    if entity_type == 'GPE' and match.lastindex and match.lastindex >= 1:
                        entity_text = match.group(1).strip()

                    # For MONEY patterns with currency before number, reformat
                    if entity_type == 'MONEY' and match.lastindex and match.lastindex >= 2:
                        # Use the full match text
                        entity_text = match.group(0).strip()

                    # Confidence scoring based on entity type
                    confidence = self._calculate_regex_confidence(entity_type, entity_text, match)

                    entity = Entity(
                        text=entity_text,
                        type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        confidence=confidence,
                        method='regex',
                    )

                    entities.append(entity)

        return entities

    def _calculate_regex_confidence(
        self,
        entity_type: str,
        entity_text: str,
        match: re.Match,
    ) -> float:
        """Calculate confidence score for a regex match."""
        # Base confidence by type
        base_confidence = {
            'MONEY': 0.95,
            'DATE': 0.95,
            'TAX_ID': 0.98,
            'LEGAL_REF': 0.85,
            'IBAN': 0.97,
            'GPE': 0.80,
        }

        confidence = base_confidence.get(entity_type, 0.80)

        # Adjust based on match quality
        if entity_type == 'MONEY':
            # Higher confidence if currency symbol is clear
            if any(c in entity_text for c in ['денари', 'EUR', '€', 'МКД ', 'USD', '$']):
                confidence = 0.98
        elif entity_type == 'DATE':
            # Check if date values are reasonable
            try:
                groups = match.groups()
                if len(groups) >= 3:
                    # Try to validate the date parts
                    nums = [int(g) for g in groups if g.isdigit()]
                    if nums:
                        if any(n > 2030 or n < 1990 for n in nums if n > 31):
                            confidence *= 0.7  # Unusual year
            except (ValueError, AttributeError):
                pass
        elif entity_type == 'GPE':
            # Higher confidence if preceded by "во" (in) or "од" (from)
            pre_text = entity_text[:10] if len(entity_text) > 10 else ''
            if any(word in pre_text.lower() for word in ['во', 'од', 'за']):
                confidence = 0.90

        return round(confidence, 2)

    # ========================================================================
    # LLM-BASED EXTRACTION (Gemini)
    # ========================================================================

    async def extract_llm_entities(self, text: str) -> List[Entity]:
        """
        Use Gemini API to extract person names and organization names.

        Limits text to first 3000 chars for cost control.
        Uses structured JSON output for reliable parsing.

        Returns:
            List of Entity objects (PERSON and ORG types)
        """
        try:
            import google.generativeai as genai
            from google.generativeai.types import HarmCategory, HarmBlockThreshold
        except ImportError:
            logger.warning("google-generativeai not installed, skipping LLM extraction")
            return []

        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not api_key:
            logger.warning("No Gemini API key found, skipping LLM extraction")
            return []

        # Truncate text to control costs
        max_chars = 3000
        truncated_text = text[:max_chars] if len(text) > max_chars else text

        # Configure Gemini
        genai.configure(api_key=api_key)

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        prompt = f"""Analyze this Macedonian procurement document text and extract all named entities.

Return a JSON object with two arrays:
- "persons": list of person names (individuals mentioned in the document - decision makers, representatives, committee members, signatories)
- "organizations": list of organization/company names (companies, institutions, government bodies)

Rules:
1. Return ONLY names that are clearly identifiable in the text
2. Use the exact text as it appears (Cyrillic or Latin)
3. Do NOT include generic titles like "Директор" without a name
4. Do NOT include partial names or abbreviations unless they are clearly entity names
5. For each entity, include the exact text match from the document

Text:
{truncated_text}

Return valid JSON:
{{"persons": ["Име Презиме", ...], "organizations": ["Назив на организација", ...]}}"""

        try:
            model = genai.GenerativeModel(
                os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
            )
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
                safety_settings=safety_settings,
            )

            result = json.loads(response.text)
            entities: List[Entity] = []

            # Process person names
            for person_name in result.get('persons', []):
                if not person_name or len(person_name.strip()) < 3:
                    continue

                person_name = person_name.strip()

                # Find position in text
                start = text.find(person_name)
                end = start + len(person_name) if start >= 0 else 0

                entities.append(Entity(
                    text=person_name,
                    type='PERSON',
                    start=max(0, start),
                    end=end,
                    confidence=0.85,
                    method='llm',
                ))

            # Process organization names
            for org_name in result.get('organizations', []):
                if not org_name or len(org_name.strip()) < 2:
                    continue

                org_name = org_name.strip()

                # Find position in text
                start = text.find(org_name)
                end = start + len(org_name) if start >= 0 else 0

                entities.append(Entity(
                    text=org_name,
                    type='ORG',
                    start=max(0, start),
                    end=end,
                    confidence=0.82,
                    method='llm',
                ))

            logger.info(
                f"LLM extracted {len(entities)} entities "
                f"({sum(1 for e in entities if e.type == 'PERSON')} persons, "
                f"{sum(1 for e in entities if e.type == 'ORG')} orgs)"
            )

            return entities

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            return []

    # ========================================================================
    # ENTITY RESOLUTION / DEDUPLICATION
    # ========================================================================

    def resolve_entities(
        self,
        entities: List[Entity],
        known_companies: Optional[List[str]] = None,
    ) -> List[Entity]:
        """
        Entity resolution and deduplication.

        Steps:
        1. Normalize company names (remove DOOEL, AD, DOO suffixes)
        2. Apply Latin-to-Cyrillic transliteration for matching
        3. Deduplicate based on normalized text + type + proximity
        4. Match against known companies if provided

        Args:
            entities: Raw extracted entities
            known_companies: Optional list of known company names

        Returns:
            Deduplicated and normalized entity list
        """
        if not entities:
            return []

        # Step 1: Normalize all entities
        for entity in entities:
            entity.normalized = self._normalize_entity(entity.text, entity.type)

        # Step 2: Deduplicate by normalized text + type
        seen = {}  # key: (normalized, type) -> best entity
        for entity in entities:
            key = (entity.normalized or entity.text, entity.type)
            if key in seen:
                existing = seen[key]
                # Keep the one with higher confidence
                if entity.confidence > existing.confidence:
                    seen[key] = entity
                # If same confidence, prefer the one with valid position
                elif (entity.confidence == existing.confidence
                      and entity.start > 0 and existing.start <= 0):
                    seen[key] = entity
            else:
                seen[key] = entity

        resolved = list(seen.values())

        # Step 3: Match ORG entities against known companies
        if known_companies:
            known_normalized = {
                self._normalize_entity(name, 'ORG'): name
                for name in known_companies
            }
            for entity in resolved:
                if entity.type == 'ORG' and entity.normalized in known_normalized:
                    # Boost confidence for known companies
                    entity.confidence = min(1.0, entity.confidence + 0.1)

        # Step 4: Remove overlapping entities (keep higher-priority type)
        # Priority: IBAN > TAX_ID > MONEY > DATE > LEGAL_REF > GPE > ORG > PERSON
        type_priority = {
            'IBAN': 8, 'TAX_ID': 7, 'MONEY': 6, 'DATE': 5,
            'LEGAL_REF': 4, 'GPE': 3, 'ORG': 2, 'PERSON': 1,
        }

        # Sort by position first
        resolved.sort(key=lambda e: (e.start if e.start >= 0 else float('inf')))

        # Remove overlaps: if two entities share the same text span, keep
        # the one with higher type priority
        non_overlapping = []
        for entity in resolved:
            if entity.start < 0:
                # No position info - always keep
                non_overlapping.append(entity)
                continue

            overlap = False
            for existing in non_overlapping:
                if existing.start < 0:
                    continue
                # Check overlap
                if (entity.start < existing.end and entity.end > existing.start):
                    # Overlapping - keep the one with higher priority
                    entity_prio = type_priority.get(entity.type, 0)
                    existing_prio = type_priority.get(existing.type, 0)
                    if entity_prio > existing_prio:
                        non_overlapping.remove(existing)
                        non_overlapping.append(entity)
                    overlap = True
                    break

            if not overlap:
                non_overlapping.append(entity)

        non_overlapping.sort(key=lambda e: (e.start if e.start >= 0 else float('inf')))

        return non_overlapping

    def _normalize_entity(self, text: str, entity_type: str) -> str:
        """
        Normalize entity text for deduplication.

        For ORG: strips company suffixes, normalizes whitespace
        For PERSON: normalizes whitespace, title-cases
        For others: strips whitespace
        """
        if not text:
            return ''

        # Basic cleanup
        normalized = ' '.join(text.split())  # normalize whitespace

        if entity_type == 'ORG':
            # Remove common company suffixes
            for suffix in COMPANY_SUFFIXES:
                # Remove suffix from end, with optional punctuation
                pattern = rf'\s*[-–—,]?\s*{re.escape(suffix)}\s*$'
                normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)

            # Remove quotes
            normalized = normalized.strip('"\'«»„"')

            # Remove trailing punctuation
            normalized = normalized.rstrip('.,;:-')

        elif entity_type == 'PERSON':
            # Remove common titles
            titles = [
                'г-дин', 'г-ѓа', 'проф.', 'д-р', 'м-р',
                'Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.',
            ]
            for title in titles:
                if normalized.startswith(title):
                    normalized = normalized[len(title):].strip()

        elif entity_type == 'MONEY':
            # Keep as-is for money
            pass

        elif entity_type == 'GPE':
            # Remove prepositions that might be captured
            for prep in ['во ', 'од ', 'за ', 'до ']:
                if normalized.startswith(prep):
                    normalized = normalized[len(prep):]

        return normalized.strip()

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    @staticmethod
    def latin_to_cyrillic(text: str) -> str:
        """
        Convert Latin transliteration to Macedonian Cyrillic.
        Delegates to the shared transliteration utility.
        """
        # Import from the project's transliteration module
        try:
            from backend.transliteration import latin_to_cyrillic as _l2c
            return _l2c(text)
        except ImportError:
            pass

        # Fallback: inline transliteration
        latin_to_macedonian = {
            'dzh': '\u045f', 'Dzh': '\u040f',
            'gj': '\u0453', 'Gj': '\u0403',
            'kj': '\u045c', 'Kj': '\u040c',
            'lj': '\u0459', 'Lj': '\u0409',
            'nj': '\u045a', 'Nj': '\u040a',
            'dz': '\u0455', 'Dz': '\u0405',
            'zh': '\u0436', 'Zh': '\u0416',
            'ch': '\u0447', 'Ch': '\u0427',
            'sh': '\u0448', 'Sh': '\u0428',
        }
        single_char = {
            'a': '\u0430', 'b': '\u0431', 'v': '\u0432', 'g': '\u0433',
            'd': '\u0434', 'e': '\u0435', 'z': '\u0437', 'i': '\u0438',
            'j': '\u0458', 'k': '\u043a', 'l': '\u043b', 'm': '\u043c',
            'n': '\u043d', 'o': '\u043e', 'p': '\u043f', 'r': '\u0440',
            's': '\u0441', 't': '\u0442', 'u': '\u0443', 'f': '\u0444',
            'h': '\u0445', 'c': '\u0446',
            'A': '\u0410', 'B': '\u0411', 'V': '\u0412', 'G': '\u0413',
            'D': '\u0414', 'E': '\u0415', 'Z': '\u0417', 'I': '\u0418',
            'J': '\u0408', 'K': '\u041a', 'L': '\u041b', 'M': '\u041c',
            'N': '\u041d', 'O': '\u041e', 'P': '\u041f', 'R': '\u0420',
            'S': '\u0421', 'T': '\u0422', 'U': '\u0423', 'F': '\u0424',
            'H': '\u0425', 'C': '\u0426',
        }

        result = text
        for latin, cyrillic in latin_to_macedonian.items():
            result = result.replace(latin, cyrillic)
        output = ''
        for char in result:
            output += single_char.get(char, char)
        return output

    @staticmethod
    def has_cyrillic(text: str) -> bool:
        """Check if text contains Cyrillic characters."""
        return any('\u0400' <= c <= '\u04FF' for c in text)

    @staticmethod
    def simple_levenshtein(s1: str, s2: str) -> int:
        """Simple Levenshtein distance for fuzzy matching (no heavy deps)."""
        if len(s1) < len(s2):
            return MacedonianNERExtractor.simple_levenshtein(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def fuzzy_match(self, s1: str, s2: str, threshold: float = 0.8) -> bool:
        """Check if two strings are similar enough (Levenshtein-based)."""
        if not s1 or not s2:
            return False
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return True
        distance = self.simple_levenshtein(s1.lower(), s2.lower())
        similarity = 1.0 - (distance / max_len)
        return similarity >= threshold
