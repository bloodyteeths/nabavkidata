"""
Specification Text Analyzer for Corruption Detection

Analyzes tender specification documents for patterns that indicate rigging:
1. Brand-name specifications (mentioning only one brand/model)
2. Restrictive qualification requirements (abnormally high thresholds)
3. Text complexity anomalies (unusually simple or complex)
4. Copied/templated sections from previous tenders

Uses regex-based heuristics for efficiency (no heavy NLP libraries).
Falls back to Gemini API for advanced classification when heuristics
are inconclusive.

Primary language: Macedonian (Cyrillic)

Author: nabavkidata.com
License: Proprietary
"""

import re
import os
import json
import logging
import math
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================================
# BRAND / PRODUCT DETECTION PATTERNS
# ============================================================================

# Well-known international brands commonly seen in procurement specs
KNOWN_BRANDS = [
    # IT / Electronics
    'HP', 'DELL', 'LENOVO', 'APPLE', 'SAMSUNG', 'LG', 'SONY', 'ASUS',
    'ACER', 'TOSHIBA', 'FUJITSU', 'CISCO', 'JUNIPER', 'HUAWEI', 'ZTE',
    'MICROSOFT', 'ORACLE', 'SAP', 'IBM', 'INTEL', 'AMD', 'NVIDIA',
    'CANON', 'EPSON', 'BROTHER', 'XEROX', 'RICOH', 'KONICA', 'MINOLTA',
    # Office / Furniture
    'STEELCASE', 'HERMAN MILLER', 'IKEA',
    # Vehicles
    'MERCEDES', 'BMW', 'AUDI', 'VOLKSWAGEN', 'TOYOTA', 'HYUNDAI', 'KIA',
    'FORD', 'OPEL', 'RENAULT', 'PEUGEOT', 'CITROEN', 'FIAT', 'SKODA',
    'LAND ROVER', 'VOLVO', 'DACIA', 'NISSAN', 'MITSUBISHI', 'SUZUKI',
    # Medical
    'SIEMENS', 'PHILIPS', 'GE HEALTHCARE', 'MEDTRONIC', 'ROCHE',
    'ABBOTT', 'BECKMAN', 'MINDRAY', 'DRAEGER',
    # Construction / Industrial
    'CATERPILLAR', 'KOMATSU', 'BOSCH', 'MAKITA', 'HILTI', 'DEWALT',
    'ATLAS COPCO', 'KARCHER', 'STIHL',
]

# Compile lowercase set for fast lookup
_KNOWN_BRANDS_LOWER = {b.lower() for b in KNOWN_BRANDS}

# Regex: words in ALL-CAPS (3+ chars), likely brand names
_RE_ALLCAPS_WORD = re.compile(r'\b([A-Z][A-Z0-9]{2,})\b')

# Regex: model numbers (letters + digits mix, e.g. "HP ProBook 450 G10", "X570")
_RE_MODEL_NUMBER = re.compile(
    r'\b([A-Za-z]{1,10}[\-\s]?[0-9]{2,6}[A-Za-z0-9\-]*)\b'
)

# Regex: registered/trademark symbols
_RE_TRADEMARK = re.compile(r'[®™©]')

# Macedonian phrase "или еквивалент" (or equivalent) - legally indicates brand-specific spec
_RE_OR_EQUIVALENT_MK = re.compile(
    r'или\s+еквивалент(?:ен|но|на|ни)?', re.IGNORECASE
)
# English variant
_RE_OR_EQUIVALENT_EN = re.compile(
    r'or\s+equivalent', re.IGNORECASE
)

# Quoted product names (Cyrillic or Latin, 2+ words)
_RE_QUOTED_PRODUCT = re.compile(
    r'["\u201C\u201E]([^"\u201D\u201F]{3,60})["\u201D\u201F]'
)

# Part numbers (sequences like "P/N: ABC-1234", "Part No. 12345")
_RE_PART_NUMBER = re.compile(
    r'(?:P/?N|Part\s*No\.?|Кат\.?\s*бр\.?|Арт\.?\s*бр\.?)\s*:?\s*([A-Za-z0-9\-]{3,20})',
    re.IGNORECASE
)


# ============================================================================
# QUALIFICATION REQUIREMENT PATTERNS (Macedonian + English)
# ============================================================================

# Monetary amounts in denari or EUR
_RE_MONEY_MKD = re.compile(
    r'(\d[\d\.\,]{2,15})\s*(?:денар[иа]?|ден\.?|МКД|MKD)',
    re.IGNORECASE
)
_RE_MONEY_EUR = re.compile(
    r'(\d[\d\.\,]{2,15})\s*(?:евр[аоа]?|EUR|€)',
    re.IGNORECASE
)

# Experience years
_RE_EXPERIENCE_YEARS_MK = re.compile(
    r'(?:минимум|најмалку|барем)?\s*(\d+)\s*(?:годин[аиe]|год\.?)\s*(?:искуств[оа]|работно)',
    re.IGNORECASE
)
_RE_EXPERIENCE_YEARS_EN = re.compile(
    r'(?:minimum|at\s+least)?\s*(\d+)\s*years?\s*(?:of\s+)?experience',
    re.IGNORECASE
)

# Turnover requirements (Macedonian)
_RE_TURNOVER_MK = re.compile(
    r'(?:минимален?\s+)?(?:годишен\s+)?промет\s+(?:од\s+)?(\d[\d\.\,]{2,15})',
    re.IGNORECASE
)

# ISO certifications
_RE_ISO_CERT = re.compile(
    r'ISO\s*(\d{4,5})(?:\s*:\s*\d{4})?',
    re.IGNORECASE
)

# Employee count requirements
_RE_EMPLOYEES_MK = re.compile(
    r'(?:минимум|најмалку|барем)\s*(\d+)\s*(?:вработен[иа]|лиц[аеи]|работниц[иа])',
    re.IGNORECASE
)

# Specific license patterns
_RE_LICENSE_MK = re.compile(
    r'(?:лиценц[аиа]|дозвол[аа]|одобрение|сертификат|овластување)\s+(?:за|од)\s+(.{5,80}?)(?:\.|;|,|\n)',
    re.IGNORECASE
)

# Financial guarantee amounts
_RE_GUARANTEE_MK = re.compile(
    r'(?:банкарска\s+)?гаранциј[аа]\s+(?:од|во\s+износ\s+од)\s+(\d[\d\.\,]{2,15})',
    re.IGNORECASE
)


# ============================================================================
# TEXT COMPLEXITY CONSTANTS
# ============================================================================

# Average values from a corpus of Macedonian procurement specifications
# Used for z-score normalization
MK_SPEC_AVG_SENTENCE_LEN = 18.5   # words per sentence
MK_SPEC_STD_SENTENCE_LEN = 6.2
MK_SPEC_AVG_WORD_LEN = 6.8        # characters per word
MK_SPEC_STD_WORD_LEN = 1.4
MK_SPEC_AVG_TTR = 0.42            # type-token ratio
MK_SPEC_STD_TTR = 0.12


@dataclass
class BrandDetection:
    """A detected brand or product reference."""
    brand: str
    context: str       # surrounding text snippet
    confidence: float  # 0-1
    detection_type: str  # 'known_brand', 'allcaps', 'trademark', 'or_equivalent', 'model_number', 'part_number'


@dataclass
class QualificationRequirement:
    """An extracted qualification requirement."""
    type: str          # 'turnover', 'experience_years', 'certification', 'employees', 'license', 'guarantee'
    value: str         # the extracted value (e.g. "10,000,000" or "5")
    raw_text: str      # the original matched text
    is_excessive: bool = False  # flagged if value exceeds typical thresholds


@dataclass
class ComplexityMetrics:
    """Text complexity measurements."""
    avg_sentence_len: float
    avg_word_len: float
    vocabulary_richness: float  # type-token ratio
    technical_density: float    # fraction of technical/uncommon terms
    complexity_score: float     # 0-1 overall score


class SpecificationAnalyzer:
    """
    Analyzes specification text for rigging indicators.

    Detects brand-name restrictions, excessive qualification requirements,
    and text complexity anomalies in Macedonian procurement documents.
    Uses regex heuristics with optional Gemini API fallback.
    """

    def __init__(self, use_gemini_fallback: bool = True):
        """
        Args:
            use_gemini_fallback: Whether to use Gemini API for ambiguous cases.
        """
        self.use_gemini_fallback = use_gemini_fallback
        self._gemini_model = None

    def _get_gemini_model(self):
        """Lazy-initialize Gemini model."""
        if self._gemini_model is None:
            try:
                import google.generativeai as genai
                api_key = os.getenv('GEMINI_API_KEY')
                if api_key:
                    genai.configure(api_key=api_key)
                    self._gemini_model = genai.GenerativeModel(
                        os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
                    )
                else:
                    logger.warning("GEMINI_API_KEY not set, Gemini fallback disabled")
                    self.use_gemini_fallback = False
            except ImportError:
                logger.warning("google-generativeai not installed, Gemini fallback disabled")
                self.use_gemini_fallback = False
        return self._gemini_model

    async def analyze_specification(
        self,
        content_text: str,
        tender_id: str,
        cpv_code: str = None,
    ) -> dict:
        """
        Full specification analysis.

        Args:
            content_text: Extracted document text (Macedonian or mixed).
            tender_id: The tender identifier.
            cpv_code: Optional CPV code for context-aware analysis.

        Returns:
            Dictionary with analysis results including:
            - brand_names_detected: list of detected brands
            - brand_exclusivity_score: 0-1 (higher = more restrictive)
            - qualification_requirements: list of extracted requirements
            - qualification_restrictiveness: 0-1
            - complexity_score: 0-1
            - vocabulary_richness: type-token ratio
            - rigging_probability: overall 0-1
            - risk_factors: human-readable list of concerns
        """
        if not content_text or len(content_text.strip()) < 50:
            return self._empty_result(tender_id)

        # Truncate very long documents to save processing time (keep first 50K chars)
        text = content_text[:50000] if len(content_text) > 50000 else content_text

        # 1. Brand name detection
        brand_detections = self.detect_brand_names(text)

        # 2. Qualification requirements extraction
        qualifications = self.extract_qualifications(text)

        # 3. Text complexity analysis
        complexity = self.compute_complexity(text)

        # 4. Compute scores
        brand_exclusivity = self._compute_brand_exclusivity_score(brand_detections, text)
        qualification_restrictiveness = self._compute_qualification_restrictiveness(qualifications)

        # 5. Build risk factors list
        risk_factors = self._build_risk_factors(
            brand_detections, brand_exclusivity,
            qualifications, qualification_restrictiveness,
            complexity
        )

        # 6. Compute overall rigging probability
        rigging_probability = self._compute_rigging_probability(
            brand_exclusivity,
            qualification_restrictiveness,
            complexity,
            len(risk_factors),
        )

        # 7. Optional Gemini verification for high-risk cases
        if (
            self.use_gemini_fallback
            and 0.3 <= rigging_probability <= 0.7
            and len(text) > 200
        ):
            gemini_adjustment = await self._gemini_verify(
                text[:8000], brand_detections, qualifications, tender_id
            )
            if gemini_adjustment is not None:
                # Blend heuristic and Gemini scores (70% heuristic, 30% Gemini)
                rigging_probability = 0.7 * rigging_probability + 0.3 * gemini_adjustment

        return {
            'tender_id': tender_id,
            'brand_names_detected': [
                {
                    'brand': d.brand,
                    'context': d.context[:200],
                    'confidence': round(d.confidence, 3),
                }
                for d in brand_detections
            ],
            'brand_exclusivity_score': round(brand_exclusivity, 3),
            'qualification_requirements': [
                {
                    'type': q.type,
                    'value': q.value,
                    'is_excessive': q.is_excessive,
                }
                for q in qualifications
            ],
            'qualification_restrictiveness': round(qualification_restrictiveness, 3),
            'complexity_score': round(complexity.complexity_score, 3),
            'vocabulary_richness': round(complexity.vocabulary_richness, 3),
            'rigging_probability': round(min(max(rigging_probability, 0.0), 1.0), 3),
            'risk_factors': risk_factors,
        }

    def detect_brand_names(self, text: str) -> List[BrandDetection]:
        """
        Detect product brand names, model numbers, proprietary references.

        Uses multiple detection strategies:
        - Known brand lookup (case-insensitive)
        - ALL-CAPS words (3+ characters, likely brand names)
        - Registered/trademark symbols (R), (TM)
        - "ili ekvivalent" / "or equivalent" patterns
        - Quoted product names
        - Part/catalog number patterns

        Args:
            text: Document text to analyze.

        Returns:
            List of BrandDetection objects with brand, context, confidence.
        """
        detections: List[BrandDetection] = []
        seen_brands = set()  # avoid duplicates

        def _context_snippet(match_start: int, match_end: int, window: int = 80) -> str:
            """Extract surrounding context for a match."""
            start = max(0, match_start - window)
            end = min(len(text), match_end + window)
            snippet = text[start:end].replace('\n', ' ').strip()
            return snippet

        def _add_detection(brand: str, start: int, end: int, confidence: float, dtype: str):
            key = brand.lower().strip()
            if key and key not in seen_brands and len(key) >= 2:
                seen_brands.add(key)
                detections.append(BrandDetection(
                    brand=brand.strip(),
                    context=_context_snippet(start, end),
                    confidence=confidence,
                    detection_type=dtype,
                ))

        # Strategy 1: Known brand lookup
        text_lower = text.lower()
        for brand in KNOWN_BRANDS:
            brand_lower = brand.lower()
            idx = text_lower.find(brand_lower)
            if idx >= 0:
                _add_detection(brand, idx, idx + len(brand), 0.9, 'known_brand')

        # Strategy 2: ALL-CAPS words (potential unknown brands)
        for match in _RE_ALLCAPS_WORD.finditer(text):
            word = match.group(1)
            # Skip common Macedonian abbreviations and generic terms
            if word in ('ДДВ', 'МКД', 'EUR', 'ISO', 'ЕМБС', 'ЕДБ', 'НВО',
                        'ЈН', 'ДОО', 'ДООЕЛ', 'АД', 'ООД', 'THE', 'AND',
                        'FOR', 'PDF', 'DOC', 'XML', 'HTML', 'URL', 'API',
                        'RAM', 'CPU', 'GPU', 'SSD', 'HDD', 'USB', 'LED',
                        'LCD', 'LAN', 'WAN', 'VPN', 'DNS', 'TCP', 'UDP',
                        'HTTP', 'HTTPS', 'FTP', 'SSH', 'SQL', 'LOT'):
                continue
            if word.lower() not in seen_brands:
                _add_detection(word, match.start(), match.end(), 0.5, 'allcaps')

        # Strategy 3: Trademark/registered symbols
        for match in _RE_TRADEMARK.finditer(text):
            # Look backwards for the brand name preceding the symbol
            preceding = text[max(0, match.start() - 40):match.start()].strip()
            words = preceding.split()
            if words:
                brand_name = ' '.join(words[-2:]) if len(words) >= 2 else words[-1]
                _add_detection(brand_name, match.start() - len(brand_name), match.end(), 0.95, 'trademark')

        # Strategy 4: "or equivalent" pattern (in Macedonian and English)
        for pattern in (_RE_OR_EQUIVALENT_MK, _RE_OR_EQUIVALENT_EN):
            for match in pattern.finditer(text):
                # The brand is usually mentioned before "or equivalent"
                preceding = text[max(0, match.start() - 100):match.start()].strip()
                # Try to find a brand in the preceding text
                caps_in_preceding = _RE_ALLCAPS_WORD.findall(preceding)
                if caps_in_preceding:
                    brand_candidate = caps_in_preceding[-1]
                    _add_detection(
                        brand_candidate, match.start() - 50, match.end(),
                        0.85, 'or_equivalent'
                    )
                else:
                    # Use quoted name if present
                    quoted = _RE_QUOTED_PRODUCT.findall(preceding)
                    if quoted:
                        _add_detection(
                            quoted[-1], match.start() - 50, match.end(),
                            0.8, 'or_equivalent'
                        )

        # Strategy 5: Part numbers / catalog numbers
        for match in _RE_PART_NUMBER.finditer(text):
            _add_detection(
                match.group(1), match.start(), match.end(),
                0.7, 'part_number'
            )

        # Strategy 6: Model number patterns (e.g., "ProBook 450", "X570-PLUS")
        model_matches = list(_RE_MODEL_NUMBER.finditer(text))
        # Only flag if there are a moderate number (too many = noise)
        if 1 <= len(model_matches) <= 20:
            for match in model_matches[:10]:
                model = match.group(1)
                # Filter out common non-model patterns (dates, page numbers, etc.)
                if re.match(r'^\d{4}$', model):  # skip pure years
                    continue
                if len(model) < 3:
                    continue
                _add_detection(
                    model, match.start(), match.end(),
                    0.4, 'model_number'
                )

        return detections

    def extract_qualifications(self, text: str) -> List[QualificationRequirement]:
        """
        Extract qualification requirements from specification text.

        Detects:
        - Turnover thresholds (e.g., "minimalen promet od 10,000,000 denari")
        - Experience years (e.g., "minimum 5 godini iskustvo")
        - Specific certifications (ISO standards)
        - Staff requirements (number of employees)
        - License requirements
        - Financial guarantees

        Args:
            text: Document text to analyze.

        Returns:
            List of QualificationRequirement objects.
        """
        qualifications: List[QualificationRequirement] = []

        # Turnover requirements (Macedonian)
        for match in _RE_TURNOVER_MK.finditer(text):
            value_str = match.group(1).replace('.', '').replace(',', '')
            try:
                value_num = float(value_str)
                qualifications.append(QualificationRequirement(
                    type='turnover',
                    value=match.group(1),
                    raw_text=match.group(0),
                    # Flag if turnover > 50M MKD (~800K EUR) as potentially excessive
                    is_excessive=value_num > 50_000_000,
                ))
            except ValueError:
                qualifications.append(QualificationRequirement(
                    type='turnover',
                    value=match.group(1),
                    raw_text=match.group(0),
                ))

        # Monetary amounts in MKD (general)
        for match in _RE_MONEY_MKD.finditer(text):
            value_str = match.group(1).replace('.', '').replace(',', '')
            # Only add if not already captured as turnover
            already_captured = any(q.raw_text in match.group(0) for q in qualifications)
            if not already_captured:
                try:
                    value_num = float(value_str)
                    if value_num > 1_000_000:  # Only flag significant amounts
                        qualifications.append(QualificationRequirement(
                            type='financial_threshold',
                            value=match.group(1),
                            raw_text=match.group(0),
                            is_excessive=value_num > 100_000_000,
                        ))
                except ValueError:
                    pass

        # Experience years (Macedonian)
        for match in _RE_EXPERIENCE_YEARS_MK.finditer(text):
            years = int(match.group(1))
            qualifications.append(QualificationRequirement(
                type='experience_years',
                value=str(years),
                raw_text=match.group(0),
                # Flag if > 10 years required as potentially excessive
                is_excessive=years > 10,
            ))

        # Experience years (English)
        for match in _RE_EXPERIENCE_YEARS_EN.finditer(text):
            years = int(match.group(1))
            qualifications.append(QualificationRequirement(
                type='experience_years',
                value=str(years),
                raw_text=match.group(0),
                is_excessive=years > 10,
            ))

        # ISO certifications
        for match in _RE_ISO_CERT.finditer(text):
            iso_num = match.group(1)
            qualifications.append(QualificationRequirement(
                type='certification',
                value=f'ISO {iso_num}',
                raw_text=match.group(0),
                # Multiple ISO certs can be restrictive but not individually excessive
                is_excessive=False,
            ))

        # Employee count requirements
        for match in _RE_EMPLOYEES_MK.finditer(text):
            count = int(match.group(1))
            qualifications.append(QualificationRequirement(
                type='employees',
                value=str(count),
                raw_text=match.group(0),
                # Flag if > 50 employees required
                is_excessive=count > 50,
            ))

        # License requirements
        for match in _RE_LICENSE_MK.finditer(text):
            qualifications.append(QualificationRequirement(
                type='license',
                value=match.group(1).strip(),
                raw_text=match.group(0),
                is_excessive=False,
            ))

        # Financial guarantees
        for match in _RE_GUARANTEE_MK.finditer(text):
            value_str = match.group(1).replace('.', '').replace(',', '')
            try:
                value_num = float(value_str)
                qualifications.append(QualificationRequirement(
                    type='guarantee',
                    value=match.group(1),
                    raw_text=match.group(0),
                    is_excessive=value_num > 10_000_000,
                ))
            except ValueError:
                qualifications.append(QualificationRequirement(
                    type='guarantee',
                    value=match.group(1),
                    raw_text=match.group(0),
                ))

        # Check if multiple ISO certs are required (restrictive pattern)
        iso_certs = [q for q in qualifications if q.type == 'certification']
        if len(iso_certs) >= 3:
            for cert in iso_certs:
                cert.is_excessive = True

        return qualifications

    def compute_complexity(self, text: str) -> ComplexityMetrics:
        """
        Compute text complexity metrics adapted for Macedonian.

        Metrics:
        - Average sentence length (words per sentence)
        - Average word length (characters per word)
        - Vocabulary richness (unique words / total words = type-token ratio)
        - Technical density (estimated fraction of technical/uncommon terms)
        - Composite complexity score (0-1)

        Args:
            text: Document text to analyze.

        Returns:
            ComplexityMetrics dataclass with all computed values.
        """
        if not text or len(text.strip()) < 20:
            return ComplexityMetrics(
                avg_sentence_len=0,
                avg_word_len=0,
                vocabulary_richness=0,
                technical_density=0,
                complexity_score=0.5,
            )

        # Split into sentences (handle Macedonian punctuation)
        sentences = re.split(r'[.!?;]\s+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

        if not sentences:
            return ComplexityMetrics(
                avg_sentence_len=0,
                avg_word_len=0,
                vocabulary_richness=0,
                technical_density=0,
                complexity_score=0.5,
            )

        # Extract words (Cyrillic + Latin, 2+ chars)
        words = re.findall(r'[\w\u0400-\u04FF]{2,}', text.lower())

        if not words:
            return ComplexityMetrics(
                avg_sentence_len=0,
                avg_word_len=0,
                vocabulary_richness=0,
                technical_density=0,
                complexity_score=0.5,
            )

        total_words = len(words)
        unique_words = len(set(words))

        # Sentence lengths (in words)
        sentence_word_counts = []
        for sent in sentences:
            sent_words = re.findall(r'[\w\u0400-\u04FF]{2,}', sent)
            if sent_words:
                sentence_word_counts.append(len(sent_words))

        avg_sentence_len = (
            sum(sentence_word_counts) / len(sentence_word_counts)
            if sentence_word_counts else 0
        )

        # Average word length (characters)
        avg_word_len = sum(len(w) for w in words) / total_words

        # Type-token ratio (vocabulary richness)
        # Use a window for long texts to avoid TTR dropping with text length
        if total_words > 1000:
            # Sample TTR from multiple windows
            window_size = 500
            ttrs = []
            for i in range(0, min(total_words, 5000), window_size):
                window = words[i:i + window_size]
                if len(window) >= 100:
                    ttrs.append(len(set(window)) / len(window))
            vocabulary_richness = sum(ttrs) / len(ttrs) if ttrs else unique_words / total_words
        else:
            vocabulary_richness = unique_words / total_words

        # Technical density: estimate by looking for long words (>10 chars)
        # and words with mixed scripts/digits
        technical_words = sum(
            1 for w in words
            if len(w) > 10 or re.search(r'\d', w)
        )
        technical_density = technical_words / total_words

        # Composite complexity score (0-1)
        # Z-score based on Macedonian procurement text averages
        z_sentence = abs(avg_sentence_len - MK_SPEC_AVG_SENTENCE_LEN) / MK_SPEC_STD_SENTENCE_LEN
        z_word = abs(avg_word_len - MK_SPEC_AVG_WORD_LEN) / MK_SPEC_STD_WORD_LEN
        z_ttr = abs(vocabulary_richness - MK_SPEC_AVG_TTR) / MK_SPEC_STD_TTR

        # Average z-score, clamped to [0, 1]
        raw_complexity = (z_sentence + z_word + z_ttr) / 3.0
        # Sigmoid-like transform to map to 0-1
        complexity_score = min(1.0, raw_complexity / 3.0)

        return ComplexityMetrics(
            avg_sentence_len=round(avg_sentence_len, 2),
            avg_word_len=round(avg_word_len, 2),
            vocabulary_richness=round(vocabulary_richness, 4),
            technical_density=round(technical_density, 4),
            complexity_score=round(complexity_score, 4),
        )

    # ========================================================================
    # SCORING HELPERS
    # ========================================================================

    def _compute_brand_exclusivity_score(
        self,
        detections: List[BrandDetection],
        text: str,
    ) -> float:
        """
        Compute a brand exclusivity score (0-1).

        Higher score means the specification is more restrictive / brand-specific.
        Considers:
        - Number of distinct brands detected
        - Confidence of detections
        - Presence of "or equivalent" clauses
        - Ratio of brand mentions to text length
        """
        if not detections:
            return 0.0

        # Weight by confidence
        total_confidence = sum(d.confidence for d in detections)
        avg_confidence = total_confidence / len(detections)

        # Check for "or equivalent" - its presence slightly reduces severity
        # (it means they at least nominally allow alternatives)
        has_or_equivalent = bool(
            _RE_OR_EQUIVALENT_MK.search(text) or _RE_OR_EQUIVALENT_EN.search(text)
        )

        # Brand density: brands per 1000 words
        word_count = len(re.findall(r'[\w\u0400-\u04FF]{2,}', text))
        brand_density = (len(detections) / max(word_count, 1)) * 1000

        # Score components
        # More brands with higher confidence = higher exclusivity
        brand_count_score = min(1.0, len(detections) / 5.0)
        confidence_score = avg_confidence
        density_score = min(1.0, brand_density / 10.0)

        # Combine
        raw_score = (
            0.4 * brand_count_score
            + 0.4 * confidence_score
            + 0.2 * density_score
        )

        # "or equivalent" reduces score by 20%
        if has_or_equivalent:
            raw_score *= 0.8

        # High-confidence known brands weigh more
        known_brand_count = sum(1 for d in detections if d.detection_type == 'known_brand')
        if known_brand_count >= 2:
            raw_score = min(1.0, raw_score * 1.3)

        return min(1.0, max(0.0, raw_score))

    def _compute_qualification_restrictiveness(
        self,
        qualifications: List[QualificationRequirement],
    ) -> float:
        """
        Compute qualification restrictiveness score (0-1).

        Considers:
        - Number of qualification requirements
        - Whether any are flagged as excessive
        - Diversity of requirement types
        """
        if not qualifications:
            return 0.0

        excessive_count = sum(1 for q in qualifications if q.is_excessive)
        unique_types = len(set(q.type for q in qualifications))
        total = len(qualifications)

        # Score components
        count_score = min(1.0, total / 8.0)  # 8+ requirements is very restrictive
        excessive_score = min(1.0, excessive_count / 3.0)
        diversity_score = min(1.0, unique_types / 5.0)

        raw_score = (
            0.3 * count_score
            + 0.5 * excessive_score
            + 0.2 * diversity_score
        )

        return min(1.0, max(0.0, raw_score))

    def _build_risk_factors(
        self,
        brand_detections: List[BrandDetection],
        brand_exclusivity: float,
        qualifications: List[QualificationRequirement],
        qualification_restrictiveness: float,
        complexity: ComplexityMetrics,
    ) -> List[str]:
        """Build human-readable risk factor list."""
        factors = []

        # Brand-related factors
        known_brands = [d for d in brand_detections if d.detection_type == 'known_brand']
        if known_brands:
            brand_names = ', '.join(d.brand for d in known_brands[:5])
            factors.append(f"Спецификацијата споменува конкретни брендови: {brand_names}")

        trademark_detections = [d for d in brand_detections if d.detection_type == 'trademark']
        if trademark_detections:
            factors.append("Пронајдени се заштитени трговски марки (® / ™)")

        or_equiv = [d for d in brand_detections if d.detection_type == 'or_equivalent']
        if or_equiv:
            factors.append("Содржи формулација 'или еквивалент' - индикатор за бренд-специфична спецификација")

        part_numbers = [d for d in brand_detections if d.detection_type == 'part_number']
        if part_numbers:
            factors.append(f"Наведени се каталошки/парт броеви ({len(part_numbers)} пронајдени)")

        if brand_exclusivity > 0.7:
            factors.append("Високо ниво на ексклузивност на бренд - потенцијално ограничувачка спецификација")

        # Qualification-related factors
        excessive = [q for q in qualifications if q.is_excessive]
        if excessive:
            for q in excessive[:3]:
                if q.type == 'turnover':
                    factors.append(f"Превисок праг на промет: {q.value} денари")
                elif q.type == 'experience_years':
                    factors.append(f"Прекумерен број на потребни години искуство: {q.value}")
                elif q.type == 'employees':
                    factors.append(f"Висок барање за број на вработени: {q.value}")
                elif q.type == 'guarantee':
                    factors.append(f"Висока банкарска гаранција: {q.value} денари")
                elif q.type == 'financial_threshold':
                    factors.append(f"Висок финансиски праг: {q.value} денари")

        iso_certs = [q for q in qualifications if q.type == 'certification']
        if len(iso_certs) >= 3:
            cert_list = ', '.join(q.value for q in iso_certs[:5])
            factors.append(f"Бара {len(iso_certs)} ISO сертификати: {cert_list}")

        if qualification_restrictiveness > 0.6:
            factors.append("Комбинација на квалификациски услови може да ја ограничи конкуренцијата")

        # Complexity-related factors
        if complexity.complexity_score > 0.6:
            factors.append("Невообичаена текстуална комплексност - може да укажува на намерно збунување")
        elif complexity.complexity_score < 0.15 and complexity.avg_sentence_len > 0:
            factors.append("Невообичаено едноставен текст - може да укажува на шаблонска спецификација")

        if complexity.vocabulary_richness < 0.2 and complexity.avg_sentence_len > 0:
            factors.append("Многу низок вокабуларен диверзитет - индикатор за копиран текст")

        return factors

    def _compute_rigging_probability(
        self,
        brand_exclusivity: float,
        qualification_restrictiveness: float,
        complexity: ComplexityMetrics,
        num_risk_factors: int,
    ) -> float:
        """
        Compute overall rigging probability (0-1).

        Weighted combination of all sub-scores.
        """
        # Weights for each component
        w_brand = 0.35
        w_qual = 0.30
        w_complexity = 0.15
        w_factors = 0.20

        # Complexity anomaly: both very high and very low are suspicious
        complexity_risk = complexity.complexity_score

        # Risk factor density
        factor_score = min(1.0, num_risk_factors / 6.0)

        raw = (
            w_brand * brand_exclusivity
            + w_qual * qualification_restrictiveness
            + w_complexity * complexity_risk
            + w_factors * factor_score
        )

        return min(1.0, max(0.0, raw))

    async def _gemini_verify(
        self,
        text_snippet: str,
        brand_detections: List[BrandDetection],
        qualifications: List[QualificationRequirement],
        tender_id: str,
    ) -> Optional[float]:
        """
        Use Gemini API to verify/refine rigging assessment.

        Only called for ambiguous cases (rigging_probability between 0.3 and 0.7).

        Args:
            text_snippet: First ~8000 chars of document text.
            brand_detections: Detected brands from heuristics.
            qualifications: Detected qualifications from heuristics.
            tender_id: For logging.

        Returns:
            Float 0-1 risk score from Gemini, or None if unavailable.
        """
        model = self._get_gemini_model()
        if model is None:
            return None

        brands_summary = ', '.join(d.brand for d in brand_detections[:5]) if brand_detections else 'none detected'
        quals_summary = '; '.join(
            f"{q.type}: {q.value}" for q in qualifications[:5]
        ) if qualifications else 'none detected'

        prompt = f"""Analyze this public procurement specification text for signs of specification rigging.
Specification rigging means the document is written to favor a specific company or product.

Detected brands: {brands_summary}
Detected qualification requirements: {quals_summary}

Document text (first section):
---
{text_snippet[:5000]}
---

Based on the text, estimate the probability (0 to 1) that this specification is rigged
to favor a specific bidder. Consider:
1. Are brand names used without allowing equivalents?
2. Are qualification requirements unusually restrictive?
3. Is the specification copied from a vendor's product sheet?
4. Are there technical requirements that only one vendor can meet?

Return ONLY a valid JSON object:
{{"rigging_probability": 0.XX, "reasoning": "brief explanation"}}"""

        try:
            import google.generativeai as genai

            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )

            if response and response.text:
                result = json.loads(response.text)
                prob = float(result.get('rigging_probability', 0.5))
                reasoning = result.get('reasoning', '')
                logger.info(
                    f"Gemini spec rigging verification for {tender_id}: "
                    f"probability={prob:.2f}, reasoning={reasoning[:100]}"
                )
                return min(1.0, max(0.0, prob))

        except Exception as e:
            logger.warning(f"Gemini spec analysis failed for {tender_id}: {e}")

        return None

    def _empty_result(self, tender_id: str) -> dict:
        """Return empty analysis result for missing/short documents."""
        return {
            'tender_id': tender_id,
            'brand_names_detected': [],
            'brand_exclusivity_score': 0.0,
            'qualification_requirements': [],
            'qualification_restrictiveness': 0.0,
            'complexity_score': 0.5,
            'vocabulary_richness': 0.0,
            'rigging_probability': 0.0,
            'risk_factors': [],
        }
