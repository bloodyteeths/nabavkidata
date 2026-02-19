"""
NLP Subpackage for Corruption Detection

Text analysis tools for detecting specification rigging patterns,
document anomalies, and named entities in tender documents.

Components:
- spec_analyzer: Core specification text analysis
- spec_similarity: Cross-tender specification similarity detection
- batch_similarity: Batch processing for similarity computation (cron)
- batch_spec_analysis: Batch processing for cron jobs
- doc_anomaly: Document anomaly detection (missing docs, timing, file issues)
- batch_doc_anomaly: Batch processing for document anomaly detection (cron)
- ner_extractor: Named Entity Recognition (people, orgs, money, dates, etc.)
- entity_store: Entity storage, querying, and conflict detection
- batch_ner: Batch NER processing for cron jobs

Author: nabavkidata.com
License: Proprietary
"""

# Import NER components (always available)
from .ner_extractor import MacedonianNERExtractor, Entity, ExtractionResult
from .entity_store import EntityStore

# Import other components with graceful fallback
try:
    from .spec_analyzer import SpecificationAnalyzer
except ImportError:
    SpecificationAnalyzer = None

try:
    from .spec_similarity import SpecSimilarityAnalyzer
except ImportError:
    SpecSimilarityAnalyzer = None

try:
    from .doc_anomaly import DocumentAnomalyDetector
except ImportError:
    DocumentAnomalyDetector = None

__all__ = [
    'MacedonianNERExtractor',
    'Entity',
    'ExtractionResult',
    'EntityStore',
    'SpecificationAnalyzer',
    'SpecSimilarityAnalyzer',
    'DocumentAnomalyDetector',
]
