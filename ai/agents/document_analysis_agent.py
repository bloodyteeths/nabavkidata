"""
Document Analysis Agent for Corruption Detection

This agent analyzes tender documents (PDFs, contracts) to find red flags
and extract key information that may indicate corruption or irregularities.

Features:
- Technical requirements analysis (tailored/restrictive specifications)
- Qualification criteria examination
- Evaluation criteria assessment
- Contract analysis (payment terms, penalties, amendments)
- Pricing extraction and comparison
- Cross-tender pattern detection

Database: PostgreSQL with documents.content_text containing extracted text
LLM: Google Gemini for intelligent analysis
"""

import os
import re
import json
import logging
import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

import asyncpg
import aiohttp
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Database configuration from environment
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'nabavki_user'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'nabavkidata'),
}

# Gemini API configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Safety settings - allow all content for analysis
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}


# ============================================================================
# DATA CLASSES
# ============================================================================

class Severity(Enum):
    """Red flag severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RedFlag:
    """Represents a detected corruption red flag"""
    flag_type: str
    severity: Severity
    evidence: str
    confidence: float  # 0.0 to 1.0
    document_reference: str
    page_number: Optional[int] = None
    description: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            'flag_type': self.flag_type,
            'severity': self.severity.value,
            'evidence': self.evidence,
            'confidence': self.confidence,
            'document_reference': self.document_reference,
            'page_number': self.page_number,
            'description': self.description,
            'recommendation': self.recommendation,
        }


@dataclass
class DocumentInfo:
    """Document metadata and content"""
    doc_id: str
    tender_id: str
    doc_type: str
    file_name: str
    content_text: str
    file_url: Optional[str] = None
    page_count: Optional[int] = None

    @property
    def is_contract(self) -> bool:
        keywords = ['договор', 'contract', 'потпишан', 'signed']
        return any(kw in self.file_name.lower() or kw in (self.doc_type or '').lower()
                   for kw in keywords)

    @property
    def is_specification(self) -> bool:
        keywords = ['спецификација', 'specification', 'технички', 'technical', 'тендерска']
        return any(kw in self.file_name.lower() or kw in (self.doc_type or '').lower()
                   for kw in keywords)

    @property
    def is_evaluation(self) -> bool:
        keywords = ['евалуација', 'evaluation', 'оценка', 'избор', 'selection', 'scoring']
        return any(kw in self.file_name.lower() or kw in (self.doc_type or '').lower()
                   for kw in keywords)


@dataclass
class AnalysisResult:
    """Result of document analysis"""
    tender_id: str
    analysis_type: str
    timestamp: datetime
    red_flags: List[RedFlag]
    summary: str
    details: Dict[str, Any]
    overall_risk_score: float  # 0.0 to 1.0
    documents_analyzed: List[str]

    def to_dict(self) -> dict:
        return {
            'tender_id': self.tender_id,
            'analysis_type': self.analysis_type,
            'timestamp': self.timestamp.isoformat(),
            'red_flags': [rf.to_dict() for rf in self.red_flags],
            'summary': self.summary,
            'details': self.details,
            'overall_risk_score': self.overall_risk_score,
            'documents_analyzed': self.documents_analyzed,
        }


# ============================================================================
# DOCUMENT ANALYSIS AGENT
# ============================================================================

class DocumentAnalysisAgent:
    """
    Agent for analyzing tender documents to detect corruption red flags.

    This agent uses LLM-powered analysis to examine tender documents for:
    - Tailored specifications favoring specific vendors
    - Restrictive qualification criteria
    - Subjective evaluation criteria
    - Contract irregularities
    - Pricing anomalies
    - Pattern matching across similar tenders
    """

    def __init__(
        self,
        db_config: Dict[str, str] = None,
        gemini_api_key: str = None
    ):
        """
        Initialize the Document Analysis Agent.

        Args:
            db_config: Database connection parameters
            gemini_api_key: Google Gemini API key
        """
        self.db_config = db_config or DB_CONFIG
        self.gemini_api_key = gemini_api_key or GEMINI_API_KEY

        # Initialize Gemini
        genai.configure(api_key=self.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

        # Connection pool (lazy initialization)
        self._pool: Optional[asyncpg.Pool] = None

        logger.info("DocumentAnalysisAgent initialized")

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool"""
        if self._pool is None or self._pool._closed:
            self._pool = await asyncpg.create_pool(
                host=self.db_config['host'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database=self.db_config['database'],
                min_size=2,
                max_size=10,
                command_timeout=60,
            )
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    # ========================================================================
    # DOCUMENT RETRIEVAL
    # ========================================================================

    async def _get_tender_documents(self, tender_id: str) -> List[DocumentInfo]:
        """
        Get all documents for a tender from the database.

        Args:
            tender_id: The tender ID

        Returns:
            List of DocumentInfo objects
        """
        pool = await self._get_pool()

        query = """
            SELECT
                doc_id::text,
                tender_id,
                doc_type,
                file_name,
                content_text,
                file_url,
                page_count
            FROM documents
            WHERE tender_id = $1
            AND content_text IS NOT NULL
            AND length(content_text) > 100
            ORDER BY uploaded_at DESC
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, tender_id)

        documents = []
        for row in rows:
            documents.append(DocumentInfo(
                doc_id=row['doc_id'],
                tender_id=row['tender_id'],
                doc_type=row['doc_type'] or 'unknown',
                file_name=row['file_name'] or 'unknown',
                content_text=row['content_text'],
                file_url=row['file_url'],
                page_count=row['page_count'],
            ))

        logger.info(f"Retrieved {len(documents)} documents for tender {tender_id}")
        return documents

    async def _get_tender_info(self, tender_id: str) -> Optional[Dict]:
        """Get tender metadata"""
        pool = await self._get_pool()

        query = """
            SELECT
                tender_id,
                title,
                description,
                procuring_entity,
                estimated_value_mkd,
                actual_value_mkd,
                cpv_code,
                status,
                winner,
                opening_date,
                closing_date,
                procedure_type,
                evaluation_method,
                num_bidders
            FROM tenders
            WHERE tender_id = $1
        """

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, tender_id)

        if row:
            return dict(row)
        return None

    async def _fetch_pdf_content(self, file_url: str) -> Optional[str]:
        """
        Fetch and extract text from a PDF URL.

        Args:
            file_url: URL of the PDF

        Returns:
            Extracted text or None if failed
        """
        try:
            import tempfile
            import sys
            sys.path.insert(0, '/Users/tamsar/Downloads/nabavkidata/scraper')
            from document_parser import ResilientDocumentParser

            async with aiohttp.ClientSession() as session:
                async with session.get(file_url, timeout=30) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch PDF: {file_url}, status: {response.status}")
                        return None

                    pdf_data = await response.read()

            # Save to temp file and parse
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(pdf_data)
                temp_path = f.name

            parser = ResilientDocumentParser()
            result = parser.parse_document(temp_path)

            # Cleanup
            os.unlink(temp_path)

            return result.text if result.text else None

        except Exception as e:
            logger.error(f"PDF fetch failed: {e}")
            return None

    # ========================================================================
    # LLM ANALYSIS HELPERS
    # ========================================================================

    async def _analyze_with_llm(
        self,
        prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.2
    ) -> Optional[Dict]:
        """
        Send prompt to Gemini and parse JSON response.

        Args:
            prompt: Analysis prompt
            max_tokens: Maximum output tokens
            temperature: Generation temperature

        Returns:
            Parsed JSON response or None
        """
        try:
            def _generate():
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                    safety_settings=SAFETY_SETTINGS,
                )
                return response.text

            response_text = await asyncio.to_thread(_generate)

            # Clean and parse JSON
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Try to parse JSON
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                # Try to find JSON in response
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    return json.loads(json_match.group())
                logger.warning(f"Could not parse LLM response as JSON")
                return None

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return None

    def _calculate_risk_score(self, red_flags: List[RedFlag]) -> float:
        """Calculate overall risk score from red flags"""
        if not red_flags:
            return 0.0

        severity_weights = {
            Severity.LOW: 0.1,
            Severity.MEDIUM: 0.3,
            Severity.HIGH: 0.6,
            Severity.CRITICAL: 1.0,
        }

        total_weight = sum(
            severity_weights[rf.severity] * rf.confidence
            for rf in red_flags
        )

        # Normalize to 0-1 range
        max_possible = len(red_flags) * 1.0  # All critical with 100% confidence
        risk_score = min(1.0, total_weight / max(1, max_possible) * 2)

        return round(risk_score, 3)

    # ========================================================================
    # MAIN ANALYSIS METHODS
    # ========================================================================

    async def analyze_tender_documents(self, tender_id: str) -> Dict:
        """
        Analyze all documents for a tender.

        This comprehensive analysis:
        - Gets all documents from database
        - Fetches any missing PDFs
        - Uses LLM to analyze content

        Returns analysis of:
        - Technical requirements (are they restrictive/tailored?)
        - Qualification criteria (unusually specific?)
        - Evaluation criteria (subjective?)
        - Timeline analysis

        Args:
            tender_id: The tender ID to analyze

        Returns:
            Complete analysis results
        """
        logger.info(f"Starting comprehensive analysis for tender {tender_id}")

        # Get tender info and documents
        tender_info = await self._get_tender_info(tender_id)
        documents = await self._get_tender_documents(tender_id)

        if not tender_info:
            return {
                'error': f'Tender {tender_id} not found',
                'tender_id': tender_id,
                'timestamp': datetime.utcnow().isoformat(),
            }

        if not documents:
            return {
                'error': f'No documents found for tender {tender_id}',
                'tender_id': tender_id,
                'tender_info': tender_info,
                'timestamp': datetime.utcnow().isoformat(),
            }

        # Combine document content (limit to prevent token overflow)
        combined_content = ""
        for doc in documents[:5]:  # Limit to 5 documents
            truncated = doc.content_text[:8000] if len(doc.content_text) > 8000 else doc.content_text
            combined_content += f"\n\n=== DOCUMENT: {doc.file_name} ===\n{truncated}"

        # Prepare analysis prompt
        prompt = f"""Ти си експерт за анализа на јавни набавки и детекција на корупција.
Анализирај ги следниве документи од тендер и идентификувај потенцијални црвени знамиња.

ИНФОРМАЦИИ ЗА ТЕНДЕРОТ:
- Наслов: {tender_info.get('title', 'N/A')}
- Набавувач: {tender_info.get('procuring_entity', 'N/A')}
- Проценета вредност: {tender_info.get('estimated_value_mkd', 'N/A')} МКД
- Победник: {tender_info.get('winner', 'N/A')}
- CPV код: {tender_info.get('cpv_code', 'N/A')}
- Број на понудувачи: {tender_info.get('num_bidders', 'N/A')}

ДОКУМЕНТИ:
{combined_content[:30000]}

АНАЛИЗИРАЈ ГИ СЛЕДНИВЕ АСПЕКТИ:

1. ТЕХНИЧКИ СПЕЦИФИКАЦИИ
- Дали спецификациите се рестриктивни или премногу специфични?
- Дали има наведени брендови без потреба?
- Дали барањата одговараат само на еден производител?

2. КВАЛИФИКАЦИСКИ КРИТЕРИУМИ
- Дали критериумите се необично специфични?
- Дали бараат посебни сертификати што ги има само една компанија?
- Дали има барање за претходно искуство што е прекумерно?

3. КРИТЕРИУМИ ЗА ЕВАЛУАЦИЈА
- Дали критериумите се субјективни?
- Дали има простор за манипулација со бодовите?
- Дали најниската цена е единствен критериум (или не)?

4. ВРЕМЕНСКА АНАЛИЗА
- Дали рокот за поднесување понуди е прекраток?
- Дали има сомнителни промени на рокови?

Врати JSON со следниот формат:
{{
    "summary": "Краток опис на наодите (2-3 реченици)",
    "technical_requirements": {{
        "restrictive_level": "low/medium/high",
        "brand_mentions": ["листа на споменати брендови"],
        "unusual_specifications": ["листа на необични спецификации"],
        "analysis": "детална анализа"
    }},
    "qualification_criteria": {{
        "restrictive_level": "low/medium/high",
        "unusual_requirements": ["листа"],
        "analysis": "детална анализа"
    }},
    "evaluation_criteria": {{
        "subjectivity_level": "low/medium/high",
        "concerns": ["листа на загрижености"],
        "analysis": "детална анализа"
    }},
    "timeline": {{
        "deadline_concerns": true/false,
        "analysis": "анализа на временската рамка"
    }},
    "red_flags": [
        {{
            "type": "тип на црвено знаме",
            "severity": "low/medium/high/critical",
            "evidence": "цитат од документот",
            "confidence": 0.0-1.0,
            "description": "опис",
            "recommendation": "препорака"
        }}
    ],
    "overall_risk": "low/medium/high/critical",
    "risk_score": 0.0-1.0
}}"""

        # Run LLM analysis
        analysis = await self._analyze_with_llm(prompt, max_tokens=6000)

        if not analysis:
            return {
                'error': 'LLM analysis failed',
                'tender_id': tender_id,
                'documents_found': len(documents),
                'timestamp': datetime.utcnow().isoformat(),
            }

        # Build result
        red_flags = []
        for rf_data in analysis.get('red_flags', []):
            try:
                red_flags.append(RedFlag(
                    flag_type=rf_data.get('type', 'unknown'),
                    severity=Severity(rf_data.get('severity', 'low')),
                    evidence=rf_data.get('evidence', ''),
                    confidence=float(rf_data.get('confidence', 0.5)),
                    document_reference=documents[0].file_name if documents else 'unknown',
                    description=rf_data.get('description', ''),
                    recommendation=rf_data.get('recommendation', ''),
                ))
            except Exception as e:
                logger.warning(f"Error parsing red flag: {e}")

        result = AnalysisResult(
            tender_id=tender_id,
            analysis_type='comprehensive',
            timestamp=datetime.utcnow(),
            red_flags=red_flags,
            summary=analysis.get('summary', ''),
            details={
                'technical_requirements': analysis.get('technical_requirements', {}),
                'qualification_criteria': analysis.get('qualification_criteria', {}),
                'evaluation_criteria': analysis.get('evaluation_criteria', {}),
                'timeline': analysis.get('timeline', {}),
                'tender_info': tender_info,
            },
            overall_risk_score=float(analysis.get('risk_score', 0)),
            documents_analyzed=[d.file_name for d in documents[:5]],
        )

        return result.to_dict()

    async def detect_tailored_specifications(self, tender_id: str) -> Dict:
        """
        CRITICAL: Detect if specifications are tailored to specific vendor.

        Analyzes specification text to identify:
        - Brand names mentioned unnecessarily
        - Very specific technical requirements
        - Unusual certification requirements
        - Requirements matching only one vendor's products
        - Restrictive language
        - Unnecessary specificity
        - References to specific products/brands

        Args:
            tender_id: The tender ID to analyze

        Returns:
            Tailored specifications analysis
        """
        logger.info(f"Detecting tailored specifications for tender {tender_id}")

        documents = await self._get_tender_documents(tender_id)
        tender_info = await self._get_tender_info(tender_id)

        # Focus on specification documents
        spec_docs = [d for d in documents if d.is_specification]
        if not spec_docs:
            spec_docs = documents[:3]  # Fallback to first 3 documents

        if not spec_docs:
            return {
                'error': 'No specification documents found',
                'tender_id': tender_id,
                'timestamp': datetime.utcnow().isoformat(),
            }

        # Combine specification content
        spec_content = ""
        for doc in spec_docs[:3]:
            truncated = doc.content_text[:10000]
            spec_content += f"\n\n=== {doc.file_name} ===\n{truncated}"

        prompt = f"""Ти си форензичар за јавни набавки. Твоја задача е да детектираш дали техничките спецификации
се НАМЕРНО кроени за специфичен добавувач.

НАСЛОВ НА ТЕНДЕРОТ: {tender_info.get('title', 'N/A') if tender_info else 'N/A'}
CPV КОД: {tender_info.get('cpv_code', 'N/A') if tender_info else 'N/A'}
ПОБЕДНИК: {tender_info.get('winner', 'Непознат') if tender_info else 'Непознат'}

ТЕХНИЧКИ СПЕЦИФИКАЦИИ:
{spec_content[:25000]}

АНАЛИЗИРАЈ ЗА СЛЕДНИВЕ ЗНАЦИ НА "TAILORED" СПЕЦИФИКАЦИИ:

1. НЕПОТРЕБНИ БРЕНДОВИ
- Дали има споменати конкретни брендови (пр. "Samsung", "HP", "Siemens")?
- Дали е додадено "или еквивалент" или е инсистирано на конкретен бренд?

2. ПРЕСПЕЦИФИЧНИ ТЕХНИЧКИ БАРАЊА
- Дали спецификациите се толку детални што само еден производ ги исполнува?
- Пример: "Процесор со точно 3.47 GHz" наместо "минимум 3.4 GHz"

3. НЕОБИЧНИ СЕРТИФИКАТИ
- Дали се бараат сертификати што ги има само една компанија?
- Дали се бараат патенти или лиценци специфични за еден добавувач?

4. РЕСТРИКТИВЕН ЈАЗИК
- "Мора да биде точно..." наместо "минимум..."
- "Само од производител X..."
- "Идентичен со моделот..."

5. КОМБИНАЦИЈА НА БАРАЊА
- Дали комбинацијата на барања е толку специфична што само еден производ ги има сите?

Врати JSON:
{{
    "is_tailored": true/false,
    "tailoring_confidence": 0.0-1.0,
    "summary": "резиме на наодите",
    "brand_mentions": [
        {{
            "brand": "име на бренд",
            "context": "контекст во кој е споменат",
            "has_equivalent_clause": true/false,
            "suspicion_level": "low/medium/high"
        }}
    ],
    "overly_specific_requirements": [
        {{
            "requirement": "цитат на барањето",
            "why_suspicious": "зошто е сомнително",
            "normal_alternative": "како би требало да изгледа нормално барање"
        }}
    ],
    "unusual_certifications": [
        {{
            "certification": "име на сертификат",
            "why_unusual": "зошто е необично"
        }}
    ],
    "restrictive_language": [
        {{
            "quote": "цитат",
            "issue": "проблем"
        }}
    ],
    "potential_beneficiary": "проценка кој би можел да биде фаворизиран (ако може да се идентификува)",
    "red_flags": [
        {{
            "type": "tailored_specification",
            "severity": "low/medium/high/critical",
            "evidence": "доказ",
            "confidence": 0.0-1.0,
            "description": "опис"
        }}
    ],
    "recommendations": ["листа на препораки за понатамошна истрага"]
}}"""

        analysis = await self._analyze_with_llm(prompt, max_tokens=5000)

        if not analysis:
            return {
                'error': 'Analysis failed',
                'tender_id': tender_id,
                'timestamp': datetime.utcnow().isoformat(),
            }

        # Parse red flags
        red_flags = []
        for rf_data in analysis.get('red_flags', []):
            try:
                red_flags.append(RedFlag(
                    flag_type=rf_data.get('type', 'tailored_specification'),
                    severity=Severity(rf_data.get('severity', 'medium')),
                    evidence=rf_data.get('evidence', ''),
                    confidence=float(rf_data.get('confidence', 0.5)),
                    document_reference=spec_docs[0].file_name if spec_docs else 'unknown',
                    description=rf_data.get('description', ''),
                ))
            except Exception as e:
                logger.warning(f"Error parsing red flag: {e}")

        return {
            'tender_id': tender_id,
            'analysis_type': 'tailored_specifications',
            'timestamp': datetime.utcnow().isoformat(),
            'is_tailored': analysis.get('is_tailored', False),
            'tailoring_confidence': analysis.get('tailoring_confidence', 0),
            'summary': analysis.get('summary', ''),
            'brand_mentions': analysis.get('brand_mentions', []),
            'overly_specific_requirements': analysis.get('overly_specific_requirements', []),
            'unusual_certifications': analysis.get('unusual_certifications', []),
            'restrictive_language': analysis.get('restrictive_language', []),
            'potential_beneficiary': analysis.get('potential_beneficiary', ''),
            'red_flags': [rf.to_dict() for rf in red_flags],
            'recommendations': analysis.get('recommendations', []),
            'documents_analyzed': [d.file_name for d in spec_docs[:3]],
            'risk_score': self._calculate_risk_score(red_flags),
        }

    async def analyze_contract(self, tender_id: str) -> Dict:
        """
        Analyze contract documents for red flags.

        Analyzes:
        - Price vs estimated value
        - Payment terms (advance payments?)
        - Amendment clauses
        - Penalty clauses (or lack thereof)
        - Duration and extension provisions

        Args:
            tender_id: The tender ID to analyze

        Returns:
            Contract analysis results
        """
        logger.info(f"Analyzing contract for tender {tender_id}")

        documents = await self._get_tender_documents(tender_id)
        tender_info = await self._get_tender_info(tender_id)

        # Focus on contract documents
        contract_docs = [d for d in documents if d.is_contract]
        if not contract_docs:
            contract_docs = documents[:2]  # Fallback

        if not contract_docs:
            return {
                'error': 'No contract documents found',
                'tender_id': tender_id,
                'timestamp': datetime.utcnow().isoformat(),
            }

        # Combine contract content
        contract_content = ""
        for doc in contract_docs[:2]:
            truncated = doc.content_text[:12000]
            contract_content += f"\n\n=== {doc.file_name} ===\n{truncated}"

        estimated_value = tender_info.get('estimated_value_mkd', 'непознато') if tender_info else 'непознато'
        actual_value = tender_info.get('actual_value_mkd', 'непознато') if tender_info else 'непознато'

        prompt = f"""Ти си правен експерт за анализа на договори за јавни набавки.
Анализирај го договорот за потенцијални црвени знамиња за корупција.

ПРОЦЕНЕТА ВРЕДНОСТ: {estimated_value} МКД
ДОГОВОРЕНА ВРЕДНОСТ: {actual_value} МКД
ПОБЕДНИК: {tender_info.get('winner', 'непознато') if tender_info else 'непознато'}

ДОГОВОР:
{contract_content[:25000]}

АНАЛИЗИРАЈ ЗА:

1. ЦЕНА VS ПРОЦЕНЕТА ВРЕДНОСТ
- Дали договорената цена е многу поблиску до максимумот?
- Дали има разлика помеѓу проценката и договореното (колку %)?

2. УСЛОВИ ЗА ПЛАЌАЊЕ
- Дали има авансно плаќање? Колку %?
- Дали плаќањето е по испорака или однапред?
- Дали роковите за плаќање се необично кратки/долги?

3. КЛАУЗУЛИ ЗА ИЗМЕНИ (АНЕКСИ)
- Дали договорот дозволува лесни измени без нов тендер?
- Дали има можност за зголемување на вредноста?

4. ПЕНАЛИ И КАЗНИ
- ДАЛИ ПОСТОЈАТ клаузули за пенали при доцнење?
- Дали пеналите се доволно строги?
- КРИТИЧНО: Недостаток на пенали = црвено знаме

5. ТРАЕЊЕ И ПРОДОЛЖУВАЊЕ
- Дали траењето е соодветно за типот на набавка?
- Дали има автоматско продолжување?

Врати JSON:
{{
    "summary": "резиме на анализата",
    "price_analysis": {{
        "estimated_value": number_or_null,
        "contract_value": number_or_null,
        "difference_percent": number_or_null,
        "concern_level": "low/medium/high",
        "analysis": "детален опис"
    }},
    "payment_terms": {{
        "advance_payment_percent": number_or_null,
        "payment_schedule": "опис на распоредот",
        "concern_level": "low/medium/high",
        "issues": ["листа на проблеми"]
    }},
    "amendment_clauses": {{
        "allows_easy_amendments": true/false,
        "max_value_increase_allowed": "проценка",
        "concern_level": "low/medium/high",
        "analysis": "опис"
    }},
    "penalty_clauses": {{
        "has_delay_penalties": true/false,
        "penalty_rate": "стапка ако е наведена",
        "has_quality_penalties": true/false,
        "adequacy": "low/medium/high",
        "concern_level": "low/medium/high",
        "analysis": "опис"
    }},
    "duration": {{
        "contract_duration": "траење",
        "has_auto_renewal": true/false,
        "concern_level": "low/medium/high"
    }},
    "red_flags": [
        {{
            "type": "contract_issue",
            "severity": "low/medium/high/critical",
            "evidence": "доказ",
            "confidence": 0.0-1.0,
            "description": "опис",
            "recommendation": "препорака"
        }}
    ],
    "overall_contract_risk": "low/medium/high/critical"
}}"""

        analysis = await self._analyze_with_llm(prompt, max_tokens=5000)

        if not analysis:
            return {
                'error': 'Contract analysis failed',
                'tender_id': tender_id,
                'timestamp': datetime.utcnow().isoformat(),
            }

        # Parse red flags
        red_flags = []
        for rf_data in analysis.get('red_flags', []):
            try:
                red_flags.append(RedFlag(
                    flag_type=rf_data.get('type', 'contract_issue'),
                    severity=Severity(rf_data.get('severity', 'medium')),
                    evidence=rf_data.get('evidence', ''),
                    confidence=float(rf_data.get('confidence', 0.5)),
                    document_reference=contract_docs[0].file_name if contract_docs else 'unknown',
                    description=rf_data.get('description', ''),
                    recommendation=rf_data.get('recommendation', ''),
                ))
            except Exception as e:
                logger.warning(f"Error parsing red flag: {e}")

        return {
            'tender_id': tender_id,
            'analysis_type': 'contract_analysis',
            'timestamp': datetime.utcnow().isoformat(),
            'summary': analysis.get('summary', ''),
            'price_analysis': analysis.get('price_analysis', {}),
            'payment_terms': analysis.get('payment_terms', {}),
            'amendment_clauses': analysis.get('amendment_clauses', {}),
            'penalty_clauses': analysis.get('penalty_clauses', {}),
            'duration': analysis.get('duration', {}),
            'red_flags': [rf.to_dict() for rf in red_flags],
            'overall_contract_risk': analysis.get('overall_contract_risk', 'unknown'),
            'documents_analyzed': [d.file_name for d in contract_docs[:2]],
            'risk_score': self._calculate_risk_score(red_flags),
        }

    async def extract_pricing_details(self, tender_id: str) -> Dict:
        """
        Extract detailed pricing from documents.

        Extracts:
        - Unit prices
        - Total amounts
        - Compare with market prices (if available)
        - Compare with similar past tenders

        Args:
            tender_id: The tender ID to analyze

        Returns:
            Pricing extraction results
        """
        logger.info(f"Extracting pricing details for tender {tender_id}")

        documents = await self._get_tender_documents(tender_id)
        tender_info = await self._get_tender_info(tender_id)

        if not documents:
            return {
                'error': 'No documents found',
                'tender_id': tender_id,
                'timestamp': datetime.utcnow().isoformat(),
            }

        # Combine document content
        doc_content = ""
        for doc in documents[:4]:
            truncated = doc.content_text[:8000]
            doc_content += f"\n\n=== {doc.file_name} ===\n{truncated}"

        # Get similar tenders for comparison
        cpv_code = tender_info.get('cpv_code') if tender_info else None
        similar_prices = await self._get_similar_tender_prices(cpv_code) if cpv_code else []

        similar_context = ""
        if similar_prices:
            similar_context = "\n\nСЛИЧНИ ТЕНДЕРИ ЗА СПОРЕДБА:\n"
            for sp in similar_prices[:5]:
                similar_context += f"- {sp.get('title', 'N/A')}: {sp.get('actual_value_mkd', 'N/A')} МКД\n"

        prompt = f"""Ти си финансиски аналитичар. Извлечи ги сите детали за цени од документите.

ТЕНДЕР: {tender_info.get('title', 'N/A') if tender_info else 'N/A'}
ПРОЦЕНЕТА ВРЕДНОСТ: {tender_info.get('estimated_value_mkd', 'N/A') if tender_info else 'N/A'} МКД
ДОГОВОРЕНА ВРЕДНОСТ: {tender_info.get('actual_value_mkd', 'N/A') if tender_info else 'N/A'} МКД
{similar_context}

ДОКУМЕНТИ:
{doc_content[:25000]}

ИЗВЛЕЧИ:

1. ЕДИНЕЧНИ ЦЕНИ
- Идентификувај секоја ставка со цена
- Извлечи единечна цена, количина, единица мерка

2. ВКУПНИ ИЗНОСИ
- Вкупна вредност по ставка
- Вкупна вредност на договорот

3. СПОРЕДБА СО СЛИЧНИ ТЕНДЕРИ
- Ако има податоци за слични тендери, споредби ги цените

4. АНОМАЛИИ
- Дали некоја цена е необично висока/ниска?
- Дали има позиции со преголема разлика од вообичаено?

Врати JSON:
{{
    "summary": "резиме на ценовната анализа",
    "items_with_prices": [
        {{
            "item_name": "име на ставка",
            "unit": "единица мерка",
            "quantity": number_or_null,
            "unit_price": number_or_null,
            "total_price": number_or_null,
            "currency": "МКД/ЕУР"
        }}
    ],
    "total_contract_value": number_or_null,
    "estimated_value": number_or_null,
    "price_to_estimate_ratio": number_or_null,
    "comparison_with_similar": {{
        "average_similar_value": number_or_null,
        "deviation_percent": number_or_null,
        "is_significantly_higher": true/false
    }},
    "price_anomalies": [
        {{
            "item": "ставка",
            "issue": "опис на проблемот",
            "expected_range": "очекуван ранг",
            "actual_price": "реална цена",
            "severity": "low/medium/high"
        }}
    ],
    "red_flags": [
        {{
            "type": "pricing_anomaly",
            "severity": "low/medium/high/critical",
            "evidence": "доказ",
            "confidence": 0.0-1.0,
            "description": "опис"
        }}
    ]
}}"""

        analysis = await self._analyze_with_llm(prompt, max_tokens=5000)

        if not analysis:
            return {
                'error': 'Pricing extraction failed',
                'tender_id': tender_id,
                'timestamp': datetime.utcnow().isoformat(),
            }

        # Parse red flags
        red_flags = []
        for rf_data in analysis.get('red_flags', []):
            try:
                red_flags.append(RedFlag(
                    flag_type=rf_data.get('type', 'pricing_anomaly'),
                    severity=Severity(rf_data.get('severity', 'medium')),
                    evidence=rf_data.get('evidence', ''),
                    confidence=float(rf_data.get('confidence', 0.5)),
                    document_reference=documents[0].file_name if documents else 'unknown',
                    description=rf_data.get('description', ''),
                ))
            except Exception as e:
                logger.warning(f"Error parsing red flag: {e}")

        return {
            'tender_id': tender_id,
            'analysis_type': 'pricing_extraction',
            'timestamp': datetime.utcnow().isoformat(),
            'summary': analysis.get('summary', ''),
            'items_with_prices': analysis.get('items_with_prices', []),
            'total_contract_value': analysis.get('total_contract_value'),
            'estimated_value': analysis.get('estimated_value'),
            'price_to_estimate_ratio': analysis.get('price_to_estimate_ratio'),
            'comparison_with_similar': analysis.get('comparison_with_similar', {}),
            'price_anomalies': analysis.get('price_anomalies', []),
            'red_flags': [rf.to_dict() for rf in red_flags],
            'documents_analyzed': [d.file_name for d in documents[:4]],
            'risk_score': self._calculate_risk_score(red_flags),
        }

    async def _get_similar_tender_prices(self, cpv_code: str, limit: int = 10) -> List[Dict]:
        """Get prices from similar tenders with same CPV code"""
        if not cpv_code:
            return []

        pool = await self._get_pool()

        # Use first 5 digits of CPV for broader matching
        cpv_prefix = cpv_code[:5]

        query = """
            SELECT
                tender_id,
                title,
                actual_value_mkd,
                estimated_value_mkd,
                procuring_entity,
                winner,
                opening_date
            FROM tenders
            WHERE cpv_code LIKE $1
            AND actual_value_mkd IS NOT NULL
            ORDER BY opening_date DESC
            LIMIT $2
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, f"{cpv_prefix}%", limit)

        return [dict(row) for row in rows]

    async def analyze_evaluation_report(self, tender_id: str) -> Dict:
        """
        Analyze evaluation report for irregularities.

        If evaluation report exists, analyzes:
        - Scoring methodology
        - Score differences between bidders
        - Justification for winner selection
        - Any irregularities in evaluation

        Args:
            tender_id: The tender ID to analyze

        Returns:
            Evaluation analysis results
        """
        logger.info(f"Analyzing evaluation report for tender {tender_id}")

        documents = await self._get_tender_documents(tender_id)
        tender_info = await self._get_tender_info(tender_id)

        # Focus on evaluation documents
        eval_docs = [d for d in documents if d.is_evaluation]
        if not eval_docs:
            # Look for keywords in content
            for doc in documents:
                if any(kw in doc.content_text.lower()[:500]
                       for kw in ['евалуација', 'бодови', 'scoring', 'оценка', 'рангирање']):
                    eval_docs.append(doc)

        if not eval_docs:
            return {
                'error': 'No evaluation documents found',
                'tender_id': tender_id,
                'timestamp': datetime.utcnow().isoformat(),
                'suggestion': 'Consider manual review of tender documents for evaluation data',
            }

        # Combine evaluation content
        eval_content = ""
        for doc in eval_docs[:2]:
            truncated = doc.content_text[:12000]
            eval_content += f"\n\n=== {doc.file_name} ===\n{truncated}"

        prompt = f"""Ти си експерт за анализа на евалуација на понуди во јавни набавки.
Анализирај го извештајот за евалуација за потенцијални неправилности.

ТЕНДЕР: {tender_info.get('title', 'N/A') if tender_info else 'N/A'}
ПОБЕДНИК: {tender_info.get('winner', 'N/A') if tender_info else 'N/A'}
БРОЈ НА ПОНУДУВАЧИ: {tender_info.get('num_bidders', 'N/A') if tender_info else 'N/A'}
МЕТОД НА ЕВАЛУАЦИЈА: {tender_info.get('evaluation_method', 'N/A') if tender_info else 'N/A'}

ДОКУМЕНТ ЗА ЕВАЛУАЦИЈА:
{eval_content[:25000]}

АНАЛИЗИРАЈ:

1. МЕТОДОЛОГИЈА НА БОДУВАЊЕ
- Дали критериумите се јасни и објективни?
- Дали тежините на критериумите се разумни?
- Дали има субјективни критериуми со голема тежина?

2. РАЗЛИКИ ВО БОДОВИ
- Колкава е разликата меѓу победникот и вториот?
- Дали некој понудувач има неочекувано ниски бодови на еден критериум?

3. ОБРАЗЛОЖЕНИЕ ЗА ИЗБОР
- Дали изборот на победник е добро образложен?
- Дали има документирана анализа на понудите?

4. НЕПРАВИЛНОСТИ
- Дали има дисквалификувани понудувачи? Зошто?
- Дали причините за дисквалификација се легитимни?
- Дали има знаци на манипулација со бодовите?

Врати JSON:
{{
    "summary": "резиме на евалуацијата",
    "scoring_methodology": {{
        "is_clear": true/false,
        "criteria": [
            {{
                "criterion": "име",
                "weight": "тежина",
                "objectivity": "objective/subjective/mixed"
            }}
        ],
        "concern_level": "low/medium/high",
        "analysis": "опис"
    }},
    "score_differences": {{
        "winner_score": number_or_null,
        "second_place_score": number_or_null,
        "gap_percent": number_or_null,
        "is_narrow_margin": true/false,
        "all_scores": [
            {{
                "bidder": "име",
                "score": number_or_null,
                "rank": number
            }}
        ]
    }},
    "winner_justification": {{
        "is_well_documented": true/false,
        "concerns": ["листа на загрижености"]
    }},
    "disqualifications": [
        {{
            "bidder": "име на понудувач",
            "reason": "причина",
            "is_legitimate": true/false,
            "concern": "загриженост ако има"
        }}
    ],
    "irregularities": [
        {{
            "type": "тип",
            "description": "опис",
            "severity": "low/medium/high"
        }}
    ],
    "red_flags": [
        {{
            "type": "evaluation_irregularity",
            "severity": "low/medium/high/critical",
            "evidence": "доказ",
            "confidence": 0.0-1.0,
            "description": "опис"
        }}
    ],
    "overall_evaluation_integrity": "low/medium/high"
}}"""

        analysis = await self._analyze_with_llm(prompt, max_tokens=5000)

        if not analysis:
            return {
                'error': 'Evaluation analysis failed',
                'tender_id': tender_id,
                'timestamp': datetime.utcnow().isoformat(),
            }

        # Parse red flags
        red_flags = []
        for rf_data in analysis.get('red_flags', []):
            try:
                red_flags.append(RedFlag(
                    flag_type=rf_data.get('type', 'evaluation_irregularity'),
                    severity=Severity(rf_data.get('severity', 'medium')),
                    evidence=rf_data.get('evidence', ''),
                    confidence=float(rf_data.get('confidence', 0.5)),
                    document_reference=eval_docs[0].file_name if eval_docs else 'unknown',
                    description=rf_data.get('description', ''),
                ))
            except Exception as e:
                logger.warning(f"Error parsing red flag: {e}")

        return {
            'tender_id': tender_id,
            'analysis_type': 'evaluation_analysis',
            'timestamp': datetime.utcnow().isoformat(),
            'summary': analysis.get('summary', ''),
            'scoring_methodology': analysis.get('scoring_methodology', {}),
            'score_differences': analysis.get('score_differences', {}),
            'winner_justification': analysis.get('winner_justification', {}),
            'disqualifications': analysis.get('disqualifications', []),
            'irregularities': analysis.get('irregularities', []),
            'red_flags': [rf.to_dict() for rf in red_flags],
            'overall_evaluation_integrity': analysis.get('overall_evaluation_integrity', 'unknown'),
            'documents_analyzed': [d.file_name for d in eval_docs[:2]],
            'risk_score': self._calculate_risk_score(red_flags),
        }

    async def compare_with_similar_tenders(self, tender_id: str) -> Dict:
        """
        Compare this tender's documents with similar tenders.

        Compares with tenders that have:
        - Same CPV code
        - Same institution
        - Similar value

        Looks for:
        - Copy-paste specifications (same company winning?)
        - Price consistency/anomalies
        - Document template patterns

        Args:
            tender_id: The tender ID to analyze

        Returns:
            Comparison analysis results
        """
        logger.info(f"Comparing tender {tender_id} with similar tenders")

        tender_info = await self._get_tender_info(tender_id)
        documents = await self._get_tender_documents(tender_id)

        if not tender_info:
            return {
                'error': f'Tender {tender_id} not found',
                'tender_id': tender_id,
                'timestamp': datetime.utcnow().isoformat(),
            }

        # Find similar tenders
        similar_tenders = await self._find_similar_tenders(tender_info)

        if not similar_tenders:
            return {
                'tender_id': tender_id,
                'analysis_type': 'similar_tender_comparison',
                'timestamp': datetime.utcnow().isoformat(),
                'message': 'No similar tenders found for comparison',
                'tender_info': tender_info,
            }

        # Get documents from similar tenders
        similar_docs = []
        for st in similar_tenders[:3]:
            st_docs = await self._get_tender_documents(st['tender_id'])
            if st_docs:
                similar_docs.append({
                    'tender': st,
                    'documents': st_docs[:2],
                })

        # Prepare comparison content
        current_content = ""
        for doc in documents[:2]:
            current_content += f"\n{doc.content_text[:5000]}"

        similar_content = ""
        for sd in similar_docs[:2]:
            similar_content += f"\n\n=== СЛИЧЕН ТЕНДЕР: {sd['tender']['title'][:100]} ===\n"
            similar_content += f"Победник: {sd['tender'].get('winner', 'N/A')}\n"
            similar_content += f"Вредност: {sd['tender'].get('actual_value_mkd', 'N/A')} МКД\n"
            for doc in sd['documents'][:1]:
                similar_content += f"\n{doc.content_text[:3000]}"

        prompt = f"""Ти си истражувач за корупција. Споредби го овој тендер со слични тендери.

ТЕКОВЕН ТЕНДЕР:
- Наслов: {tender_info.get('title', 'N/A')}
- Набавувач: {tender_info.get('procuring_entity', 'N/A')}
- CPV: {tender_info.get('cpv_code', 'N/A')}
- Победник: {tender_info.get('winner', 'N/A')}
- Вредност: {tender_info.get('actual_value_mkd', 'N/A')} МКД

ДОКУМЕНТИ ОД ТЕКОВЕН ТЕНДЕР:
{current_content[:10000]}

СЛИЧНИ ТЕНДЕРИ:
{similar_content[:15000]}

СПОРЕДБИ И АНАЛИЗИРАЈ:

1. COPY-PASTE СПЕЦИФИКАЦИИ
- Дали спецификациите се идентични или многу слични со други тендери?
- Дали истата компанија победува секогаш кога има исти спецификации?

2. КОНЗИСТЕНТНОСТ НА ЦЕНИ
- Дали цените се конзистентни меѓу слични тендери?
- Дали има значителни разлики (±20%)?

3. ШАБЛОНИ НА ДОКУМЕНТИ
- Дали институцијата користи исти шаблони?
- Дали има "fingerprint" што укажува на заеднички извор?

4. ПАТТЕРНИ НА ПОБЕДНИЦИ
- Дали истата компанија постојано победува кај истата институција?
- Дали има ротација на победници или монопол?

Врати JSON:
{{
    "summary": "резиме на споредбата",
    "specification_similarity": {{
        "similarity_score": 0.0-1.0,
        "identical_sections": ["листа на идентични делови"],
        "is_copy_paste": true/false,
        "same_winner_pattern": true/false
    }},
    "price_comparison": {{
        "current_price": number_or_null,
        "average_similar_price": number_or_null,
        "deviation_percent": number_or_null,
        "is_anomalous": true/false,
        "analysis": "опис"
    }},
    "winner_patterns": {{
        "current_winner": "име",
        "wins_at_this_institution": number,
        "total_similar_wins": number,
        "market_concentration": "low/medium/high",
        "analysis": "опис"
    }},
    "document_patterns": {{
        "uses_common_template": true/false,
        "template_indicators": ["индикатори"],
        "analysis": "опис"
    }},
    "suspicious_patterns": [
        {{
            "pattern": "опис на паттернот",
            "evidence": "доказ",
            "severity": "low/medium/high"
        }}
    ],
    "red_flags": [
        {{
            "type": "pattern_anomaly",
            "severity": "low/medium/high/critical",
            "evidence": "доказ",
            "confidence": 0.0-1.0,
            "description": "опис"
        }}
    ],
    "recommendations": ["препораки за понатамошна истрага"]
}}"""

        analysis = await self._analyze_with_llm(prompt, max_tokens=5000)

        if not analysis:
            return {
                'error': 'Comparison analysis failed',
                'tender_id': tender_id,
                'timestamp': datetime.utcnow().isoformat(),
            }

        # Parse red flags
        red_flags = []
        for rf_data in analysis.get('red_flags', []):
            try:
                red_flags.append(RedFlag(
                    flag_type=rf_data.get('type', 'pattern_anomaly'),
                    severity=Severity(rf_data.get('severity', 'medium')),
                    evidence=rf_data.get('evidence', ''),
                    confidence=float(rf_data.get('confidence', 0.5)),
                    document_reference='cross-tender comparison',
                    description=rf_data.get('description', ''),
                ))
            except Exception as e:
                logger.warning(f"Error parsing red flag: {e}")

        return {
            'tender_id': tender_id,
            'analysis_type': 'similar_tender_comparison',
            'timestamp': datetime.utcnow().isoformat(),
            'summary': analysis.get('summary', ''),
            'similar_tenders_analyzed': len(similar_tenders),
            'specification_similarity': analysis.get('specification_similarity', {}),
            'price_comparison': analysis.get('price_comparison', {}),
            'winner_patterns': analysis.get('winner_patterns', {}),
            'document_patterns': analysis.get('document_patterns', {}),
            'suspicious_patterns': analysis.get('suspicious_patterns', []),
            'red_flags': [rf.to_dict() for rf in red_flags],
            'recommendations': analysis.get('recommendations', []),
            'risk_score': self._calculate_risk_score(red_flags),
        }

    async def _find_similar_tenders(self, tender_info: Dict, limit: int = 10) -> List[Dict]:
        """Find similar tenders based on CPV code and institution"""
        pool = await self._get_pool()

        cpv_code = tender_info.get('cpv_code')
        institution = tender_info.get('procuring_entity')
        tender_id = tender_info.get('tender_id')

        # Build query based on available info
        conditions = ["tender_id != $1"]
        params = [tender_id]
        param_idx = 2

        if cpv_code:
            cpv_prefix = cpv_code[:5]
            conditions.append(f"cpv_code LIKE ${param_idx}")
            params.append(f"{cpv_prefix}%")
            param_idx += 1

        if institution:
            conditions.append(f"procuring_entity ILIKE ${param_idx}")
            params.append(f"%{institution[:30]}%")
            param_idx += 1

        query = f"""
            SELECT
                tender_id,
                title,
                procuring_entity,
                cpv_code,
                actual_value_mkd,
                winner,
                opening_date
            FROM tenders
            WHERE {' OR '.join(conditions[1:])}
            AND tender_id != $1
            ORDER BY opening_date DESC
            LIMIT {limit}
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [dict(row) for row in rows]

    # ========================================================================
    # FULL CORRUPTION RISK ASSESSMENT
    # ========================================================================

    async def full_corruption_assessment(self, tender_id: str) -> Dict:
        """
        Run all analyses and provide comprehensive corruption risk assessment.

        This method runs:
        1. analyze_tender_documents
        2. detect_tailored_specifications
        3. analyze_contract
        4. extract_pricing_details
        5. analyze_evaluation_report
        6. compare_with_similar_tenders

        And aggregates all findings into a final risk assessment.

        Args:
            tender_id: The tender ID to analyze

        Returns:
            Comprehensive corruption risk assessment
        """
        logger.info(f"Running full corruption assessment for tender {tender_id}")

        start_time = datetime.utcnow()

        # Run all analyses in parallel where possible
        results = await asyncio.gather(
            self.analyze_tender_documents(tender_id),
            self.detect_tailored_specifications(tender_id),
            self.analyze_contract(tender_id),
            self.extract_pricing_details(tender_id),
            self.analyze_evaluation_report(tender_id),
            self.compare_with_similar_tenders(tender_id),
            return_exceptions=True,
        )

        # Process results
        analyses = {
            'comprehensive_analysis': results[0] if not isinstance(results[0], Exception) else {'error': str(results[0])},
            'tailored_specifications': results[1] if not isinstance(results[1], Exception) else {'error': str(results[1])},
            'contract_analysis': results[2] if not isinstance(results[2], Exception) else {'error': str(results[2])},
            'pricing_analysis': results[3] if not isinstance(results[3], Exception) else {'error': str(results[3])},
            'evaluation_analysis': results[4] if not isinstance(results[4], Exception) else {'error': str(results[4])},
            'similar_tender_comparison': results[5] if not isinstance(results[5], Exception) else {'error': str(results[5])},
        }

        # Aggregate all red flags
        all_red_flags = []
        for analysis_name, analysis_result in analyses.items():
            if isinstance(analysis_result, dict) and 'red_flags' in analysis_result:
                for rf in analysis_result['red_flags']:
                    rf['source_analysis'] = analysis_name
                    all_red_flags.append(rf)

        # Calculate overall risk score
        risk_scores = []
        for analysis in analyses.values():
            if isinstance(analysis, dict) and 'risk_score' in analysis:
                risk_scores.append(analysis['risk_score'])

        overall_risk_score = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0

        # Determine overall risk level
        if overall_risk_score >= 0.7:
            risk_level = 'CRITICAL'
        elif overall_risk_score >= 0.5:
            risk_level = 'HIGH'
        elif overall_risk_score >= 0.3:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'

        # Count flags by severity
        severity_counts = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
        for rf in all_red_flags:
            sev = rf.get('severity', 'low')
            if sev in severity_counts:
                severity_counts[sev] += 1

        end_time = datetime.utcnow()

        return {
            'tender_id': tender_id,
            'assessment_type': 'full_corruption_assessment',
            'timestamp': datetime.utcnow().isoformat(),
            'processing_time_seconds': (end_time - start_time).total_seconds(),
            'overall_risk_level': risk_level,
            'overall_risk_score': round(overall_risk_score, 3),
            'total_red_flags': len(all_red_flags),
            'red_flags_by_severity': severity_counts,
            'all_red_flags': all_red_flags,
            'individual_analyses': analyses,
            'executive_summary': self._generate_executive_summary(analyses, all_red_flags, risk_level),
            'recommended_actions': self._generate_recommendations(all_red_flags, risk_level),
        }

    def _generate_executive_summary(
        self,
        analyses: Dict,
        red_flags: List[Dict],
        risk_level: str
    ) -> str:
        """Generate executive summary from all analyses"""
        critical_count = sum(1 for rf in red_flags if rf.get('severity') == 'critical')
        high_count = sum(1 for rf in red_flags if rf.get('severity') == 'high')

        summary_parts = [f"Ниво на ризик: {risk_level}"]

        if critical_count > 0:
            summary_parts.append(f"Идентификувани {critical_count} КРИТИЧНИ црвени знамиња.")
        if high_count > 0:
            summary_parts.append(f"Идентификувани {high_count} ВИСОКИ црвени знамиња.")

        # Add specific findings
        tailored = analyses.get('tailored_specifications', {})
        if isinstance(tailored, dict) and tailored.get('is_tailored'):
            summary_parts.append("ПРЕДУПРЕДУВАЊЕ: Спецификациите изгледаат кроени за специфичен добавувач.")

        contract = analyses.get('contract_analysis', {})
        if isinstance(contract, dict):
            penalties = contract.get('penalty_clauses', {})
            if isinstance(penalties, dict) and not penalties.get('has_delay_penalties'):
                summary_parts.append("ЗАГРИЖЕНОСТ: Договорот нема клаузули за пенали.")

        pricing = analyses.get('pricing_analysis', {})
        if isinstance(pricing, dict):
            comparison = pricing.get('comparison_with_similar', {})
            if isinstance(comparison, dict) and comparison.get('is_significantly_higher'):
                summary_parts.append("АНОМАЛИЈА: Цената е значително повисока од слични тендери.")

        return " ".join(summary_parts)

    def _generate_recommendations(
        self,
        red_flags: List[Dict],
        risk_level: str
    ) -> List[str]:
        """Generate recommended actions based on findings"""
        recommendations = []

        if risk_level in ['CRITICAL', 'HIGH']:
            recommendations.append("Препорачуваме детална ревизија од надлежни органи")
            recommendations.append("Побарајте дополнителна документација од набавувачот")

        flag_types = set(rf.get('type', '') for rf in red_flags)

        if 'tailored_specification' in flag_types:
            recommendations.append("Проверете дали спецификациите дозволуваат еквивалентни производи")

        if 'contract_issue' in flag_types:
            recommendations.append("Прегледајте ги договорните услови со правен експерт")

        if 'pricing_anomaly' in flag_types:
            recommendations.append("Споредете ги цените со пазарни референци")

        if 'evaluation_irregularity' in flag_types:
            recommendations.append("Побарајте детален извештај за евалуација")

        if 'pattern_anomaly' in flag_types:
            recommendations.append("Истражете ги историските набавки на оваа институција")

        if not recommendations:
            recommendations.append("Нема специфични препораки - ризикот е низок")

        return recommendations


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def analyze_tender(tender_id: str) -> Dict:
    """
    Quick function to analyze a tender.

    Usage:
        result = await analyze_tender("123456/2024")
        print(result['overall_risk_level'])
    """
    agent = DocumentAnalysisAgent()
    try:
        return await agent.full_corruption_assessment(tender_id)
    finally:
        await agent.close()


async def check_tailored_specs(tender_id: str) -> Dict:
    """
    Quick function to check for tailored specifications.

    Usage:
        result = await check_tailored_specs("123456/2024")
        print(result['is_tailored'])
    """
    agent = DocumentAnalysisAgent()
    try:
        return await agent.detect_tailored_specifications(tender_id)
    finally:
        await agent.close()


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    import asyncio

    async def main():
        # Example usage
        agent = DocumentAnalysisAgent()

        try:
            # Test with a sample tender ID
            tender_id = "00215-2024-0041"  # Replace with actual tender ID

            print(f"Analyzing tender: {tender_id}")
            print("-" * 50)

            # Run full assessment
            result = await agent.full_corruption_assessment(tender_id)

            print(f"\nRisk Level: {result.get('overall_risk_level')}")
            print(f"Risk Score: {result.get('overall_risk_score')}")
            print(f"Total Red Flags: {result.get('total_red_flags')}")
            print(f"\nExecutive Summary:")
            print(result.get('executive_summary'))
            print(f"\nRecommendations:")
            for rec in result.get('recommended_actions', []):
                print(f"  - {rec}")

        finally:
            await agent.close()

    asyncio.run(main())
