#!/usr/bin/env python3
"""
Corruption Research Orchestrator - The BRAIN of the Corruption Detection System

This module coordinates all research agents, runs them in parallel, and uses
LLM (Gemini) to synthesize findings into intelligent corruption assessments.

Architecture:
- Imports and coordinates 6 specialized agents:
  1. DBResearchAgent - queries our PostgreSQL database
  2. WebResearchAgent - web searches for news, controversies
  3. ENabavkiAgent - official e-nabavki.gov.mk data
  4. EPazarAgent - e-pazar.mk electronic marketplace data (NEW)
  5. CompanyResearchAgent - company ownership, connections
  6. DocumentAnalysisAgent - specification and contract analysis

Key Principles:
1. NEVER flag based on single source - require corroboration
2. Official sources (e-nabavki) trump our DB when they conflict
3. Weight evidence by source reliability
4. Include uncertainty/confidence in all assessments
5. Provide evidence trail for every finding
6. Generate human-readable summaries in Macedonian

Author: nabavkidata.com
License: Proprietary
"""

import asyncio
import asyncpg
import logging
import json
import os
from dotenv import load_dotenv
load_dotenv()
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from decimal import Decimal
import re
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Import existing agents
from ai.agents.db_research_agent import (
    DBResearchAgent,
    TenderResearch,
    CompanyResearch,
    InstitutionResearch
)
from ai.agents.web_research_agent import WebResearchAgent, ResearchReport
from ai.agents.enabavki_agent import (
    ENabavkiAgent,
    TenderDetails,
    OfficialBidderData,
    VerificationResult,
    DataDiscrepancy
)
from ai.agents.company_research_agent import (
    CompanyResearchAgent,
    CompanyProfile,
    OwnershipInfo,
    RelatedCompany,
    PoliticalConnection,
    ShellCompanyIndicator
)
from ai.agents.document_analysis_agent import (
    DocumentAnalysisAgent,
    RedFlag,
    Severity,
    AnalysisResult
)
from ai.agents.epazar_agent import (
    EPazarAgent,
    EPazarTender,
    EPazarSearchResult
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration from environment
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'nabavki_user'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'nabavkidata')
}

DB_URL = os.getenv('DATABASE_URL', f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}")

# Gemini API Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Safety settings to prevent content blocking
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# Initialize Gemini (only if API key is available)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API configured successfully")
else:
    logger.warning("GEMINI_API_KEY not set - LLM synthesis will be disabled, falling back to rule-based analysis")
# =============================================================================
# Data Classes for Research Results
# =============================================================================

@dataclass
class ResearchFinding:
    """Individual finding from research"""
    source: str  # 'db', 'web', 'enabavki', 'company', 'document'
    finding_type: str  # 'red_flag', 'info', 'connection', 'anomaly', 'discrepancy'
    description: str
    evidence: Dict[str, Any]
    confidence: float  # 0.0 - 1.0
    severity: str  # 'low', 'medium', 'high', 'critical'

    def to_dict(self) -> Dict:
        return asdict(self)
@dataclass
class CorruptionAssessment:
    """Synthesized corruption risk assessment"""
    entity_type: str  # 'tender', 'company', 'institution'
    entity_id: str
    entity_name: str
    risk_score: int  # 0-100
    risk_level: str  # 'minimal', 'low', 'medium', 'high', 'critical'
    findings: List[ResearchFinding]
    evidence_summary: Dict[str, Any]
    confidence: float  # Overall confidence in assessment (0.0-1.0)
    recommendations: List[str]
    summary_mk: str  # Macedonian language summary
    summary_en: str  # English summary
    data_quality: Dict[str, Any]  # Info about data completeness
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['findings'] = [f.to_dict() if hasattr(f, 'to_dict') else f for f in self.findings]
        return result
@dataclass
class DataConsistencyReport:
    """Report comparing our DB with official sources"""
    is_consistent: bool
    discrepancies: List[Dict[str, Any]]
    our_data: Dict[str, Any]
    official_data: Dict[str, Any]
    recommendations: List[str]
# =============================================================================
# Main Orchestrator Class
# =============================================================================

class CorruptionResearchOrchestrator:
    """
    The BRAIN of the corruption detection system.

    Coordinates all research agents, runs them in parallel, and uses
    Gemini LLM to synthesize findings into intelligent assessments.
    """

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

        # Initialize agents (6 specialized research agents)
        self.db_agent: Optional[DBResearchAgent] = None
        self.web_agent: Optional[WebResearchAgent] = None
        self.enabavki_agent: Optional[ENabavkiAgent] = None
        self.epazar_agent: Optional[EPazarAgent] = None  # NEW: E-Pazar agent
        self.company_agent: Optional[CompanyResearchAgent] = None
        self.document_agent: Optional[DocumentAnalysisAgent] = None

        # LLM model for synthesis (only if Gemini is configured)
        self.synthesis_model = None
        if GEMINI_API_KEY:
            try:
                self.synthesis_model = genai.GenerativeModel('gemini-2.0-flash')
                logger.info("LLM synthesis model initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM model: {e}")
        else:
            logger.info("LLM synthesis disabled - will use rule-based analysis only")

        logger.info("CorruptionResearchOrchestrator initialized")

    async def initialize(self):
        """Initialize database connection and agents"""
        logger.info("Initializing database connection and agents...")

        try:
            # Create database pool
            self.pool = await asyncpg.create_pool(
                DB_URL,
                min_size=2,
                max_size=10,
                command_timeout=60
            )

            # Initialize all agents (6 specialized research agents)
            self.db_agent = DBResearchAgent(self.pool)
            self.web_agent = WebResearchAgent()
            self.enabavki_agent = ENabavkiAgent()
            self.epazar_agent = EPazarAgent(self.pool)  # NEW: E-Pazar agent
            self.company_agent = CompanyResearchAgent()
            self.document_agent = DocumentAnalysisAgent()

            logger.info("All agents initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise

    async def close(self):
        """Close database connection and cleanup"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection closed")

        # Close web agent session if needed
        if self.web_agent and hasattr(self.web_agent, 'close'):
            await self.web_agent.close()

    async def get_cached_investigation(
        self,
        entity_id: str,
        entity_type: str,
        max_age_hours: int = 24
    ) -> Optional[CorruptionAssessment]:
        """
        Check if a recent investigation exists in cache.

        Args:
            entity_id: The ID of the entity (tender_id, company_name, etc.)
            entity_type: Type of entity ('tender', 'company', 'institution')
            max_age_hours: Maximum age of cached result in hours (default: 24)

        Returns:
            CorruptionAssessment if found and recent enough, None otherwise
        """
        if not self.pool:
            logger.warning("Cannot check cache - no database connection")
            return None

        try:
            async with self.pool.acquire() as conn:
                # Check if investigation exists and is recent enough
                result = await conn.fetchrow("""
                    SELECT
                        entity_id,
                        entity_type,
                        entity_name,
                        risk_score,
                        risk_level,
                        confidence,
                        findings,
                        recommendations,
                        summary_mk,
                        summary_en,
                        data_quality,
                        investigated_at
                    FROM corruption_investigations
                    WHERE entity_id = $1
                      AND entity_type = $2
                      AND investigated_at > NOW() - INTERVAL '1 hour' * $3
                    ORDER BY investigated_at DESC
                    LIMIT 1
                """, entity_id, entity_type, max_age_hours)

                if not result:
                    logger.info(f"No cached investigation found for {entity_type}:{entity_id} (max age: {max_age_hours}h)")
                    return None

                # Reconstruct CorruptionAssessment from cached data
                findings = []
                if result['findings']:
                    findings_data = json.loads(result['findings']) if isinstance(result['findings'], str) else result['findings']
                    for f in findings_data:
                        findings.append(ResearchFinding(
                            source=f.get('source', 'unknown'),
                            finding_type=f.get('finding_type', 'info'),
                            description=f.get('description', ''),
                            evidence=f.get('evidence', {}),
                            confidence=f.get('confidence', 0.5),
                            severity=f.get('severity', 'low')
                        ))

                recommendations = []
                if result['recommendations']:
                    recs_data = json.loads(result['recommendations']) if isinstance(result['recommendations'], str) else result['recommendations']
                    recommendations = recs_data if isinstance(recs_data, list) else []

                data_quality = {}
                if result['data_quality']:
                    data_quality = json.loads(result['data_quality']) if isinstance(result['data_quality'], str) else result['data_quality']

                assessment = CorruptionAssessment(
                    entity_type=result['entity_type'],
                    entity_id=result['entity_id'],
                    entity_name=result['entity_name'] or entity_id,
                    risk_score=result['risk_score'] or 0,
                    risk_level=result['risk_level'] or 'minimal',
                    findings=findings,
                    evidence_summary={},  # Not stored in cache
                    confidence=result['confidence'] or 0.5,
                    recommendations=recommendations,
                    summary_mk=result['summary_mk'] or '',
                    summary_en=result['summary_en'] or '',
                    data_quality=data_quality,
                    timestamp=result['investigated_at']
                )

                age_hours = (datetime.utcnow() - result['investigated_at']).total_seconds() / 3600
                logger.info(f"Found cached investigation for {entity_type}:{entity_id} (age: {age_hours:.1f}h)")
                return assessment

        except Exception as e:
            logger.error(f"Failed to check investigation cache: {e}")
            return None

    # =========================================================================
    # Main Investigation Methods
    # =========================================================================

    async def investigate_tender(self, tender_id: str, progress_callback=None) -> CorruptionAssessment:
        """
        FULL investigation of a single tender.

        1. Run ALL agents in parallel:
           - DB: tender details, bidders, history
           - E-Nabavki: official data, verify bidder count
           - Company: research winner and all bidders
           - Documents: analyze specifications, contract
           - Web: news, controversies, connections

        2. Cross-reference findings:
           - Does our DB match official source?
           - Are bidders related to each other?
           - Is winner connected to institution?
           - Do documents show tailored specs?

        3. Use LLM to synthesize everything:
           - Generate corruption risk assessment
           - Identify specific red flags with evidence
           - Calculate confidence score
           - Provide recommendations

        Args:
            tender_id: The tender ID to investigate
            progress_callback: Optional async callback(stage: str, status: str) for progress updates
        """
        logger.info(f"{'='*60}")
        logger.info(f"Starting FULL investigation of tender: {tender_id}")
        logger.info(f"{'='*60}")
        start_time = datetime.utcnow()

        # Check cache first
        if progress_callback:
            await progress_callback("cache", "checking")

        cached = await self.get_cached_investigation(tender_id, 'tender', max_age_hours=24)
        if cached:
            logger.info("Using cached investigation result")
            if progress_callback:
                await progress_callback("cache", "hit")
            return cached

        if progress_callback:
            await progress_callback("cache", "miss")

        # Step 1: Run all agents in parallel
        logger.info("Step 1: Running all research agents in parallel...")
        if progress_callback:
            await progress_callback("database", "started")

        # Gather results from all agents
        results = await asyncio.gather(
            self._safe_call(self.db_agent.research_tender, tender_id),
            self._safe_call(self.enabavki_agent.get_tender_details, tender_id),
            self._safe_call(self.enabavki_agent.get_official_bidder_count, tender_id),
            return_exceptions=True
        )

        db_research = results[0] if not isinstance(results[0], Exception) else None
        official_tender = results[1] if not isinstance(results[1], Exception) else None
        official_bidders = results[2] if not isinstance(results[2], Exception) else None

        if progress_callback:
            await progress_callback("database", "completed")

        # Extract key information for further research
        tender_title = ""
        institution_name = ""
        winner_name = ""
        all_bidders = []

        if db_research and hasattr(db_research, 'basic_info'):
            tender_title = db_research.basic_info.get('title', '')
            institution_name = db_research.basic_info.get('procuring_entity', '')
            winner_name = db_research.basic_info.get('winner', '')
            all_bidders = [b.get('company_name', '') for b in db_research.bidders if b.get('company_name')]
        elif official_tender:
            tender_title = official_tender.title or ''
            institution_name = official_tender.procuring_entity or ''

        # Step 2: Web research and company research
        logger.info("Step 2: Running web and company research...")
        if progress_callback:
            await progress_callback("web_research", "started")

        company_results = await asyncio.gather(
            # Web research for tender
            self._safe_call(self.web_agent.research_tender, tender_id, tender_title, institution_name)
            if tender_title else asyncio.sleep(0),
            # Research winner company
            self._safe_call(self.company_agent.research_company, winner_name)
            if winner_name else asyncio.sleep(0),
            # Find connections between bidders
            self._research_bidder_connections(all_bidders[:5]),  # Limit to 5 bidders
            return_exceptions=True
        )

        web_research = company_results[0] if not isinstance(company_results[0], Exception) else None
        winner_research = company_results[1] if not isinstance(company_results[1], Exception) else None
        bidder_connections = company_results[2] if not isinstance(company_results[2], Exception) else []

        if progress_callback:
            await progress_callback("web_research", "completed")

        # Step 3: Verify data consistency between our DB and official sources
        logger.info("Step 3: Verifying data consistency...")
        if progress_callback:
            await progress_callback("verification", "started")

        consistency_report = await self._verify_data_consistency(
            db_research, official_tender, official_bidders
        )

        if progress_callback:
            await progress_callback("verification", "completed")

        # Step 4: Document analysis (if we have specifications)
        logger.info("Step 4: Analyzing documents...")
        if progress_callback:
            await progress_callback("documents", "started")

        document_analysis = None
        if db_research and db_research.documents:
            specs_doc = next(
                (d for d in db_research.documents if 'спецификација' in (d.get('doc_type', '') or '').lower()),
                None
            )
            if specs_doc and specs_doc.get('content'):
                document_analysis = await self._safe_call(
                    self.document_agent.analyze_specifications,
                    tender_id,
                    specs_doc['content']
                )

        if progress_callback:
            await progress_callback("documents", "completed")

        # Step 5: Compile all research
        logger.info("Step 5: Compiling all research data...")
        if progress_callback:
            await progress_callback("synthesis", "started")
        all_research = {
            'tender_id': tender_id,
            'db_research': self._serialize_research(db_research),
            'official_tender': self._serialize_dataclass(official_tender),
            'official_bidders': self._serialize_dataclass(official_bidders),
            'web_research': self._serialize_research(web_research),
            'winner_research': self._serialize_research(winner_research),
            'bidder_connections': bidder_connections,
            'consistency_report': asdict(consistency_report) if isinstance(consistency_report, DataConsistencyReport) else consistency_report,
            'document_analysis': document_analysis,
            'investigation_time_seconds': (datetime.utcnow() - start_time).total_seconds()
        }

        # Step 6: Synthesize findings using LLM
        logger.info("Step 6: Synthesizing findings with LLM...")
        assessment = await self._synthesize_findings(all_research, 'tender')

        # Step 7: Store investigation results
        await self._store_investigation_results(tender_id, 'tender', assessment)

        if progress_callback:
            await progress_callback("synthesis", "completed")

        logger.info(f"{'='*60}")
        logger.info(f"Investigation complete. Risk: {assessment.risk_score}/100 ({assessment.risk_level})")
        logger.info(f"{'='*60}")

        return assessment

    async def investigate_company(self, company_name: str) -> CorruptionAssessment:
        """
        FULL investigation of a company.

        Research across all sources:
        - Tender history (DB)
        - Official records (web)
        - Ownership and connections
        - Related companies
        - News and controversies

        Generate assessment:
        - Overall risk profile
        - Specific concerns
        - Evidence
        """
        logger.info(f"{'='*60}")
        logger.info(f"Starting FULL investigation of company: {company_name}")
        logger.info(f"{'='*60}")
        start_time = datetime.utcnow()

        # Step 1: Run all agents in parallel
        logger.info("Step 1: Running all research agents...")

        results = await asyncio.gather(
            self._safe_call(self.db_agent.research_company, company_name),
            self._safe_call(self.company_agent.research_company, company_name),
            self._safe_call(self.web_agent.research_company, company_name),
            return_exceptions=True
        )

        db_research = results[0] if not isinstance(results[0], Exception) else None
        ownership_research = results[1] if not isinstance(results[1], Exception) else None
        web_research = results[2] if not isinstance(results[2], Exception) else None

        # Step 2: Research related companies
        logger.info("Step 2: Researching related companies...")
        related_research = []
        if ownership_research and hasattr(ownership_research, 'related_companies'):
            for related in ownership_research.related_companies[:3]:
                if hasattr(related, 'company_name') and related.company_name:
                    related_db = await self._safe_call(self.db_agent.research_company, related.company_name)
                    related_research.append({
                        'company': related.company_name,
                        'relationship': related.relation_type if hasattr(related, 'relation_type') else 'unknown',
                        'tender_data': self._serialize_research(related_db)
                    })

        # Step 3: Look for shell company indicators
        logger.info("Step 3: Checking for shell company indicators...")
        shell_indicators = []
        if ownership_research:
            shell_indicators = await self._safe_call(
                self.company_agent.detect_shell_company_indicators,
                company_name
            )

        # Compile all research
        all_research = {
            'company_name': company_name,
            'db_research': self._serialize_research(db_research),
            'ownership_research': self._serialize_research(ownership_research),
            'web_research': self._serialize_research(web_research),
            'related_companies': related_research,
            'shell_indicators': shell_indicators if not isinstance(shell_indicators, Exception) else [],
            'investigation_time_seconds': (datetime.utcnow() - start_time).total_seconds()
        }

        # Synthesize findings
        assessment = await self._synthesize_findings(all_research, 'company')

        # Store results
        await self._store_investigation_results(company_name, 'company', assessment)

        logger.info(f"Company investigation complete. Risk: {assessment.risk_score}/100")
        return assessment

    async def investigate_institution(self, institution_name: str) -> CorruptionAssessment:
        """
        FULL investigation of a procuring institution.

        Research:
        - All their tenders
        - Winner patterns
        - Problematic tenders
        - News coverage
        - Leadership connections

        Generate assessment of institutional corruption risk.
        """
        logger.info(f"{'='*60}")
        logger.info(f"Starting FULL investigation of institution: {institution_name}")
        logger.info(f"{'='*60}")
        start_time = datetime.utcnow()

        # Step 1: Run all agents in parallel
        logger.info("Step 1: Running all research agents...")

        results = await asyncio.gather(
            self._safe_call(self.db_agent.research_institution, institution_name),
            self._safe_call(self.web_agent.research_institution, institution_name),
            self._safe_call(self.enabavki_agent.search_institution_tenders, institution_name, 50),
            return_exceptions=True
        )

        db_research = results[0] if not isinstance(results[0], Exception) else None
        web_research = results[1] if not isinstance(results[1], Exception) else None
        official_tenders = results[2] if not isinstance(results[2], Exception) else None

        # Step 2: Research top winners at this institution
        logger.info("Step 2: Researching top winners...")
        winner_research = []
        if db_research and hasattr(db_research, 'winner_distribution'):
            for winner_info in db_research.winner_distribution[:5]:
                if isinstance(winner_info, dict) and winner_info.get('winner'):
                    ownership = await self._safe_call(
                        self.company_agent.research_company,
                        winner_info['winner']
                    )
                    winner_research.append({
                        'company': winner_info['winner'],
                        'wins': winner_info.get('wins'),
                        'percentage': winner_info.get('percentage'),
                        'ownership': self._serialize_research(ownership)
                    })

        # Compile all research
        all_research = {
            'institution_name': institution_name,
            'db_research': self._serialize_research(db_research),
            'web_research': self._serialize_research(web_research),
            'official_tenders': official_tenders,
            'winner_research': winner_research,
            'investigation_time_seconds': (datetime.utcnow() - start_time).total_seconds()
        }

        # Synthesize findings
        assessment = await self._synthesize_findings(all_research, 'institution')

        # Store results
        await self._store_investigation_results(institution_name, 'institution', assessment)

        logger.info(f"Institution investigation complete. Risk: {assessment.risk_score}/100")
        return assessment

    async def quick_analyze_tender(self, tender_id: str) -> CorruptionAssessment:
        """
        Quick analysis using ONLY database + rules (no LLM, no web research).

        This is faster and works even when GEMINI_API_KEY is not available.
        Use this for:
        - Bulk screening
        - When LLM is unavailable
        - Quick risk checks

        Returns:
            CorruptionAssessment with rule-based findings
        """
        logger.info(f"Starting QUICK analysis of tender: {tender_id}")
        start_time = datetime.utcnow()

        # Check cache first
        cached = await self.get_cached_investigation(tender_id, 'tender', max_age_hours=24)
        if cached:
            logger.info("Using cached investigation result")
            return cached

        # Step 1: Get basic data from DB and official sources
        results = await asyncio.gather(
            self._safe_call(self.db_agent.research_tender, tender_id),
            self._safe_call(self.enabavki_agent.get_tender_details, tender_id),
            self._safe_call(self.enabavki_agent.get_official_bidder_count, tender_id),
            return_exceptions=True
        )

        db_research = results[0] if not isinstance(results[0], Exception) else None
        official_tender = results[1] if not isinstance(results[1], Exception) else None
        official_bidders = results[2] if not isinstance(results[2], Exception) else None

        # Step 2: Verify data consistency
        consistency_report = await self._verify_data_consistency(
            db_research, official_tender, official_bidders
        )

        # Step 3: Apply rule-based analysis
        all_research = {
            'tender_id': tender_id,
            'db_research': self._serialize_research(db_research),
            'official_tender': self._serialize_dataclass(official_tender),
            'official_bidders': self._serialize_dataclass(official_bidders),
            'consistency_report': asdict(consistency_report) if isinstance(consistency_report, DataConsistencyReport) else consistency_report,
            'investigation_time_seconds': (datetime.utcnow() - start_time).total_seconds(),
            'analysis_type': 'quick_rule_based'
        }

        # Use rule-based synthesis (no LLM)
        assessment = await self._rule_based_synthesis(all_research, 'tender')

        # Store results
        await self._store_investigation_results(tender_id, 'tender', assessment)

        logger.info(f"Quick analysis complete. Risk: {assessment.risk_score}/100 ({assessment.risk_level})")
        return assessment

    async def find_corruption_patterns(self, limit: int = 100) -> Dict[str, Any]:
        """
        Proactive corruption hunting.

        1. Get list of recent/high-value tenders
        2. Run quick screening on each
        3. Deep dive on suspicious ones
        4. Generate report of findings
        """
        logger.info(f"{'='*60}")
        logger.info(f"Starting proactive corruption pattern search (limit: {limit})")
        logger.info(f"{'='*60}")

        if not self.pool:
            return {'error': 'Database not initialized'}

        results = {
            'scan_time': datetime.utcnow().isoformat(),
            'tenders_scanned': 0,
            'suspicious_tenders': [],
            'pattern_summary': {},
            'recommendations': [],
            'top_risk_tenders': []
        }

        try:
            async with self.pool.acquire() as conn:
                # Get high-value and recent tenders with existing risk scores
                tenders = await conn.fetch("""
                    SELECT
                        t.tender_id,
                        t.title,
                        t.procuring_entity,
                        t.estimated_value_mkd,
                        t.actual_value_mkd,
                        t.winner,
                        t.num_bidders,
                        t.publication_date,
                        COALESCE(trs.risk_score, 0) as risk_score,
                        trs.risk_level,
                        trs.flags_summary
                    FROM tenders t
                    LEFT JOIN tender_risk_scores trs ON t.tender_id = trs.tender_id
                    WHERE t.status = 'awarded'
                      AND t.estimated_value_mkd > 1000000
                    ORDER BY
                        COALESCE(trs.risk_score, 0) DESC,
                        t.estimated_value_mkd DESC
                    LIMIT $1
                """, limit)

                results['tenders_scanned'] = len(tenders)

                # Quick screening
                suspicious = []
                for tender in tenders:
                    quick_flags = []

                    # Single bidder check
                    if tender['num_bidders'] == 1:
                        quick_flags.append('single_bidder')

                    # High existing risk score
                    if tender['risk_score'] >= 60:
                        quick_flags.append('high_risk_score')

                    # Large contract
                    if tender['estimated_value_mkd'] and tender['estimated_value_mkd'] > 10000000:
                        quick_flags.append('high_value')

                    # No winner recorded (anomaly)
                    if not tender['winner'] and tender['risk_score'] == 0:
                        quick_flags.append('no_winner_recorded')

                    if quick_flags:
                        suspicious.append({
                            'tender_id': tender['tender_id'],
                            'title': tender['title'][:100] if tender['title'] else '',
                            'institution': tender['procuring_entity'],
                            'value_mkd': float(tender['estimated_value_mkd'] or 0),
                            'winner': tender['winner'],
                            'num_bidders': tender['num_bidders'],
                            'risk_score': tender['risk_score'],
                            'risk_level': tender['risk_level'],
                            'quick_flags': quick_flags
                        })

                results['suspicious_tenders'] = suspicious

                # Pattern summary
                results['pattern_summary'] = {
                    'single_bidder_count': sum(1 for t in suspicious if 'single_bidder' in t['quick_flags']),
                    'high_risk_count': sum(1 for t in suspicious if 'high_risk_score' in t['quick_flags']),
                    'high_value_count': sum(1 for t in suspicious if 'high_value' in t['quick_flags']),
                    'total_suspicious': len(suspicious),
                    'total_scanned': results['tenders_scanned']
                }

                # Deep dive on top 5 suspicious tenders
                logger.info("Running deep analysis on top suspicious tenders...")
                top_suspicious = sorted(
                    suspicious,
                    key=lambda x: (len(x['quick_flags']), x['value_mkd']),
                    reverse=True
                )[:5]

                for tender in top_suspicious:
                    try:
                        assessment = await self.investigate_tender(tender['tender_id'])
                        results['top_risk_tenders'].append({
                            'tender_id': tender['tender_id'],
                            'title': tender['title'],
                            'risk_score': assessment.risk_score,
                            'risk_level': assessment.risk_level,
                            'summary_mk': assessment.summary_mk,
                            'findings_count': len(assessment.findings)
                        })
                    except Exception as e:
                        logger.error(f"Deep analysis failed for {tender['tender_id']}: {e}")

                # Generate recommendations
                summary = results['pattern_summary']
                if summary['single_bidder_count'] > limit * 0.3:
                    results['recommendations'].append(
                        "HIGH PRIORITY: Over 30% of high-value tenders have single bidders - investigate procurement practices"
                    )
                if summary['high_risk_count'] > 10:
                    results['recommendations'].append(
                        f"URGENT: {summary['high_risk_count']} tenders with risk score >= 60 require immediate review"
                    )
                if summary['total_suspicious'] > limit * 0.5:
                    results['recommendations'].append(
                        "SYSTEMIC ISSUE: Over 50% of scanned tenders show suspicious patterns"
                    )

        except Exception as e:
            logger.error(f"Error in pattern search: {e}")
            results['error'] = str(e)

        return results

    # =========================================================================
    # Synthesis and Analysis Methods
    # =========================================================================

    async def _synthesize_findings(self, all_research: Dict[str, Any], entity_type: str) -> CorruptionAssessment:
        """
        Use Gemini LLM to intelligently synthesize all research.

        If GEMINI_API_KEY is not available, falls back to rule-based synthesis.

        The LLM should:
        - Cross-reference data from all sources
        - Identify patterns humans might miss
        - Weight evidence by source reliability
        - Generate natural language assessment
        - Provide specific, actionable findings

        Prompt should instruct LLM to think like an investigator:
        - What's suspicious?
        - What's the evidence?
        - What's missing?
        - What would I investigate next?
        """
        # Fall back to rule-based if LLM not available
        if not self.synthesis_model or not GEMINI_API_KEY:
            logger.warning("LLM not available - falling back to rule-based synthesis")
            return await self._rule_based_synthesis(all_research, entity_type)

        logger.info(f"Synthesizing {entity_type} findings with LLM...")

        # Prepare research summary for LLM (truncate if too long)
        research_summary = json.dumps(all_research, indent=2, default=str, ensure_ascii=False)
        if len(research_summary) > 30000:
            research_summary = research_summary[:30000] + "\n... [TRUNCATED]"

        synthesis_prompt = f"""You are an expert corruption investigator analyzing public procurement data in North Macedonia (Macedonia).

ENTITY TYPE: {entity_type.upper()}
RESEARCH DATA:
{research_summary}

Analyze this research data and provide a corruption risk assessment. Think like an experienced investigator:

1. CROSS-REFERENCE all sources - look for inconsistencies between our database and official e-nabavki data
2. IDENTIFY specific red flags with supporting evidence
3. NOTE what's suspicious and why - be specific
4. CONSIDER what information is missing
5. WEIGHT evidence by source reliability:
   - Official e-nabavki data = HIGHEST reliability
   - Our database = HIGH reliability
   - Company registry = HIGH reliability
   - Web news = MEDIUM reliability
   - Single source claims = LOW reliability

CRITICAL PRINCIPLES:
- NEVER flag based on single source alone - require corroboration from 2+ sources
- Official e-nabavki data TRUMPS our database when they conflict
- Single bidder alone is NOT proof of corruption - look for PATTERNS
- High win rate at ONE institution could indicate expertise OR corruption - investigate further
- Be conservative - high confidence requires strong multi-source evidence
- Include uncertainty in your assessment

SEVERITY GUIDELINES:
- CRITICAL: Multiple corroborated red flags, clear patterns of manipulation
- HIGH: Strong indicators from 2+ sources, suspicious patterns
- MEDIUM: Concerning patterns that need further investigation
- LOW: Minor anomalies, could be innocent explanations
- MINIMAL: Normal patterns, no significant concerns

Return your analysis in this EXACT JSON format:
{{
    "risk_score": 0-100,
    "risk_level": "minimal/low/medium/high/critical",
    "confidence": 0.0-1.0,
    "findings": [
        {{
            "type": "red_flag/info/connection/anomaly/discrepancy",
            "description": "Specific finding in Macedonian language",
            "evidence": ["evidence item 1", "evidence item 2"],
            "source": "db/web/enabavki/company/document",
            "severity": "low/medium/high/critical",
            "corroborated": true/false,
            "corroborating_sources": ["source1", "source2"]
        }}
    ],
    "data_quality": {{
        "db_data_complete": true/false,
        "official_data_available": true/false,
        "web_data_found": true/false,
        "missing_info": ["specific missing information items"]
    }},
    "recommendations": ["specific actionable recommendations"],
    "summary_mk": "Детално резиме на македонски јазик - 2-3 реченици со клучни наоди",
    "summary_en": "Detailed summary in English - 2-3 sentences with key findings"
}}

Focus on ACTIONABLE findings. Be thorough but factual. Only report findings you can support with evidence."""

        try:
            response = self.synthesis_model.generate_content(
                synthesis_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    response_mime_type="application/json"
                ),
                safety_settings=SAFETY_SETTINGS
            )

            synthesis = json.loads(response.text)

            # Build findings list
            findings = []
            for f in synthesis.get('findings', []):
                findings.append(ResearchFinding(
                    source=f.get('source', 'unknown'),
                    finding_type=f.get('type', 'info'),
                    description=f.get('description', ''),
                    evidence={
                        'items': f.get('evidence', []),
                        'corroborated': f.get('corroborated', False),
                        'corroborating_sources': f.get('corroborating_sources', [])
                    },
                    confidence=synthesis.get('confidence', 0.5),
                    severity=f.get('severity', 'low')
                ))

            # Determine entity ID and name
            entity_id = (
                all_research.get('tender_id') or
                all_research.get('company_name') or
                all_research.get('institution_name', 'unknown')
            )

            entity_name = entity_id
            if entity_type == 'tender':
                db_data = all_research.get('db_research', {})
                if isinstance(db_data, dict):
                    entity_name = db_data.get('basic_info', {}).get('title', entity_id)

            return CorruptionAssessment(
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=str(entity_name)[:200] if entity_name else 'Unknown',
                risk_score=synthesis.get('risk_score', 0),
                risk_level=synthesis.get('risk_level', 'minimal'),
                findings=findings,
                evidence_summary=all_research,
                confidence=synthesis.get('confidence', 0.5),
                recommendations=synthesis.get('recommendations', []),
                summary_mk=synthesis.get('summary_mk', 'Нема резиме'),
                summary_en=synthesis.get('summary_en', 'No summary available'),
                data_quality=synthesis.get('data_quality', {})
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.warning("Falling back to rule-based synthesis due to LLM error")
            return await self._rule_based_synthesis(all_research, entity_type)
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            logger.warning("Falling back to rule-based synthesis due to error")
            return await self._rule_based_synthesis(all_research, entity_type)

    async def _verify_data_consistency(
        self,
        db_research: Any,
        official_tender: Any,
        official_bidders: Any
    ) -> DataConsistencyReport:
        """
        Compare our DB with official sources.
        Flag any discrepancies - our DB may be incomplete.
        """
        discrepancies = []
        is_consistent = True
        our_data = {}
        official_data = {}

        # Extract our data
        if db_research and hasattr(db_research, 'basic_info'):
            our_data = {
                'title': db_research.basic_info.get('title'),
                'num_bidders': len(db_research.bidders) if db_research.bidders else 0,
                'winner': db_research.basic_info.get('winner'),
                'value': db_research.basic_info.get('actual_value_mkd'),
            }

        # Extract official data
        if official_tender:
            official_data['title'] = official_tender.title if hasattr(official_tender, 'title') else None
            official_data['value'] = official_tender.estimated_value_mkd if hasattr(official_tender, 'estimated_value_mkd') else None

        if official_bidders:
            official_data['num_bidders'] = official_bidders.total_bidders if hasattr(official_bidders, 'total_bidders') else None
            official_data['winner'] = official_bidders.winner_name if hasattr(official_bidders, 'winner_name') else None

        # Compare bidder counts (CRITICAL check)
        our_bidders = our_data.get('num_bidders', 0)
        official_bidder_count = official_data.get('num_bidders')

        if official_bidder_count is not None and our_bidders != official_bidder_count:
            discrepancies.append({
                'field': 'Bidder Count',
                'our_value': our_bidders,
                'official_value': official_bidder_count,
                'severity': 'high' if abs(our_bidders - official_bidder_count) > 1 else 'medium',
                'issue': f'Our DB has {our_bidders} bidders, official shows {official_bidder_count}'
            })
            is_consistent = False

        # Compare winner
        our_winner = our_data.get('winner', '')
        official_winner = official_data.get('winner', '')

        if official_winner and our_winner and our_winner.lower() != official_winner.lower():
            # Check if it's just a name variation
            if our_winner.lower() not in official_winner.lower() and official_winner.lower() not in our_winner.lower():
                discrepancies.append({
                    'field': 'Winner',
                    'our_value': our_winner,
                    'official_value': official_winner,
                    'severity': 'high',
                    'issue': f'Winner mismatch: our DB has "{our_winner}", official shows "{official_winner}"'
                })
                is_consistent = False

        recommendations = []
        if not is_consistent:
            recommendations.append('Update our database with official e-nabavki data')
            recommendations.append('Trust official source over our database in case of conflict')
            if any(d['field'] == 'Bidder Count' for d in discrepancies):
                recommendations.append('CRITICAL: Missing bidders in our database - may affect analysis accuracy')

        if not official_data:
            recommendations.append('Could not verify against official source - manual verification recommended')

        return DataConsistencyReport(
            is_consistent=is_consistent,
            discrepancies=discrepancies,
            our_data=our_data,
            official_data=official_data,
            recommendations=recommendations
        )

    async def _rule_based_synthesis(self, all_research: Dict[str, Any], entity_type: str) -> CorruptionAssessment:
        """
        Rule-based corruption assessment (no LLM required).

        This method applies a set of predefined rules to detect corruption risks.
        Used when LLM is unavailable or for quick screening.

        Rules applied:
        - Single bidder tenders (high risk if value > threshold)
        - Data inconsistencies between DB and official sources
        - Unusually high win rates
        - Missing critical information
        """
        logger.info(f"Applying rule-based synthesis for {entity_type}")

        findings = []
        risk_score = 0
        recommendations = []

        # Extract research data
        db_data = all_research.get('db_research', {})
        consistency_report = all_research.get('consistency_report', {})
        entity_id = (
            all_research.get('tender_id') or
            all_research.get('company_name') or
            all_research.get('institution_name', 'unknown')
        )

        # Rule 1: Check for data inconsistencies (HIGH PRIORITY)
        if consistency_report and not consistency_report.get('is_consistent', True):
            discrepancies = consistency_report.get('discrepancies', [])
            for disc in discrepancies:
                severity = disc.get('severity', 'low')
                findings.append(ResearchFinding(
                    source='verification',
                    finding_type='discrepancy',
                    description=f"Несовпаѓање на податоци: {disc.get('issue', 'Непозната грешка')}",
                    evidence={'discrepancy': disc},
                    confidence=0.9,
                    severity=severity
                ))
                if severity == 'high':
                    risk_score += 20
                elif severity == 'medium':
                    risk_score += 10
                else:
                    risk_score += 5

            recommendations.append("Ажурирање на базата со официјални податоци")

        # Rule 2: Single bidder check (for tenders)
        if entity_type == 'tender':
            basic_info = db_data.get('basic_info', {})
            num_bidders = basic_info.get('num_bidders', 0)
            estimated_value = basic_info.get('estimated_value_mkd', 0)

            if num_bidders == 1:
                severity = 'high' if estimated_value > 5000000 else 'medium'
                findings.append(ResearchFinding(
                    source='db',
                    finding_type='red_flag',
                    description=f"Само еден понудувач (вредност: {estimated_value:,.0f} МКД)",
                    evidence={'num_bidders': num_bidders, 'value': estimated_value},
                    confidence=0.8,
                    severity=severity
                ))
                risk_score += 30 if severity == 'high' else 20
                recommendations.append("Проверка дали техничката спецификација е прилагодена")

            # Rule 3: No bidders recorded (data quality issue)
            elif num_bidders == 0:
                findings.append(ResearchFinding(
                    source='db',
                    finding_type='info',
                    description="Нема податоци за понудувачи во базата",
                    evidence={'num_bidders': 0},
                    confidence=0.3,
                    severity='low'
                ))
                recommendations.append("Дополнување на податоците за понудувачи")

        # Rule 4: Check for missing critical information
        if entity_type == 'tender':
            basic_info = db_data.get('basic_info', {})
            missing = []

            if not basic_info.get('winner'):
                missing.append('winner')
            if not basic_info.get('actual_value_mkd'):
                missing.append('contract_value')
            if not basic_info.get('procuring_entity'):
                missing.append('procuring_entity')

            if missing:
                findings.append(ResearchFinding(
                    source='db',
                    finding_type='info',
                    description=f"Недостасуваат критични информации: {', '.join(missing)}",
                    evidence={'missing_fields': missing},
                    confidence=0.5,
                    severity='low'
                ))
                risk_score += len(missing) * 2

        # Rule 5: Price comparison (if both estimated and actual values available)
        if entity_type == 'tender':
            basic_info = db_data.get('basic_info', {})
            estimated = basic_info.get('estimated_value_mkd', 0)
            actual = basic_info.get('actual_value_mkd', 0)

            if estimated and actual and estimated > 0:
                price_ratio = actual / estimated
                if price_ratio > 1.2:
                    findings.append(ResearchFinding(
                        source='db',
                        finding_type='red_flag',
                        description=f"Договорена цена е {price_ratio:.1%} од проценетата ({actual:,.0f} МКД наспроти {estimated:,.0f} МКД)",
                        evidence={'estimated': estimated, 'actual': actual, 'ratio': price_ratio},
                        confidence=0.7,
                        severity='medium'
                    ))
                    risk_score += 15
                    recommendations.append("Проверка на причините за зголемена цена")

        # Rule 6: Check for high win rates (for companies)
        if entity_type == 'company':
            win_stats = db_data.get('win_statistics', {})
            total_bids = win_stats.get('total_participations', 0)
            total_wins = win_stats.get('total_wins', 0)

            if total_bids >= 5:  # Only check if sufficient data
                win_rate = total_wins / total_bids if total_bids > 0 else 0
                if win_rate > 0.7:  # 70% win rate is suspicious
                    findings.append(ResearchFinding(
                        source='db',
                        finding_type='red_flag',
                        description=f"Висока стапка на добиени тендери: {win_rate:.1%} ({total_wins} од {total_bids})",
                        evidence={'win_rate': win_rate, 'wins': total_wins, 'participations': total_bids},
                        confidence=0.7,
                        severity='high'
                    ))
                    risk_score += 25
                    recommendations.append("Детална анализа на добиените тендери")

        # Cap risk score at 100
        risk_score = min(risk_score, 100)

        # Determine risk level
        if risk_score >= 75:
            risk_level = 'critical'
        elif risk_score >= 60:
            risk_level = 'high'
        elif risk_score >= 40:
            risk_level = 'medium'
        elif risk_score >= 20:
            risk_level = 'low'
        else:
            risk_level = 'minimal'

        # Calculate confidence (lower for rule-based analysis)
        confidence = 0.6 if findings else 0.3

        # Generate summaries
        if findings:
            summary_mk = f"Правилна анализа открива {len(findings)} наод(и). Ризик: {risk_level}. "
            if any(f.severity in ['high', 'critical'] for f in findings):
                summary_mk += "Пронајдени се значајни индикатори за ризик."
            else:
                summary_mk += "Пронајдени се помали индикатори за ризик."

            summary_en = f"Rule-based analysis found {len(findings)} finding(s). Risk: {risk_level}. "
            if any(f.severity in ['high', 'critical'] for f in findings):
                summary_en += "Significant risk indicators found."
            else:
                summary_en += "Minor risk indicators found."
        else:
            summary_mk = "Правилната анализа не откри значајни ризици. Препорачано е LLM анализа за подлабока проверка."
            summary_en = "Rule-based analysis found no significant risks. LLM analysis recommended for deeper investigation."

        # Get entity name
        entity_name = entity_id
        if entity_type == 'tender':
            entity_name = db_data.get('basic_info', {}).get('title', entity_id)

        return CorruptionAssessment(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=str(entity_name)[:200] if entity_name else 'Unknown',
            risk_score=risk_score,
            risk_level=risk_level,
            findings=findings,
            evidence_summary=all_research,
            confidence=confidence,
            recommendations=recommendations or ["LLM анализа препорачана за подлабока проверка"],
            summary_mk=summary_mk,
            summary_en=summary_en,
            data_quality={
                'analysis_method': 'rule_based',
                'llm_available': False,
                'findings_count': len(findings)
            }
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _safe_call(self, func, *args, **kwargs) -> Any:
        """Safely call an async function, returning None on error"""
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Safe call failed for {func.__name__ if hasattr(func, '__name__') else func}: {e}")
            return None

    async def _research_bidder_connections(self, bidders: List[str]) -> List[Dict[str, Any]]:
        """Research connections between bidders"""
        connections = []

        if len(bidders) < 2 or not self.company_agent:
            return connections

        # Check connections between each pair
        for i, bidder1 in enumerate(bidders):
            for bidder2 in bidders[i+1:]:
                if not bidder1 or not bidder2:
                    continue

                try:
                    connection = await self._safe_call(
                        self.company_agent.find_connections,
                        bidder1, bidder2
                    )
                    if connection and isinstance(connection, dict) and connection.get('connections_found'):
                        connections.append({
                            'company_a': bidder1,
                            'company_b': bidder2,
                            'connection_types': connection.get('connection_types', []),
                            'confidence': connection.get('confidence', 0)
                        })
                except Exception as e:
                    logger.debug(f"Connection check failed: {e}")

        return connections

    def _serialize_research(self, research: Any) -> Dict[str, Any]:
        """Serialize research object to dict"""
        if research is None:
            return {}
        if isinstance(research, dict):
            return research
        if hasattr(research, 'to_dict'):
            return research.to_dict()
        if hasattr(research, 'to_json'):
            return json.loads(research.to_json())
        if hasattr(research, '__dict__'):
            return {k: self._serialize_value(v) for k, v in research.__dict__.items()}
        return {'value': str(research)}

    def _serialize_dataclass(self, obj: Any) -> Dict[str, Any]:
        """Serialize a dataclass to dict"""
        if obj is None:
            return {}
        if hasattr(obj, '__dataclass_fields__'):
            return asdict(obj)
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        if isinstance(obj, dict):
            return obj
        return {'value': str(obj)}

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a single value"""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, (datetime, Decimal)):
            return str(value)
        if isinstance(value, list):
            return [self._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        if hasattr(value, 'to_dict'):
            return value.to_dict()
        if hasattr(value, '__dict__'):
            return {k: self._serialize_value(v) for k, v in value.__dict__.items()}
        return str(value)

    def _create_error_assessment(self, entity_type: str, research: Dict, error: str) -> CorruptionAssessment:
        """Create an assessment when synthesis fails"""
        entity_id = (
            research.get('tender_id') or
            research.get('company_name') or
            research.get('institution_name', 'unknown')
        )

        return CorruptionAssessment(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_id,
            risk_score=0,
            risk_level='minimal',
            findings=[ResearchFinding(
                source='system',
                finding_type='info',
                description=f'Assessment could not be completed: {error}',
                evidence={},
                confidence=0.0,
                severity='low'
            )],
            evidence_summary=research,
            confidence=0.0,
            recommendations=['Manual review recommended due to analysis error'],
            summary_mk='Автоматската анализа не успеа. Потребна е рачна проверка.',
            summary_en='Automated analysis failed. Manual review required.',
            data_quality={'error': error}
        )

    async def _store_investigation_results(
        self,
        entity_id: str,
        entity_type: str,
        assessment: CorruptionAssessment
    ):
        """Store investigation results in database"""
        if not self.pool:
            logger.warning("Cannot store results - no database connection")
            return

        try:
            async with self.pool.acquire() as conn:
                # Check if table exists, create if not
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS corruption_investigations (
                        id SERIAL PRIMARY KEY,
                        entity_id VARCHAR(255) NOT NULL,
                        entity_type VARCHAR(50) NOT NULL,
                        entity_name TEXT,
                        risk_score INTEGER,
                        risk_level VARCHAR(20),
                        confidence FLOAT,
                        findings JSONB,
                        recommendations JSONB,
                        summary_mk TEXT,
                        summary_en TEXT,
                        data_quality JSONB,
                        investigated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(entity_id, entity_type)
                    )
                """)

                # Create index for faster lookups
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_corruption_investigations_entity
                    ON corruption_investigations(entity_id, entity_type)
                """)

                # Upsert investigation results
                findings_json = json.dumps(
                    [f.to_dict() for f in assessment.findings],
                    default=str,
                    ensure_ascii=False
                )

                await conn.execute("""
                    INSERT INTO corruption_investigations
                    (entity_id, entity_type, entity_name, risk_score, risk_level, confidence,
                     findings, recommendations, summary_mk, summary_en, data_quality)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (entity_id, entity_type) DO UPDATE SET
                        entity_name = EXCLUDED.entity_name,
                        risk_score = EXCLUDED.risk_score,
                        risk_level = EXCLUDED.risk_level,
                        confidence = EXCLUDED.confidence,
                        findings = EXCLUDED.findings,
                        recommendations = EXCLUDED.recommendations,
                        summary_mk = EXCLUDED.summary_mk,
                        summary_en = EXCLUDED.summary_en,
                        data_quality = EXCLUDED.data_quality,
                        investigated_at = CURRENT_TIMESTAMP
                """,
                    entity_id,
                    entity_type,
                    assessment.entity_name,
                    assessment.risk_score,
                    assessment.risk_level,
                    assessment.confidence,
                    findings_json,
                    json.dumps(assessment.recommendations),
                    assessment.summary_mk,
                    assessment.summary_en,
                    json.dumps(assessment.data_quality, default=str)
                )

                logger.info(f"Stored investigation results for {entity_type}: {entity_id}")

        except Exception as e:
            logger.error(f"Failed to store investigation results: {e}")
# =============================================================================
# CLI Interface
# =============================================================================

async def main():
    """CLI interface for corruption research"""
    import sys

    orchestrator = CorruptionResearchOrchestrator()

    try:
        await orchestrator.initialize()

        if len(sys.argv) < 2:
            print("""
Corruption Research Orchestrator - CLI Interface
================================================

Usage:
  python corruption_research_orchestrator.py tender <tender_id>       - Investigate a tender
  python corruption_research_orchestrator.py company <company_name>   - Investigate a company
  python corruption_research_orchestrator.py institution <name>       - Investigate an institution
  python corruption_research_orchestrator.py scan [limit]             - Scan for corruption patterns

Examples:
  python corruption_research_orchestrator.py tender "123456/2024"
  python corruption_research_orchestrator.py company "ДКММ ДООЕЛ"
  python corruption_research_orchestrator.py institution "Министерство за здравство"
  python corruption_research_orchestrator.py scan 50
            """)
            return

        command = sys.argv[1].lower()

        if command == 'tender' and len(sys.argv) > 2:
            tender_id = sys.argv[2]
            assessment = await orchestrator.investigate_tender(tender_id)
            _print_assessment(assessment)

        elif command == 'company' and len(sys.argv) > 2:
            company_name = ' '.join(sys.argv[2:])
            assessment = await orchestrator.investigate_company(company_name)
            _print_assessment(assessment)

        elif command == 'institution' and len(sys.argv) > 2:
            institution_name = ' '.join(sys.argv[2:])
            assessment = await orchestrator.investigate_institution(institution_name)
            _print_assessment(assessment)

        elif command == 'scan':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            results = await orchestrator.find_corruption_patterns(limit)
            _print_scan_results(results)

        else:
            print(f"Unknown command: {command}")
            print("Run without arguments for usage help.")

    finally:
        await orchestrator.close()
def _print_assessment(assessment: CorruptionAssessment):
    """Pretty print an assessment"""
    risk_colors = {
        'critical': '\033[91m',  # Red
        'high': '\033[93m',      # Yellow
        'medium': '\033[33m',    # Orange-ish
        'low': '\033[94m',       # Blue
        'minimal': '\033[92m'    # Green
    }
    reset = '\033[0m'
    color = risk_colors.get(assessment.risk_level, '')

    print(f"\n{'='*70}")
    print(f"CORRUPTION RISK ASSESSMENT")
    print(f"{'='*70}")
    print(f"Entity: {assessment.entity_name}")
    print(f"Type: {assessment.entity_type.upper()}")
    print(f"ID: {assessment.entity_id}")
    print(f"\n{color}RISK SCORE: {assessment.risk_score}/100 ({assessment.risk_level.upper()}){reset}")
    print(f"Confidence: {assessment.confidence:.0%}")

    print(f"\n{'-'*70}")
    print("FINDINGS:")
    print(f"{'-'*70}")

    if not assessment.findings:
        print("  No significant findings.")
    else:
        for i, finding in enumerate(assessment.findings, 1):
            severity_markers = {'critical': '!!!', 'high': '!!', 'medium': '!', 'low': '-'}
            marker = severity_markers.get(finding.severity, '-')
            print(f"\n{i}. [{marker}] [{finding.severity.upper()}] {finding.description}")
            print(f"   Source: {finding.source} | Type: {finding.finding_type}")
            if finding.evidence.get('items'):
                print(f"   Evidence: {', '.join(str(e)[:60] for e in finding.evidence['items'][:3])}")
            if finding.evidence.get('corroborated'):
                print(f"   Corroborated: Yes ({', '.join(finding.evidence.get('corroborating_sources', []))})")

    if assessment.recommendations:
        print(f"\n{'-'*70}")
        print("RECOMMENDATIONS:")
        print(f"{'-'*70}")
        for rec in assessment.recommendations:
            print(f"  * {rec}")

    print(f"\n{'-'*70}")
    print("SUMMARY (Macedonian):")
    print(f"{'-'*70}")
    print(f"  {assessment.summary_mk}")

    print(f"\n{'-'*70}")
    print("SUMMARY (English):")
    print(f"{'-'*70}")
    print(f"  {assessment.summary_en}")

    # Data quality
    if assessment.data_quality:
        print(f"\n{'-'*70}")
        print("DATA QUALITY:")
        print(f"{'-'*70}")
        for key, value in assessment.data_quality.items():
            print(f"  {key}: {value}")

    print(f"\n{'='*70}\n")
def _print_scan_results(results: Dict):
    """Pretty print scan results"""
    print(f"\n{'='*70}")
    print("CORRUPTION PATTERN SCAN RESULTS")
    print(f"{'='*70}")
    print(f"Scan time: {results.get('scan_time', 'N/A')}")
    print(f"Tenders scanned: {results.get('tenders_scanned', 0)}")

    summary = results.get('pattern_summary', {})
    print(f"\n{'-'*70}")
    print("PATTERN SUMMARY:")
    print(f"{'-'*70}")
    print(f"  Total suspicious: {summary.get('total_suspicious', 0)}")
    print(f"  Single bidder: {summary.get('single_bidder_count', 0)}")
    print(f"  High risk score: {summary.get('high_risk_count', 0)}")
    print(f"  High value: {summary.get('high_value_count', 0)}")

    if results.get('suspicious_tenders'):
        print(f"\n{'-'*70}")
        print("TOP SUSPICIOUS TENDERS:")
        print(f"{'-'*70}")

        for tender in results['suspicious_tenders'][:15]:
            flags = ', '.join(tender.get('quick_flags', []))
            print(f"\n  [{tender['risk_score']:3d}] {tender['tender_id']}")
            print(f"       {tender['title'][:55]}...")
            print(f"       Value: {tender['value_mkd']:,.0f} MKD | Bidders: {tender['num_bidders'] or '?'}")
            print(f"       Flags: {flags}")

    if results.get('top_risk_tenders'):
        print(f"\n{'-'*70}")
        print("DEEP ANALYSIS - TOP RISK TENDERS:")
        print(f"{'-'*70}")

        for tender in results['top_risk_tenders']:
            print(f"\n  [{tender['risk_score']:3d}] {tender['tender_id']} - {tender['risk_level'].upper()}")
            print(f"       {tender['summary_mk'][:100]}...")
            print(f"       Findings: {tender['findings_count']}")

    if results.get('recommendations'):
        print(f"\n{'-'*70}")
        print("RECOMMENDATIONS:")
        print(f"{'-'*70}")
        for rec in results['recommendations']:
            print(f"  * {rec}")

    print(f"\n{'='*70}\n")
if __name__ == "__main__":
    asyncio.run(main())
