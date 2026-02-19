"""
Document Anomaly Detection for Procurement Fraud

Detects anomalous document characteristics that may indicate manipulation:
1. Missing required documents for procedure type
2. Coordinated bid timing (multiple bids with near-identical upload dates)
3. Suspicious file characteristics (size, type, formatting)
4. Content length anomalies (suspiciously short or empty documents)
5. Identical file sizes across different bidders (template duplication)

This module works with data already present in the 'documents' table:
- doc_id, tender_id, file_name, file_size_bytes, doc_type, doc_category
- content_text (extracted text), extraction_status, upload_date, file_hash
- page_count, mime_type

Note: PDF metadata (creation date, author) is NOT available in the database.
All anomaly detection is based on file-level and content-level signals.

Author: nabavkidata.com
License: Proprietary
"""

import logging
import json
import math
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class DocumentAnomalyDetector:
    """
    Detects anomalous document characteristics in procurement tenders.

    Works exclusively with data in the 'documents' and 'tenders' tables.
    No external libraries required beyond stdlib.
    """

    # Expected document types/categories by procedure type
    # Mapped from Macedonian procurement law requirements
    REQUIRED_DOCS = {
        'open': ['specification', 'evaluation_criteria', 'notice'],
        'restricted': ['specification', 'evaluation_criteria', 'notice', 'qualification'],
        'negotiated': ['specification', 'justification'],
        'simplified': ['specification', 'notice'],
        'mini_competition': ['specification', 'notice'],
    }

    # Map doc_category values to required doc types
    DOC_CATEGORY_TO_TYPE = {
        'technical_specs': 'specification',
        'financial_docs': 'evaluation_criteria',
        'award_decision': 'notice',
        'contract': 'contract',
        'qualification_docs': 'qualification',
        'justification': 'justification',
    }

    # File name patterns to infer doc type when doc_category is missing
    FILE_NAME_PATTERNS = {
        'specification': [
            r'спецификаци', r'техничк', r'specification', r'spec',
            r'барањ', r'предмет', r'опис',
        ],
        'evaluation_criteria': [
            r'критериум', r'евалуаци', r'criteria', r'evaluation',
            r'оценувањ', r'бодувањ',
        ],
        'notice': [
            r'оглас', r'известувањ', r'notice', r'announcement',
            r'одлука', r'decision',
        ],
        'qualification': [
            r'квалификаци', r'qualification', r'способност',
            r'услов', r'докази',
        ],
        'justification': [
            r'образложени', r'justification', r'оправдан',
        ],
        'bid': [
            r'понуда', r'bid', r'offer', r'понудувач',
        ],
    }

    # Severity thresholds
    SEVERITY_CRITICAL = 'critical'
    SEVERITY_HIGH = 'high'
    SEVERITY_MEDIUM = 'medium'
    SEVERITY_LOW = 'low'

    # File size thresholds
    MIN_MEANINGFUL_FILE_SIZE = 1024       # 1 KB - below this is likely empty/corrupt
    ROUND_SIZE_TOLERANCE = 100            # bytes tolerance for "round" sizes
    IDENTICAL_SIZE_MIN_DOCS = 2           # minimum docs to flag identical sizes

    async def analyze_tender_documents(self, pool, tender_id: str) -> dict:
        """
        Full document anomaly analysis for a tender.

        Args:
            pool: asyncpg connection pool
            tender_id: The tender ID to analyze

        Returns:
            Dictionary with:
            - tender_id: str
            - total_documents: int
            - anomalies: list of anomaly dicts
            - completeness_score: float (0-1)
            - timing_anomaly_score: float (0-1)
            - anomaly_count: int
            - overall_risk_contribution: float (0-100)
        """
        async with pool.acquire() as conn:
            # Gather all anomalies
            completeness_result = await self._check_document_completeness(conn, tender_id)
            timing_anomalies = await self._check_timing_anomalies(conn, tender_id)
            file_anomalies = await self._check_file_anomalies(conn, tender_id)
            content_anomalies = await self._check_content_anomalies(conn, tender_id)

            # Get total document count
            total_docs = await conn.fetchval(
                "SELECT COUNT(*) FROM documents WHERE tender_id = $1",
                tender_id
            )

            # Combine all anomalies
            all_anomalies = (
                completeness_result.get('anomalies', [])
                + timing_anomalies
                + file_anomalies
                + content_anomalies
            )

            completeness_score = completeness_result.get('completeness_score', 1.0)

            # Compute timing anomaly score (0-1)
            timing_anomaly_score = self._compute_timing_score(timing_anomalies)

            # Compute overall risk contribution (0-100)
            overall_risk = self._compute_risk_contribution(
                all_anomalies, completeness_score, timing_anomaly_score
            )

            return {
                'tender_id': tender_id,
                'total_documents': total_docs or 0,
                'anomalies': all_anomalies,
                'completeness_score': round(completeness_score, 3),
                'timing_anomaly_score': round(timing_anomaly_score, 3),
                'anomaly_count': len(all_anomalies),
                'overall_risk_contribution': round(overall_risk, 2),
            }

    async def check_document_completeness(self, pool, tender_id: str) -> dict:
        """
        Check if required documents are present for the tender's procedure type.

        Args:
            pool: asyncpg connection pool
            tender_id: The tender ID

        Returns:
            Dictionary with present, missing, completeness_score, anomalies
        """
        async with pool.acquire() as conn:
            return await self._check_document_completeness(conn, tender_id)

    async def check_timing_anomalies(self, pool, tender_id: str) -> list:
        """
        Check for timing anomalies in documents.

        Args:
            pool: asyncpg connection pool
            tender_id: The tender ID

        Returns:
            List of anomaly dicts with type, severity, description, evidence
        """
        async with pool.acquire() as conn:
            return await self._check_timing_anomalies(conn, tender_id)

    async def check_file_anomalies(self, pool, tender_id: str) -> list:
        """
        Check for file-level anomalies.

        Args:
            pool: asyncpg connection pool
            tender_id: The tender ID

        Returns:
            List of anomaly dicts
        """
        async with pool.acquire() as conn:
            return await self._check_file_anomalies(conn, tender_id)

    async def compute_institution_doc_stats(self, pool, institution: str) -> dict:
        """
        Compute document health statistics for an institution.

        Args:
            pool: asyncpg connection pool
            institution: Name of the procuring entity

        Returns:
            Dictionary with aggregate document stats
        """
        async with pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(DISTINCT t.tender_id) AS total_tenders,
                    COUNT(d.doc_id) AS total_documents,
                    ROUND(
                        COUNT(d.doc_id)::numeric / NULLIF(COUNT(DISTINCT t.tender_id), 0),
                        2
                    ) AS avg_docs_per_tender,
                    COUNT(CASE WHEN d.extraction_status = 'success' THEN 1 END) AS success_count,
                    COUNT(CASE WHEN d.extraction_status = 'failed' THEN 1 END) AS failed_count,
                    COUNT(CASE WHEN d.extraction_status = 'pending' THEN 1 END) AS pending_count,
                    ROUND(
                        COUNT(CASE WHEN d.extraction_status = 'success' THEN 1 END)::numeric
                        / NULLIF(COUNT(d.doc_id), 0) * 100, 2
                    ) AS extraction_success_rate,
                    COUNT(CASE WHEN d.file_size_bytes IS NOT NULL AND d.file_size_bytes < 1024 THEN 1 END) AS tiny_files_count,
                    ROUND(AVG(d.file_size_bytes)::numeric, 0) AS avg_file_size_bytes,
                    COUNT(DISTINCT t.tender_id) FILTER (
                        WHERE NOT EXISTS (
                            SELECT 1 FROM documents d2
                            WHERE d2.tender_id = t.tender_id
                        )
                    ) AS tenders_without_docs
                FROM tenders t
                LEFT JOIN documents d ON t.tender_id = d.tender_id
                WHERE t.procuring_entity = $1
            """, institution)

            if not stats:
                return {
                    'institution': institution,
                    'total_tenders': 0,
                    'total_documents': 0,
                    'avg_docs_per_tender': 0,
                    'extraction_success_rate': 0,
                    'tiny_files_count': 0,
                    'avg_file_size_bytes': 0,
                    'tenders_without_docs': 0,
                    'missing_doc_rate': 0,
                }

            total_tenders = stats['total_tenders'] or 0
            tenders_without_docs = stats['tenders_without_docs'] or 0
            missing_rate = round(
                tenders_without_docs / total_tenders * 100, 2
            ) if total_tenders > 0 else 0

            return {
                'institution': institution,
                'total_tenders': total_tenders,
                'total_documents': stats['total_documents'] or 0,
                'avg_docs_per_tender': float(stats['avg_docs_per_tender'] or 0),
                'extraction_success_rate': float(stats['extraction_success_rate'] or 0),
                'success_count': stats['success_count'] or 0,
                'failed_count': stats['failed_count'] or 0,
                'pending_count': stats['pending_count'] or 0,
                'tiny_files_count': stats['tiny_files_count'] or 0,
                'avg_file_size_bytes': int(stats['avg_file_size_bytes'] or 0),
                'tenders_without_docs': tenders_without_docs,
                'missing_doc_rate': missing_rate,
            }

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    async def _check_document_completeness(self, conn, tender_id: str) -> dict:
        """Internal: Check document completeness against expected docs."""
        anomalies = []

        # Get tender procedure type
        tender = await conn.fetchrow("""
            SELECT procedure_type, status, closing_date
            FROM tenders
            WHERE tender_id = $1
        """, tender_id)

        if not tender:
            return {
                'present': [],
                'missing': [],
                'completeness_score': 0.0,
                'anomalies': [{
                    'type': 'missing_doc',
                    'severity': self.SEVERITY_LOW,
                    'description': f'Tender {tender_id} not found in database',
                    'evidence': {'tender_id': tender_id},
                }],
            }

        # Get all documents for this tender
        docs = await conn.fetch("""
            SELECT doc_id, file_name, doc_type, doc_category, file_size_bytes,
                   extraction_status
            FROM documents
            WHERE tender_id = $1
        """, tender_id)

        # No documents at all
        if not docs:
            return {
                'present': [],
                'missing': ['all_documents'],
                'completeness_score': 0.0,
                'anomalies': [{
                    'type': 'missing_doc',
                    'severity': self.SEVERITY_HIGH,
                    'description': 'No documents found for this tender',
                    'evidence': {
                        'tender_id': tender_id,
                        'status': tender['status'],
                    },
                }],
            }

        # Determine procedure type and expected docs
        proc_type = self._normalize_procedure_type(tender['procedure_type'])
        expected_types = self.REQUIRED_DOCS.get(proc_type, self.REQUIRED_DOCS.get('open', []))

        # Classify each document
        present_types = set()
        for doc in docs:
            doc_type = self._classify_document(doc)
            if doc_type:
                present_types.add(doc_type)

        # Determine missing
        missing_types = [t for t in expected_types if t not in present_types]
        present_list = [t for t in expected_types if t in present_types]

        completeness_score = (
            len(present_list) / len(expected_types) if expected_types else 1.0
        )

        # Generate anomalies for missing docs
        for missing_type in missing_types:
            severity = self.SEVERITY_HIGH if missing_type == 'specification' else self.SEVERITY_MEDIUM
            anomalies.append({
                'type': 'missing_doc',
                'severity': severity,
                'description': f'Missing required document type: {missing_type}',
                'evidence': {
                    'procedure_type': proc_type,
                    'expected': expected_types,
                    'present': list(present_types),
                    'missing_type': missing_type,
                },
            })

        return {
            'present': present_list,
            'missing': missing_types,
            'completeness_score': round(completeness_score, 3),
            'anomalies': anomalies,
        }

    async def _check_timing_anomalies(self, conn, tender_id: str) -> list:
        """
        Internal: Check for timing anomalies in documents.

        Detects:
        - Documents uploaded after tender closing date
        - Multiple documents with identical upload dates (possible coordination)
        - Bid documents with identical file hashes (copy-paste bids)
        """
        anomalies = []

        # Get tender closing date
        tender = await conn.fetchrow("""
            SELECT closing_date, opening_date, publication_date
            FROM tenders WHERE tender_id = $1
        """, tender_id)

        if not tender:
            return anomalies

        # Get documents with upload dates
        docs = await conn.fetch("""
            SELECT doc_id, file_name, doc_type, doc_category,
                   upload_date, file_hash, file_size_bytes
            FROM documents
            WHERE tender_id = $1
            ORDER BY upload_date ASC NULLS LAST
        """, tender_id)

        if not docs:
            return anomalies

        closing_date = tender['closing_date']

        # Check 1: Documents uploaded after closing date
        if closing_date:
            for doc in docs:
                if doc['upload_date'] and doc['upload_date'] > closing_date:
                    days_after = (doc['upload_date'] - closing_date).days
                    severity = self.SEVERITY_CRITICAL if days_after > 7 else self.SEVERITY_HIGH
                    anomalies.append({
                        'type': 'metadata_tampering',
                        'severity': severity,
                        'description': (
                            f'Document "{doc["file_name"]}" uploaded {days_after} '
                            f'day(s) after tender closing date'
                        ),
                        'evidence': {
                            'doc_id': str(doc['doc_id']),
                            'file_name': doc['file_name'],
                            'upload_date': str(doc['upload_date']),
                            'closing_date': str(closing_date),
                            'days_after_deadline': days_after,
                        },
                    })

        # Check 2: Documents with identical file hashes (duplicate bids)
        hash_groups = {}
        for doc in docs:
            if doc['file_hash']:
                hash_groups.setdefault(doc['file_hash'], []).append(doc)

        for file_hash, group in hash_groups.items():
            if len(group) >= 2:
                # Check if they are from different doc categories (bidder docs)
                file_names = [d['file_name'] for d in group]
                anomalies.append({
                    'type': 'timing_coordination',
                    'severity': self.SEVERITY_HIGH,
                    'description': (
                        f'{len(group)} documents share identical content hash '
                        f'(possible duplicate/template reuse)'
                    ),
                    'evidence': {
                        'file_hash': file_hash,
                        'file_count': len(group),
                        'file_names': file_names,
                        'doc_ids': [str(d['doc_id']) for d in group],
                    },
                })

        # Check 3: Multiple documents uploaded on the same date
        # (only meaningful if we have upload_date data)
        date_groups = {}
        for doc in docs:
            if doc['upload_date']:
                date_key = str(doc['upload_date'])
                date_groups.setdefault(date_key, []).append(doc)

        # Flag dates with unusually high document counts (potential batch upload)
        for upload_date, group in date_groups.items():
            if len(group) >= 5:
                # Many docs on same date is normal for tender setup, but
                # flag if they appear to be from different sources (bid docs)
                bid_like = [d for d in group if self._looks_like_bid_doc(d)]
                if len(bid_like) >= 3:
                    anomalies.append({
                        'type': 'timing_coordination',
                        'severity': self.SEVERITY_MEDIUM,
                        'description': (
                            f'{len(bid_like)} bid-like documents uploaded on '
                            f'same date ({upload_date}), possible coordination'
                        ),
                        'evidence': {
                            'upload_date': upload_date,
                            'total_docs': len(group),
                            'bid_like_docs': len(bid_like),
                            'file_names': [d['file_name'] for d in bid_like],
                        },
                    })

        return anomalies

    async def _check_file_anomalies(self, conn, tender_id: str) -> list:
        """
        Internal: Check for file-level anomalies.

        Detects:
        - Extremely small files (< 1KB - likely empty/corrupt)
        - Identical file sizes across different documents (template duplication)
        - Suspiciously round file sizes (exactly 1MB, 2MB, etc.)
        - Failed extractions that may indicate corrupt files
        """
        anomalies = []

        docs = await conn.fetch("""
            SELECT doc_id, file_name, file_size_bytes, doc_type, doc_category,
                   extraction_status, mime_type, page_count
            FROM documents
            WHERE tender_id = $1
        """, tender_id)

        if not docs:
            return anomalies

        # Check 1: Extremely small files
        for doc in docs:
            size = doc['file_size_bytes']
            if size is not None and size < self.MIN_MEANINGFUL_FILE_SIZE and size > 0:
                anomalies.append({
                    'type': 'empty_file',
                    'severity': self.SEVERITY_MEDIUM,
                    'description': (
                        f'File "{doc["file_name"]}" is suspiciously small '
                        f'({size} bytes), likely empty or corrupt'
                    ),
                    'evidence': {
                        'doc_id': str(doc['doc_id']),
                        'file_name': doc['file_name'],
                        'file_size_bytes': size,
                        'extraction_status': doc['extraction_status'],
                    },
                })
            elif size is not None and size == 0:
                anomalies.append({
                    'type': 'empty_file',
                    'severity': self.SEVERITY_HIGH,
                    'description': f'File "{doc["file_name"]}" has zero bytes',
                    'evidence': {
                        'doc_id': str(doc['doc_id']),
                        'file_name': doc['file_name'],
                        'file_size_bytes': 0,
                    },
                })

        # Check 2: Identical file sizes across different documents
        size_groups = {}
        for doc in docs:
            size = doc['file_size_bytes']
            if size and size > self.MIN_MEANINGFUL_FILE_SIZE:
                size_groups.setdefault(size, []).append(doc)

        for size, group in size_groups.items():
            if len(group) >= self.IDENTICAL_SIZE_MIN_DOCS:
                # Only flag if they have different file names (not re-uploads of same file)
                unique_names = set(d['file_name'] for d in group)
                if len(unique_names) >= 2:
                    anomalies.append({
                        'type': 'size_anomaly',
                        'severity': self.SEVERITY_MEDIUM,
                        'description': (
                            f'{len(group)} documents have identical file size '
                            f'({size:,} bytes), possible template duplication'
                        ),
                        'evidence': {
                            'file_size_bytes': size,
                            'file_count': len(group),
                            'file_names': [d['file_name'] for d in group],
                            'doc_ids': [str(d['doc_id']) for d in group],
                        },
                    })

        # Check 3: Suspiciously round file sizes
        round_sizes = [
            1024 * 1024,        # 1 MB
            2 * 1024 * 1024,    # 2 MB
            5 * 1024 * 1024,    # 5 MB
            10 * 1024 * 1024,   # 10 MB
        ]
        for doc in docs:
            size = doc['file_size_bytes']
            if size:
                for round_size in round_sizes:
                    if abs(size - round_size) < self.ROUND_SIZE_TOLERANCE:
                        anomalies.append({
                            'type': 'size_anomaly',
                            'severity': self.SEVERITY_LOW,
                            'description': (
                                f'File "{doc["file_name"]}" has suspiciously '
                                f'round size ({size:,} bytes ~ '
                                f'{round_size // (1024*1024)} MB)'
                            ),
                            'evidence': {
                                'doc_id': str(doc['doc_id']),
                                'file_name': doc['file_name'],
                                'file_size_bytes': size,
                                'nearest_round_size': round_size,
                            },
                        })
                        break  # only flag once per doc

        # Check 4: High failure rate
        failed_docs = [d for d in docs if d['extraction_status'] == 'failed']
        if len(failed_docs) > 0 and len(docs) > 0:
            failure_rate = len(failed_docs) / len(docs)
            if failure_rate >= 0.5 and len(docs) >= 3:
                anomalies.append({
                    'type': 'size_anomaly',
                    'severity': self.SEVERITY_MEDIUM,
                    'description': (
                        f'{len(failed_docs)} of {len(docs)} documents '
                        f'({failure_rate:.0%}) failed extraction, '
                        f'possible corrupt or password-protected files'
                    ),
                    'evidence': {
                        'total_docs': len(docs),
                        'failed_docs': len(failed_docs),
                        'failure_rate': round(failure_rate, 3),
                        'failed_files': [d['file_name'] for d in failed_docs],
                    },
                })

        return anomalies

    async def _check_content_anomalies(self, conn, tender_id: str) -> list:
        """
        Internal: Check for content-level anomalies in extracted text.

        Detects:
        - Documents with extracted text that is suspiciously short
        - Specification documents with very little content (possible placeholder)
        """
        anomalies = []

        docs = await conn.fetch("""
            SELECT doc_id, file_name, doc_type, doc_category,
                   LENGTH(content_text) AS content_length,
                   file_size_bytes, page_count, extraction_status
            FROM documents
            WHERE tender_id = $1 AND extraction_status = 'success'
        """, tender_id)

        if not docs:
            return anomalies

        # Check: Successful extraction but very short content
        for doc in docs:
            content_length = doc['content_length'] or 0
            file_size = doc['file_size_bytes'] or 0
            page_count = doc['page_count'] or 0

            # If file is substantial (>10KB) but extracted text is tiny (<100 chars)
            if file_size > 10240 and content_length < 100:
                anomalies.append({
                    'type': 'empty_file',
                    'severity': self.SEVERITY_MEDIUM,
                    'description': (
                        f'File "{doc["file_name"]}" is {file_size:,} bytes '
                        f'but extracted only {content_length} characters '
                        f'(possible image-only PDF or corruption)'
                    ),
                    'evidence': {
                        'doc_id': str(doc['doc_id']),
                        'file_name': doc['file_name'],
                        'file_size_bytes': file_size,
                        'content_length': content_length,
                        'page_count': page_count,
                    },
                })

            # If it has many pages but very little text per page
            if page_count and page_count > 5 and content_length > 0:
                chars_per_page = content_length / page_count
                if chars_per_page < 50:
                    anomalies.append({
                        'type': 'empty_file',
                        'severity': self.SEVERITY_LOW,
                        'description': (
                            f'File "{doc["file_name"]}" has {page_count} pages '
                            f'but only {chars_per_page:.0f} characters/page '
                            f'(mostly blank or image-based)'
                        ),
                        'evidence': {
                            'doc_id': str(doc['doc_id']),
                            'file_name': doc['file_name'],
                            'page_count': page_count,
                            'content_length': content_length,
                            'chars_per_page': round(chars_per_page, 1),
                        },
                    })

        return anomalies

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _normalize_procedure_type(self, proc_type: Optional[str]) -> str:
        """Normalize procedure type string to a known key."""
        if not proc_type:
            return 'open'

        proc_lower = proc_type.lower().strip()

        # Macedonian procedure types
        mapping = {
            'отворена': 'open',
            'ограничена': 'restricted',
            'конкурентен дијалог': 'negotiated',
            'постапка со преговарање': 'negotiated',
            'поедноставена': 'simplified',
            'мини конкуренција': 'mini_competition',
            'набавка од мала вредност': 'simplified',
            # English
            'open': 'open',
            'restricted': 'restricted',
            'negotiated': 'negotiated',
            'competitive dialogue': 'negotiated',
            'simplified': 'simplified',
            'mini competition': 'mini_competition',
        }

        for key, value in mapping.items():
            if key in proc_lower:
                return value

        return 'open'  # Default to open for unknown types

    def _classify_document(self, doc) -> Optional[str]:
        """Classify a document into a required document type."""
        # First try doc_category
        if doc['doc_category']:
            mapped = self.DOC_CATEGORY_TO_TYPE.get(doc['doc_category'])
            if mapped:
                return mapped

        # Then try doc_type
        if doc['doc_type']:
            for req_type, patterns in self.FILE_NAME_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, doc['doc_type'], re.IGNORECASE):
                        return req_type

        # Finally try file_name
        if doc['file_name']:
            fname_lower = doc['file_name'].lower()
            for req_type, patterns in self.FILE_NAME_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, fname_lower, re.IGNORECASE):
                        return req_type

        return None

    def _looks_like_bid_doc(self, doc) -> bool:
        """Check if a document appears to be a bid/offer document."""
        if doc.get('doc_category') in ('bid', 'offer', 'financial_docs'):
            return True
        name = (doc.get('file_name') or '').lower()
        for pattern in self.FILE_NAME_PATTERNS.get('bid', []):
            if re.search(pattern, name, re.IGNORECASE):
                return True
        return False

    def _compute_timing_score(self, timing_anomalies: list) -> float:
        """Compute a timing anomaly score from 0 to 1."""
        if not timing_anomalies:
            return 0.0

        severity_weights = {
            self.SEVERITY_CRITICAL: 1.0,
            self.SEVERITY_HIGH: 0.7,
            self.SEVERITY_MEDIUM: 0.4,
            self.SEVERITY_LOW: 0.2,
        }

        total_weight = sum(
            severity_weights.get(a.get('severity', 'low'), 0.1)
            for a in timing_anomalies
        )

        # Normalize to 0-1 range (cap at 3.0 weighted anomalies = 1.0)
        return min(1.0, total_weight / 3.0)

    def _compute_risk_contribution(
        self,
        anomalies: list,
        completeness_score: float,
        timing_score: float,
    ) -> float:
        """
        Compute overall risk contribution (0-100) from document anomalies.

        Weighting:
        - Completeness: 30% (inverted: lower completeness = higher risk)
        - Timing anomalies: 30%
        - File/content anomalies: 40% (severity-weighted)
        """
        # Completeness contribution: 0 completeness = 30 points, 1.0 = 0 points
        completeness_risk = (1.0 - completeness_score) * 30.0

        # Timing contribution
        timing_risk = timing_score * 30.0

        # File/content anomaly contribution
        severity_scores = {
            self.SEVERITY_CRITICAL: 15.0,
            self.SEVERITY_HIGH: 10.0,
            self.SEVERITY_MEDIUM: 5.0,
            self.SEVERITY_LOW: 2.0,
        }

        file_risk = 0.0
        for anomaly in anomalies:
            atype = anomaly.get('type', '')
            # Skip completeness and timing anomalies (already counted)
            if atype in ('missing_doc', 'metadata_tampering', 'timing_coordination'):
                continue
            file_risk += severity_scores.get(anomaly.get('severity', 'low'), 2.0)

        # Cap file risk at 40
        file_risk = min(40.0, file_risk)

        return min(100.0, completeness_risk + timing_risk + file_risk)
