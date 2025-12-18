#!/usr/bin/env python3
"""
Company Research Agent for Corruption Detection

This agent performs deep research on companies to identify:
- Ownership structures and beneficial owners
- Related companies (same owner/director/address)
- Political connections
- Financial health indicators
- Shell company red flags

Data Sources:
- CRM (Central Registry of Macedonia): https://www.crm.com.mk
- Serper API for Google Search
- Cross-referencing multiple public sources

Author: nabavkidata.com
License: Proprietary
"""

import asyncio
import aiohttp
import logging
import re
import json
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Serper API configuration
SERPER_API_KEY = "4415877ad2273c0e07330ca8400a2e058186192a"
SERPER_URL = "https://google.serper.dev/search"

# Macedonian business data sources
CRM_BASE_URL = "https://www.crm.com.mk"
ENABAVKI_URL = "https://e-nabavki.gov.mk"


class ConfidenceLevel(Enum):
    """Confidence levels for information"""
    HIGH = "high"  # Official source, direct match
    MEDIUM = "medium"  # Reliable source, indirect match
    LOW = "low"  # Unverified source, possible match
    UNVERIFIED = "unverified"  # Single source, needs verification


@dataclass
class SourcedInfo:
    """Information with source attribution and confidence"""
    value: Any
    source: str
    confidence: ConfidenceLevel
    retrieved_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: Optional[str] = None


@dataclass
class CompanyProfile:
    """Complete company profile"""
    company_name: str
    legal_name: Optional[SourcedInfo] = None
    embs: Optional[SourcedInfo] = None  # Registration number
    edb: Optional[SourcedInfo] = None  # Tax number
    address: Optional[SourcedInfo] = None
    founded_date: Optional[SourcedInfo] = None
    legal_form: Optional[SourcedInfo] = None  # DOO, DOOEL, AD, etc.
    main_activity: Optional[SourcedInfo] = None
    industry: Optional[SourcedInfo] = None
    employees: Optional[SourcedInfo] = None
    revenue: Optional[SourcedInfo] = None
    status: Optional[SourcedInfo] = None  # Active, Inactive, Liquidation
    raw_data: Dict = field(default_factory=dict)


@dataclass
class OwnershipInfo:
    """Company ownership structure"""
    company_name: str
    owners: List[Dict] = field(default_factory=list)  # {name, percentage, type, since}
    beneficial_owners: List[Dict] = field(default_factory=list)
    directors: List[Dict] = field(default_factory=list)  # {name, position, since}
    board_members: List[Dict] = field(default_factory=list)
    management: List[Dict] = field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.UNVERIFIED
    sources: List[str] = field(default_factory=list)


@dataclass
class RelatedCompany:
    """A company related through ownership/management/address"""
    company_name: str
    relation_type: str  # 'same_owner', 'same_director', 'same_address', 'parent', 'subsidiary', 'similar_name'
    shared_person: Optional[str] = None
    shared_address: Optional[str] = None
    confidence: ConfidenceLevel = ConfidenceLevel.UNVERIFIED
    risk_notes: Optional[str] = None


@dataclass
class PoliticalConnection:
    """A political connection found"""
    person_name: str
    company_role: str  # 'owner', 'director', 'board_member'
    political_role: Optional[str] = None
    party: Optional[str] = None
    government_position: Optional[str] = None
    source: str = ""
    confidence: ConfidenceLevel = ConfidenceLevel.UNVERIFIED


@dataclass
class ShellCompanyIndicator:
    """Indicator that a company may be a shell"""
    indicator_type: str
    description: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    evidence: str
    score: int  # 0-100


class CompanyResearchAgent:
    """
    Deep research agent for company intelligence and corruption detection.

    Uses multiple data sources to build comprehensive company profiles,
    identify ownership structures, find related companies, and detect
    red flags that may indicate corruption or fraud.
    """

    def __init__(self, serper_api_key: str = SERPER_API_KEY):
        self.serper_api_key = serper_api_key
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _ensure_session(self):
        """Ensure we have an active session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def _serper_search(
        self,
        query: str,
        num_results: int = 10,
        site_filter: Optional[str] = None,
        language: str = "mk",
        country: str = "mk"
    ) -> List[Dict]:
        """
        Perform a search using Serper API.

        Args:
            query: Search query
            num_results: Number of results to return
            site_filter: Optional site: filter (e.g., 'crm.com.mk')
            language: Search language
            country: Search country

        Returns:
            List of search results
        """
        await self._ensure_session()

        # Build query with site filter if provided
        full_query = f"site:{site_filter} {query}" if site_filter else query

        payload = {
            "q": full_query,
            "gl": country,
            "hl": language,
            "num": num_results
        }

        headers = {
            "X-API-KEY": self.serper_api_key,
            "Content-Type": "application/json"
        }

        try:
            async with self.session.post(
                SERPER_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []

                    # Process organic results
                    for item in data.get('organic', []):
                        results.append({
                            'title': item.get('title', ''),
                            'url': item.get('link', ''),
                            'snippet': item.get('snippet', ''),
                            'position': item.get('position', 0)
                        })

                    # Process knowledge graph if available
                    if 'knowledgeGraph' in data:
                        kg = data['knowledgeGraph']
                        results.insert(0, {
                            'title': kg.get('title', ''),
                            'url': kg.get('website', ''),
                            'snippet': kg.get('description', ''),
                            'knowledge_graph': True,
                            'attributes': kg.get('attributes', {})
                        })

                    logger.info(f"Serper search returned {len(results)} results for: {full_query[:50]}")
                    return results
                else:
                    logger.warning(f"Serper API returned status {response.status}")
                    return []

        except asyncio.TimeoutError:
            logger.error(f"Serper search timed out for: {query[:50]}")
            return []
        except Exception as e:
            logger.error(f"Serper search failed: {e}")
            return []

    async def _search_crm(self, company_name: str) -> List[Dict]:
        """Search CRM (Central Registry of Macedonia) for company info"""
        return await self._serper_search(
            query=f'"{company_name}"',
            site_filter="crm.com.mk",
            num_results=10
        )

    async def _extract_crm_data(self, search_results: List[Dict]) -> Dict:
        """Extract company data from CRM search results"""
        extracted = {}

        for result in search_results:
            snippet = result.get('snippet', '')
            title = result.get('title', '')

            # Extract EMBS (registration number) - typically 6-7 digit number
            embs_match = re.search(r'ЕМБС[:\s]*(\d{6,7})', snippet, re.IGNORECASE)
            if not embs_match:
                embs_match = re.search(r'(?:регистарски|матичен)[^0-9]*(\d{6,7})', snippet, re.IGNORECASE)
            if embs_match and 'embs' not in extracted:
                extracted['embs'] = embs_match.group(1)

            # Extract EDB (tax number) - typically 13 digit number starting with 4
            edb_match = re.search(r'ЕДБ[:\s]*(4\d{12})', snippet, re.IGNORECASE)
            if not edb_match:
                edb_match = re.search(r'(?:даночен)[^0-9]*(4\d{12})', snippet, re.IGNORECASE)
            if edb_match and 'edb' not in extracted:
                extracted['edb'] = edb_match.group(1)

            # Extract legal form
            legal_forms = ['ДООЕЛ', 'ДОО', 'АД', 'ДППУ', 'ЈП', 'ДПТУ', 'ТП']
            for form in legal_forms:
                if form in snippet.upper() or form in title.upper():
                    extracted['legal_form'] = form
                    break

            # Extract address patterns
            address_patterns = [
                r'(?:адреса|седиште)[:\s]*([^,\n]+(?:,[^,\n]+)?)',
                r'ул\.?\s*([^,\n]+)',
                r'бул\.?\s*([^,\n]+)'
            ]
            for pattern in address_patterns:
                addr_match = re.search(pattern, snippet, re.IGNORECASE)
                if addr_match and 'address' not in extracted:
                    extracted['address'] = addr_match.group(1).strip()
                    break

            # Extract founding date
            date_patterns = [
                r'основано?[:\s]*(\d{1,2}[./]\d{1,2}[./]\d{2,4})',
                r'(\d{1,2}[./]\d{1,2}[./]\d{4})',
            ]
            for pattern in date_patterns:
                date_match = re.search(pattern, snippet)
                if date_match and 'founded_date' not in extracted:
                    extracted['founded_date'] = date_match.group(1)
                    break

            # Extract activity/industry
            activity_match = re.search(
                r'(?:дејност|активност)[:\s]*([^.\n]+)',
                snippet,
                re.IGNORECASE
            )
            if activity_match and 'main_activity' not in extracted:
                extracted['main_activity'] = activity_match.group(1).strip()

        return extracted

    async def get_company_profile(self, company_name: str) -> Dict:
        """
        Build complete company profile from multiple sources.

        Args:
            company_name: Company name to research

        Returns:
            Dictionary with company profile information including:
            - Full legal name
            - Registration number (EMBS)
            - Tax number (EDB)
            - Address
            - Founded date
            - Legal form (DOO, DOOEL, AD, etc.)
            - Main activity/industry
            - Size (employees, revenue if available)
            - Confidence scores for each piece of information
        """
        logger.info(f"Building company profile for: {company_name}")

        profile = {
            'company_name': company_name,
            'legal_name': None,
            'embs': None,
            'edb': None,
            'address': None,
            'founded_date': None,
            'legal_form': None,
            'main_activity': None,
            'industry': None,
            'employees': None,
            'revenue': None,
            'status': None,
            'sources': [],
            'confidence_score': 0,
            'retrieved_at': datetime.now().isoformat()
        }

        # Search CRM for official company data
        crm_results = await self._search_crm(company_name)
        if crm_results:
            profile['sources'].append('crm.com.mk')
            crm_data = await self._extract_crm_data(crm_results)

            # Update profile with CRM data (high confidence - official source)
            if 'embs' in crm_data:
                profile['embs'] = {
                    'value': crm_data['embs'],
                    'source': 'crm.com.mk',
                    'confidence': 'high'
                }
            if 'edb' in crm_data:
                profile['edb'] = {
                    'value': crm_data['edb'],
                    'source': 'crm.com.mk',
                    'confidence': 'high'
                }
            if 'legal_form' in crm_data:
                profile['legal_form'] = {
                    'value': crm_data['legal_form'],
                    'source': 'crm.com.mk',
                    'confidence': 'high'
                }
            if 'address' in crm_data:
                profile['address'] = {
                    'value': crm_data['address'],
                    'source': 'crm.com.mk',
                    'confidence': 'high'
                }
            if 'founded_date' in crm_data:
                profile['founded_date'] = {
                    'value': crm_data['founded_date'],
                    'source': 'crm.com.mk',
                    'confidence': 'high'
                }
            if 'main_activity' in crm_data:
                profile['main_activity'] = {
                    'value': crm_data['main_activity'],
                    'source': 'crm.com.mk',
                    'confidence': 'high'
                }

        # Search general web for additional information
        general_results = await self._serper_search(
            query=f'"{company_name}" Македонија компанија',
            num_results=10
        )

        if general_results:
            profile['sources'].append('web_search')

            # Extract additional info from web results
            for result in general_results:
                snippet = result.get('snippet', '')

                # Look for employee count
                emp_match = re.search(r'(\d+)\s*(?:вработени|employees)', snippet, re.IGNORECASE)
                if emp_match and not profile['employees']:
                    profile['employees'] = {
                        'value': int(emp_match.group(1)),
                        'source': result.get('url', 'web_search'),
                        'confidence': 'medium'
                    }

                # Look for revenue information
                rev_patterns = [
                    r'(?:приход|revenue|оброт)[:\s]*([\d,.]+)\s*(?:МКД|MKD|EUR|денари)',
                    r'([\d,.]+)\s*(?:милион|million)\s*(?:МКД|MKD|EUR|денари)'
                ]
                for pattern in rev_patterns:
                    rev_match = re.search(pattern, snippet, re.IGNORECASE)
                    if rev_match and not profile['revenue']:
                        profile['revenue'] = {
                            'value': rev_match.group(1),
                            'source': result.get('url', 'web_search'),
                            'confidence': 'low'
                        }
                        break

        # Calculate overall confidence score
        fields_found = sum(1 for k, v in profile.items()
                         if v and k not in ['company_name', 'sources', 'confidence_score', 'retrieved_at'])
        profile['confidence_score'] = min(100, fields_found * 12)

        logger.info(f"Profile built with confidence {profile['confidence_score']}%: {company_name}")
        return profile

    async def get_ownership(self, company_name: str) -> Dict:
        """
        Find company ownership structure.

        Args:
            company_name: Company name to research

        Returns:
            Dictionary with ownership information:
            - Owners/shareholders with percentages
            - Ultimate beneficial owners
            - Directors/management
            - Board members if applicable
        """
        logger.info(f"Researching ownership for: {company_name}")

        ownership = {
            'company_name': company_name,
            'owners': [],
            'beneficial_owners': [],
            'directors': [],
            'board_members': [],
            'management': [],
            'sources': [],
            'confidence': 'unverified',
            'retrieved_at': datetime.now().isoformat()
        }

        # Search CRM for ownership info
        crm_results = await self._serper_search(
            query=f'"{company_name}" сопственик основач',
            site_filter="crm.com.mk",
            num_results=10
        )

        # Search general web for ownership
        web_results = await self._serper_search(
            query=f'"{company_name}" сопственик директор управител',
            num_results=15
        )

        all_results = crm_results + web_results

        # Extract names that appear to be associated with the company
        person_names = set()
        for result in all_results:
            snippet = result.get('snippet', '')
            title = result.get('title', '')
            text = f"{title} {snippet}"

            # Director/manager patterns
            director_patterns = [
                r'(?:директор|управител|менаџер)[:\s]*([А-Яа-я\s]+)',
                r'([А-Яа-я]+\s+[А-Яа-я]+)\s*[-–]\s*(?:директор|управител)',
            ]
            for pattern in director_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    name = match.strip()
                    if len(name) > 5 and len(name.split()) >= 2:
                        ownership['directors'].append({
                            'name': name,
                            'position': 'директор',
                            'source': result.get('url', 'search'),
                            'confidence': 'medium'
                        })
                        person_names.add(name)

            # Owner patterns
            owner_patterns = [
                r'(?:сопственик|основач|содружник)[:\s]*([А-Яа-я\s]+)',
                r'([А-Яа-я]+\s+[А-Яа-я]+)\s*(?:е сопственик|основал|основа)',
            ]
            for pattern in owner_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    name = match.strip()
                    if len(name) > 5 and len(name.split()) >= 2:
                        ownership['owners'].append({
                            'name': name,
                            'type': 'physical_person',
                            'source': result.get('url', 'search'),
                            'confidence': 'medium'
                        })
                        person_names.add(name)

            # Ownership percentage patterns
            pct_match = re.search(r'([А-Яа-я\s]+)[:\s]*(\d{1,3})[%\s]*(?:удел|сопственост)', text)
            if pct_match:
                name = pct_match.group(1).strip()
                pct = int(pct_match.group(2))
                for owner in ownership['owners']:
                    if name in owner.get('name', ''):
                        owner['percentage'] = pct
                        break

        # Deduplicate
        seen_directors = set()
        unique_directors = []
        for d in ownership['directors']:
            if d['name'] not in seen_directors:
                seen_directors.add(d['name'])
                unique_directors.append(d)
        ownership['directors'] = unique_directors

        seen_owners = set()
        unique_owners = []
        for o in ownership['owners']:
            if o['name'] not in seen_owners:
                seen_owners.add(o['name'])
                unique_owners.append(o)
        ownership['owners'] = unique_owners

        # Set sources and confidence
        if crm_results:
            ownership['sources'].append('crm.com.mk')
            ownership['confidence'] = 'medium'
        if web_results:
            ownership['sources'].append('web_search')

        if ownership['owners'] or ownership['directors']:
            ownership['confidence'] = 'medium'
        else:
            ownership['confidence'] = 'low'

        logger.info(f"Found {len(ownership['owners'])} owners, {len(ownership['directors'])} directors")
        return ownership

    async def find_related_companies(self, company_name: str) -> Dict:
        """
        Find companies related through ownership, management, or address.

        This is CRITICAL for detecting:
        - Bid rigging (related companies bidding against each other)
        - Shell company fraud
        - Conflict of interest

        Args:
            company_name: Company name to research

        Returns:
            Dictionary with related companies grouped by relation type
        """
        logger.info(f"Finding related companies for: {company_name}")

        result = {
            'company_name': company_name,
            'same_owner': [],
            'same_director': [],
            'same_address': [],
            'parent_subsidiary': [],
            'similar_names': [],
            'risk_assessment': {
                'bid_rigging_risk': 'low',
                'shell_company_risk': 'low',
                'conflict_of_interest_risk': 'low'
            },
            'sources': [],
            'retrieved_at': datetime.now().isoformat()
        }

        # First get ownership info
        ownership = await self.get_ownership(company_name)

        # Get company profile for address
        profile = await self.get_company_profile(company_name)

        # Search for other companies owned by same people
        for owner in ownership.get('owners', []):
            owner_name = owner.get('name', '')
            if not owner_name:
                continue

            logger.info(f"Searching for other companies owned by: {owner_name}")

            owner_results = await self._serper_search(
                query=f'"{owner_name}" сопственик компанија фирма',
                num_results=15
            )

            for search_result in owner_results:
                snippet = search_result.get('snippet', '').lower()
                title = search_result.get('title', '')

                # Look for company names in results
                # Exclude the original company
                if company_name.lower() not in snippet and company_name.lower() not in title.lower():
                    # Try to extract company names
                    company_patterns = [
                        r'([А-Яа-я\s]+)\s*(?:ДООЕЛ|ДОО|АД)',
                        r'(?:компанија|фирма|друштво)\s+([А-Яа-я\s]+)',
                    ]
                    for pattern in company_patterns:
                        matches = re.findall(pattern, title + ' ' + snippet, re.IGNORECASE)
                        for match in matches:
                            related_name = match.strip()
                            if (related_name and
                                len(related_name) > 3 and
                                related_name.lower() != company_name.lower()):
                                result['same_owner'].append({
                                    'company_name': related_name,
                                    'shared_person': owner_name,
                                    'person_role': 'owner',
                                    'source': search_result.get('url', 'search'),
                                    'confidence': 'medium'
                                })

        # Search for other companies with same director
        for director in ownership.get('directors', []):
            dir_name = director.get('name', '')
            if not dir_name:
                continue

            logger.info(f"Searching for other companies directed by: {dir_name}")

            dir_results = await self._serper_search(
                query=f'"{dir_name}" директор компанија фирма',
                num_results=15
            )

            for search_result in dir_results:
                snippet = search_result.get('snippet', '').lower()
                title = search_result.get('title', '')

                if company_name.lower() not in snippet and company_name.lower() not in title.lower():
                    company_patterns = [
                        r'([А-Яа-я\s]+)\s*(?:ДООЕЛ|ДОО|АД)',
                        r'(?:компанија|фирма|друштво)\s+([А-Яа-я\s]+)',
                    ]
                    for pattern in company_patterns:
                        matches = re.findall(pattern, title + ' ' + snippet, re.IGNORECASE)
                        for match in matches:
                            related_name = match.strip()
                            if (related_name and
                                len(related_name) > 3 and
                                related_name.lower() != company_name.lower()):
                                result['same_director'].append({
                                    'company_name': related_name,
                                    'shared_person': dir_name,
                                    'person_role': 'director',
                                    'source': search_result.get('url', 'search'),
                                    'confidence': 'medium'
                                })

        # Search for companies at same address
        address = profile.get('address', {})
        if isinstance(address, dict):
            address = address.get('value', '')
        if address:
            logger.info(f"Searching for companies at address: {address}")

            addr_results = await self._serper_search(
                query=f'"{address}" компанија фирма',
                num_results=10
            )

            for search_result in addr_results:
                snippet = search_result.get('snippet', '').lower()
                title = search_result.get('title', '')

                if company_name.lower() not in snippet and company_name.lower() not in title.lower():
                    result['same_address'].append({
                        'company_name': title[:50],  # Use title as proxy
                        'shared_address': address,
                        'source': search_result.get('url', 'search'),
                        'confidence': 'low'
                    })

        # Search for similar names (potential shell companies)
        # Generate name variations
        name_parts = company_name.split()
        if len(name_parts) > 0:
            # Search for variations of the first word
            main_word = name_parts[0]
            if len(main_word) > 3:
                similar_results = await self._serper_search(
                    query=f'{main_word} ДООЕЛ OR ДОО Македонија',
                    num_results=10
                )

                for search_result in similar_results:
                    title = search_result.get('title', '')
                    if (title and
                        company_name.lower() not in title.lower() and
                        main_word.lower() in title.lower()):
                        result['similar_names'].append({
                            'company_name': title[:50],
                            'similarity_reason': f'Contains "{main_word}"',
                            'source': search_result.get('url', 'search'),
                            'confidence': 'low'
                        })

        # Deduplicate results
        for key in ['same_owner', 'same_director', 'same_address', 'similar_names']:
            seen = set()
            unique = []
            for item in result[key]:
                name = item.get('company_name', '').lower()
                if name and name not in seen:
                    seen.add(name)
                    unique.append(item)
            result[key] = unique

        # Risk assessment
        total_related = (len(result['same_owner']) + len(result['same_director']) +
                        len(result['same_address']) + len(result['similar_names']))

        if len(result['same_owner']) >= 2 or len(result['same_director']) >= 2:
            result['risk_assessment']['bid_rigging_risk'] = 'high'
        elif total_related >= 3:
            result['risk_assessment']['bid_rigging_risk'] = 'medium'

        if len(result['same_address']) >= 3:
            result['risk_assessment']['shell_company_risk'] = 'high'
        elif len(result['same_address']) >= 2:
            result['risk_assessment']['shell_company_risk'] = 'medium'

        if len(result['same_owner']) >= 1 and len(result['same_director']) >= 1:
            result['risk_assessment']['conflict_of_interest_risk'] = 'medium'
        if total_related >= 5:
            result['risk_assessment']['conflict_of_interest_risk'] = 'high'

        result['sources'] = ['crm.com.mk', 'web_search']

        logger.info(f"Found {total_related} related companies")
        return result

    async def check_political_connections(self, company_name: str) -> Dict:
        """
        Search for political connections of company owners/directors.

        Searches for:
        - Owners with political roles
        - Directors with government positions
        - Political party donations
        - Government contracts history

        Args:
            company_name: Company name to research

        Returns:
            Dictionary with political connections found
        """
        logger.info(f"Checking political connections for: {company_name}")

        result = {
            'company_name': company_name,
            'political_connections': [],
            'government_contracts': [],
            'party_affiliations': [],
            'risk_level': 'low',
            'sources': [],
            'retrieved_at': datetime.now().isoformat()
        }

        # First get ownership to know who to search for
        ownership = await self.get_ownership(company_name)

        # Combine all people associated with the company
        people = []
        for owner in ownership.get('owners', []):
            people.append({'name': owner.get('name', ''), 'role': 'сопственик'})
        for director in ownership.get('directors', []):
            people.append({'name': director.get('name', ''), 'role': 'директор'})

        # Political search terms in Macedonian
        political_terms = [
            'политика',
            'партија',
            'функционер',
            'министер',
            'пратеник',
            'градоначалник',
            'советник',
            'владин',
            'СДСМ',
            'ВМРО-ДПМНЕ',
            'ДУИ',
            'влада'
        ]

        for person in people:
            name = person.get('name', '')
            if not name or len(name) < 5:
                continue

            logger.info(f"Checking political connections for: {name}")

            for term in political_terms[:5]:  # Limit to avoid too many API calls
                search_query = f'"{name}" {term}'

                results = await self._serper_search(
                    query=search_query,
                    num_results=5
                )

                for search_result in results:
                    snippet = search_result.get('snippet', '')
                    title = search_result.get('title', '')
                    url = search_result.get('url', '')

                    # Check if this looks like a real political connection
                    political_indicators = [
                        'министер', 'пратеник', 'градоначалник', 'советник',
                        'партија', 'СДСМ', 'ВМРО', 'ДУИ', 'влада', 'функционер',
                        'избори', 'политичар', 'member of parliament', 'minister'
                    ]

                    text = f"{title} {snippet}".lower()
                    found_indicators = [ind for ind in political_indicators if ind.lower() in text]

                    if found_indicators and name.lower() in text:
                        connection = {
                            'person_name': name,
                            'company_role': person['role'],
                            'political_indicators': found_indicators,
                            'context': snippet[:200],
                            'source': url,
                            'confidence': 'medium' if len(found_indicators) >= 2 else 'low'
                        }

                        # Try to extract specific political role
                        role_patterns = [
                            r'(министер[^\s,]*)',
                            r'(пратеник)',
                            r'(градоначалник)',
                            r'(член на [^,\.]+)',
                            r'(советник)',
                        ]
                        for pattern in role_patterns:
                            match = re.search(pattern, text, re.IGNORECASE)
                            if match:
                                connection['political_role'] = match.group(1)
                                connection['confidence'] = 'medium'
                                break

                        # Check for party affiliation
                        parties = ['СДСМ', 'ВМРО-ДПМНЕ', 'ДУИ', 'Левица', 'ДПА', 'БЕСА']
                        for party in parties:
                            if party.lower() in text:
                                connection['party'] = party
                                break

                        result['political_connections'].append(connection)

        # Search for government contracts
        contract_results = await self._serper_search(
            query=f'"{company_name}" тендер јавна набавка влада',
            site_filter="e-nabavki.gov.mk",
            num_results=10
        )

        for search_result in contract_results:
            result['government_contracts'].append({
                'title': search_result.get('title', ''),
                'url': search_result.get('url', ''),
                'snippet': search_result.get('snippet', ''),
                'source': 'e-nabavki.gov.mk'
            })

        # Deduplicate political connections
        seen = set()
        unique_connections = []
        for conn in result['political_connections']:
            key = (conn['person_name'], conn.get('political_role', ''))
            if key not in seen:
                seen.add(key)
                unique_connections.append(conn)
        result['political_connections'] = unique_connections

        # Assess risk level
        if len(result['political_connections']) >= 2:
            result['risk_level'] = 'high'
        elif len(result['political_connections']) >= 1:
            result['risk_level'] = 'medium'
        elif len(result['government_contracts']) >= 5:
            result['risk_level'] = 'medium'

        result['sources'] = ['web_search', 'e-nabavki.gov.mk']

        logger.info(f"Found {len(result['political_connections'])} political connections")
        return result

    async def get_financial_health(self, company_name: str) -> Dict:
        """
        Assess company financial situation.

        Looks for:
        - Revenue trends
        - Profitability
        - Debt levels
        - Bankruptcy proceedings
        - Court cases

        Args:
            company_name: Company name to research

        Returns:
            Dictionary with financial health indicators
        """
        logger.info(f"Assessing financial health for: {company_name}")

        result = {
            'company_name': company_name,
            'revenue_info': [],
            'profitability': None,
            'debt_indicators': [],
            'bankruptcy_status': None,
            'court_cases': [],
            'financial_health_score': 'unknown',
            'red_flags': [],
            'sources': [],
            'retrieved_at': datetime.now().isoformat()
        }

        # Search for financial information
        financial_queries = [
            f'"{company_name}" приход добивка финансии',
            f'"{company_name}" стечај ликвидација блокирана',
            f'"{company_name}" суд тужба должник',
        ]

        for query in financial_queries:
            results = await self._serper_search(query, num_results=10)

            for search_result in results:
                snippet = search_result.get('snippet', '')
                url = search_result.get('url', '')

                # Look for revenue information
                rev_patterns = [
                    r'приход[:\s]*([\d,.]+)\s*(?:МКД|MKD|денари|милион)',
                    r'([\d,.]+)\s*(?:милион|million)\s*(?:приход|оброт)',
                    r'revenue[:\s]*([\d,.]+)',
                ]
                for pattern in rev_patterns:
                    match = re.search(pattern, snippet, re.IGNORECASE)
                    if match:
                        result['revenue_info'].append({
                            'value': match.group(1),
                            'source': url,
                            'context': snippet[:150]
                        })

                # Look for bankruptcy/liquidation indicators
                bankruptcy_terms = ['стечај', 'ликвидација', 'затворена', 'престанала', 'bankruptcy', 'liquidation']
                for term in bankruptcy_terms:
                    if term in snippet.lower():
                        result['bankruptcy_status'] = {
                            'indicator': term,
                            'context': snippet[:150],
                            'source': url
                        }
                        result['red_flags'].append(f'Bankruptcy/liquidation indicator: {term}')

                # Look for debt/blocked account indicators
                debt_terms = ['блокирана', 'должник', 'долг', 'неплатени', 'debt', 'blocked']
                for term in debt_terms:
                    if term in snippet.lower():
                        result['debt_indicators'].append({
                            'indicator': term,
                            'context': snippet[:150],
                            'source': url
                        })
                        result['red_flags'].append(f'Debt indicator: {term}')

                # Look for court cases
                court_terms = ['суд', 'тужба', 'пресуда', 'court', 'lawsuit']
                for term in court_terms:
                    if term in snippet.lower():
                        result['court_cases'].append({
                            'indicator': term,
                            'context': snippet[:150],
                            'source': url
                        })

        # Assess financial health score
        red_flag_count = len(result['red_flags'])
        if result['bankruptcy_status']:
            result['financial_health_score'] = 'critical'
        elif red_flag_count >= 3:
            result['financial_health_score'] = 'poor'
        elif red_flag_count >= 1:
            result['financial_health_score'] = 'concerning'
        elif result['revenue_info']:
            result['financial_health_score'] = 'appears_stable'
        else:
            result['financial_health_score'] = 'insufficient_data'

        result['sources'] = ['web_search']

        logger.info(f"Financial health assessment: {result['financial_health_score']}")
        return result

    async def detect_shell_company_indicators(self, company_name: str) -> Dict:
        """
        Check for shell company red flags.

        Indicators checked:
        - Recently formed before tender
        - Minimal employees
        - No real business activity
        - Multiple address changes
        - Nominee directors
        - Unusual ownership structures

        Args:
            company_name: Company name to research

        Returns:
            Dictionary with shell company indicators and risk score
        """
        logger.info(f"Detecting shell company indicators for: {company_name}")

        result = {
            'company_name': company_name,
            'indicators': [],
            'total_score': 0,
            'risk_level': 'low',
            'analysis': '',
            'sources': [],
            'retrieved_at': datetime.now().isoformat()
        }

        # Get company profile
        profile = await self.get_company_profile(company_name)

        # Get ownership info
        ownership = await self.get_ownership(company_name)

        # Get related companies
        related = await self.find_related_companies(company_name)

        # Get financial health
        financial = await self.get_financial_health(company_name)

        # Check indicators

        # 1. Recently formed (within last 2 years)
        founded = profile.get('founded_date', {})
        if isinstance(founded, dict):
            founded_value = founded.get('value', '')
        else:
            founded_value = str(founded) if founded else ''

        if founded_value:
            try:
                # Try to parse date
                year_match = re.search(r'20(\d{2})', founded_value)
                if year_match:
                    year = 2000 + int(year_match.group(1))
                    current_year = datetime.now().year
                    age = current_year - year

                    if age <= 1:
                        result['indicators'].append({
                            'type': 'recently_formed',
                            'description': f'Company formed in {year} (less than 1 year old)',
                            'severity': 'high',
                            'score': 30
                        })
                    elif age <= 2:
                        result['indicators'].append({
                            'type': 'recently_formed',
                            'description': f'Company formed in {year} (1-2 years old)',
                            'severity': 'medium',
                            'score': 15
                        })
            except:
                pass

        # 2. Minimal employees
        employees = profile.get('employees', {})
        if isinstance(employees, dict):
            emp_count = employees.get('value', 0)
        else:
            emp_count = employees if employees else 0

        if emp_count and int(emp_count) <= 1:
            result['indicators'].append({
                'type': 'minimal_employees',
                'description': f'Company has only {emp_count} employee(s)',
                'severity': 'medium',
                'score': 20
            })
        elif emp_count and int(emp_count) <= 3:
            result['indicators'].append({
                'type': 'few_employees',
                'description': f'Company has only {emp_count} employees',
                'severity': 'low',
                'score': 10
            })

        # 3. Multiple companies at same address
        if len(related.get('same_address', [])) >= 3:
            result['indicators'].append({
                'type': 'shared_address',
                'description': f'{len(related["same_address"])} companies at same address',
                'severity': 'high',
                'score': 25
            })
        elif len(related.get('same_address', [])) >= 2:
            result['indicators'].append({
                'type': 'shared_address',
                'description': f'{len(related["same_address"])} companies at same address',
                'severity': 'medium',
                'score': 15
            })

        # 4. Complex ownership network
        total_related = (len(related.get('same_owner', [])) +
                        len(related.get('same_director', [])))
        if total_related >= 5:
            result['indicators'].append({
                'type': 'complex_ownership',
                'description': f'Owner/director linked to {total_related} other companies',
                'severity': 'high',
                'score': 25
            })
        elif total_related >= 3:
            result['indicators'].append({
                'type': 'ownership_network',
                'description': f'Owner/director linked to {total_related} other companies',
                'severity': 'medium',
                'score': 15
            })

        # 5. Financial red flags
        if financial.get('bankruptcy_status'):
            result['indicators'].append({
                'type': 'bankruptcy',
                'description': 'Company has bankruptcy/liquidation indicators',
                'severity': 'critical',
                'score': 40
            })

        if len(financial.get('debt_indicators', [])) >= 2:
            result['indicators'].append({
                'type': 'debt_issues',
                'description': 'Multiple debt/blocked account indicators',
                'severity': 'high',
                'score': 25
            })

        # 6. No clear business activity
        activity = profile.get('main_activity', {})
        if isinstance(activity, dict):
            activity_value = activity.get('value', '')
        else:
            activity_value = str(activity) if activity else ''

        if not activity_value:
            result['indicators'].append({
                'type': 'no_activity',
                'description': 'No main business activity found in public records',
                'severity': 'medium',
                'score': 15
            })

        # Calculate total score
        result['total_score'] = sum(ind['score'] for ind in result['indicators'])

        # Determine risk level
        if result['total_score'] >= 70:
            result['risk_level'] = 'critical'
            result['analysis'] = 'HIGH PROBABILITY of shell company. Multiple strong indicators present.'
        elif result['total_score'] >= 50:
            result['risk_level'] = 'high'
            result['analysis'] = 'Significant shell company risk. Further investigation recommended.'
        elif result['total_score'] >= 30:
            result['risk_level'] = 'medium'
            result['analysis'] = 'Some shell company indicators present. Monitor closely.'
        elif result['total_score'] >= 15:
            result['risk_level'] = 'low'
            result['analysis'] = 'Minor indicators present but likely legitimate business.'
        else:
            result['risk_level'] = 'minimal'
            result['analysis'] = 'No significant shell company indicators detected.'

        result['sources'] = ['crm.com.mk', 'web_search']

        logger.info(f"Shell company risk: {result['risk_level']} (score: {result['total_score']})")
        return result

    async def full_company_investigation(self, company_name: str) -> Dict:
        """
        Perform comprehensive company investigation combining all methods.

        Args:
            company_name: Company name to investigate

        Returns:
            Complete investigation report with all findings
        """
        logger.info(f"Starting full investigation for: {company_name}")

        # Run all investigations in parallel for efficiency
        results = await asyncio.gather(
            self.get_company_profile(company_name),
            self.get_ownership(company_name),
            self.find_related_companies(company_name),
            self.check_political_connections(company_name),
            self.get_financial_health(company_name),
            self.detect_shell_company_indicators(company_name),
            return_exceptions=True
        )

        # Compile report
        report = {
            'company_name': company_name,
            'investigation_date': datetime.now().isoformat(),
            'profile': results[0] if not isinstance(results[0], Exception) else {'error': str(results[0])},
            'ownership': results[1] if not isinstance(results[1], Exception) else {'error': str(results[1])},
            'related_companies': results[2] if not isinstance(results[2], Exception) else {'error': str(results[2])},
            'political_connections': results[3] if not isinstance(results[3], Exception) else {'error': str(results[3])},
            'financial_health': results[4] if not isinstance(results[4], Exception) else {'error': str(results[4])},
            'shell_company_analysis': results[5] if not isinstance(results[5], Exception) else {'error': str(results[5])},
            'overall_risk_assessment': {},
            'recommendations': []
        }

        # Calculate overall risk
        risks = []

        # Shell company risk
        if not isinstance(results[5], Exception):
            shell_risk = results[5].get('risk_level', 'unknown')
            risks.append(('shell_company', shell_risk))

        # Political connection risk
        if not isinstance(results[3], Exception):
            pol_risk = results[3].get('risk_level', 'low')
            risks.append(('political_exposure', pol_risk))

        # Financial risk
        if not isinstance(results[4], Exception):
            fin_health = results[4].get('financial_health_score', 'unknown')
            if fin_health == 'critical':
                risks.append(('financial', 'critical'))
            elif fin_health == 'poor':
                risks.append(('financial', 'high'))
            elif fin_health == 'concerning':
                risks.append(('financial', 'medium'))
            else:
                risks.append(('financial', 'low'))

        # Related company risk (bid rigging)
        if not isinstance(results[2], Exception):
            bid_risk = results[2].get('risk_assessment', {}).get('bid_rigging_risk', 'low')
            risks.append(('bid_rigging', bid_risk))

        report['overall_risk_assessment'] = dict(risks)

        # Calculate overall score
        risk_scores = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1, 'minimal': 0, 'unknown': 1}
        total_risk = sum(risk_scores.get(r[1], 1) for r in risks)

        if total_risk >= 10:
            report['overall_risk_level'] = 'CRITICAL'
        elif total_risk >= 7:
            report['overall_risk_level'] = 'HIGH'
        elif total_risk >= 4:
            report['overall_risk_level'] = 'MEDIUM'
        else:
            report['overall_risk_level'] = 'LOW'

        # Generate recommendations
        if report['overall_risk_level'] in ['CRITICAL', 'HIGH']:
            report['recommendations'].append('Detailed due diligence required before engagement')
            report['recommendations'].append('Verify ownership through official CRM documents')
            report['recommendations'].append('Check for recent changes in ownership/management')

        if not isinstance(results[3], Exception) and results[3].get('political_connections'):
            report['recommendations'].append('Assess potential conflict of interest with political connections')

        if not isinstance(results[2], Exception):
            if len(results[2].get('same_owner', [])) > 0:
                report['recommendations'].append('Check if related companies are bidding on same tenders')

        logger.info(f"Investigation complete. Overall risk: {report['overall_risk_level']}")
        return report


# CLI interface
async def main():
    """CLI interface for company research"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python company_research_agent.py <company_name>")
        print("\nExamples:")
        print('  python company_research_agent.py "Компанија ДОО"')
        print('  python company_research_agent.py "Company Name" --full')
        return

    company_name = sys.argv[1]
    full_investigation = '--full' in sys.argv

    async with CompanyResearchAgent() as agent:
        if full_investigation:
            print(f"\n{'='*60}")
            print(f"FULL INVESTIGATION: {company_name}")
            print(f"{'='*60}\n")

            report = await agent.full_company_investigation(company_name)
            print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        else:
            print(f"\n{'='*60}")
            print(f"COMPANY PROFILE: {company_name}")
            print(f"{'='*60}\n")

            profile = await agent.get_company_profile(company_name)
            print(json.dumps(profile, indent=2, ensure_ascii=False, default=str))

            print(f"\n{'='*60}")
            print(f"OWNERSHIP STRUCTURE")
            print(f"{'='*60}\n")

            ownership = await agent.get_ownership(company_name)
            print(json.dumps(ownership, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())
