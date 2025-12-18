"""
AI Agents for Nabavki Data Analysis

This package contains specialized agents for various research and analysis tasks
related to public procurement data in North Macedonia.

Agents:
- DBResearchAgent: Queries PostgreSQL database for comprehensive corruption analysis
- WebResearchAgent: Web research and market intelligence
- CompanyResearchAgent: Deep research on companies for ownership, connections, red flags
- ENabavkiAgent: Fetches official data from e-nabavki.gov.mk portal (SOURCE OF TRUTH)
- DocumentAnalysisAgent: Analyzes tender documents (PDFs, contracts) for corruption red flags
"""

from .db_research_agent import (
    DBResearchAgent,
    TenderResearch,
    CompanyResearch,
    InstitutionResearch,
)
from .web_research_agent import WebResearchAgent
from .company_research_agent import (
    CompanyResearchAgent,
    CompanyProfile,
    OwnershipInfo,
    RelatedCompany,
    PoliticalConnection,
    ShellCompanyIndicator,
    ConfidenceLevel,
    SourcedInfo,
)
from .enabavki_agent import (
    ENabavkiAgent,
    TenderDetails,
    BidderInfo,
    OfficialBidderData,
    AwardDecision,
    DocumentInfo,
    OfficialDocuments,
    DataDiscrepancy,
    VerificationResult,
    quick_verify_tender,
    quick_get_bidder_count,
)
from .document_analysis_agent import (
    DocumentAnalysisAgent,
    RedFlag,
    Severity,
    AnalysisResult,
    analyze_tender,
    check_tailored_specs,
)

__all__ = [
    # Database Research Agent
    'DBResearchAgent',
    'TenderResearch',
    'CompanyResearch',
    'InstitutionResearch',
    # Web Research Agent
    'WebResearchAgent',
    # Company Research Agent
    'CompanyResearchAgent',
    'CompanyProfile',
    'OwnershipInfo',
    'RelatedCompany',
    'PoliticalConnection',
    'ShellCompanyIndicator',
    'ConfidenceLevel',
    'SourcedInfo',
    # ENabavki Agent exports
    'ENabavkiAgent',
    'TenderDetails',
    'BidderInfo',
    'OfficialBidderData',
    'AwardDecision',
    'DocumentInfo',
    'OfficialDocuments',
    'DataDiscrepancy',
    'VerificationResult',
    'quick_verify_tender',
    'quick_get_bidder_count',
    # Document Analysis Agent
    'DocumentAnalysisAgent',
    'RedFlag',
    'Severity',
    'AnalysisResult',
    'analyze_tender',
    'check_tailored_specs',
]
