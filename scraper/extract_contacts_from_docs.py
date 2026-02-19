#!/usr/bin/env python3
"""
Extract contact information from existing document content and populate contacts table.

This script:
1. Reads document content_text from documents table
2. Extracts emails and company names
3. Populates the contacts table with extracted data
4. Links contacts to tenders for source tracking

Usage:
    python extract_contacts_from_docs.py
    python extract_contacts_from_docs.py --reprocess  # Re-extract from all documents
"""

import asyncio
import argparse
import logging
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import asyncpg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Database URL
DATABASE_URL = os.getenv('DATABASE_URL')


class ContactExtractor:
    """Extract contact information from text"""

    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    PHONE_PATTERNS = [
        r'\+389\s*\d{2}\s*\d{3}\s*\d{3}',
        r'0\d{2}[\s\-]?\d{3}[\s\-]?\d{3}',
        r'\d{3}[\s\-]?\d{3}[\s\-]?\d{3}',
    ]

    # Company legal forms
    LEGAL_FORMS = ['ДООЕЛ', 'ДОО', 'АД', 'ДПТУ', 'ООД', 'LLC', 'Ltd', 'Inc', 'Corp']

    @classmethod
    def extract_emails(cls, text: str) -> List[str]:
        """Extract unique valid email addresses"""
        if not text:
            return []

        emails = set()
        matches = re.findall(cls.EMAIL_PATTERN, text, re.IGNORECASE)

        for email in matches:
            email = email.lower().strip()
            if cls._validate_email(email):
                emails.add(email)

        return sorted(list(emails))

    @classmethod
    def _validate_email(cls, email: str) -> bool:
        """Validate email address"""
        invalid_domains = ['example.com', 'test.com', 'localhost', 'domain.com']
        if any(domain in email for domain in invalid_domains):
            return False

        invalid_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.pdf', '.doc']
        if any(email.endswith(ext) for ext in invalid_extensions):
            return False

        tld = email.split('.')[-1]
        if len(tld) < 2 or len(tld) > 10:
            return False

        return True

    @classmethod
    def extract_phones(cls, text: str) -> List[str]:
        """Extract unique phone numbers"""
        if not text:
            return []

        phones = set()
        for pattern in cls.PHONE_PATTERNS:
            matches = re.findall(pattern, text)
            for phone in matches:
                phone = re.sub(r'[\s\-\(\)]', '', phone)
                digits = re.sub(r'\D', '', phone)
                if 7 <= len(digits) <= 15:
                    phones.add(phone)

        return sorted(list(phones))

    @classmethod
    def extract_companies(cls, text: str) -> List[str]:
        """Extract company names from text"""
        if not text:
            return []

        companies = set()

        # Pattern for Macedonian company names with legal form
        patterns = [
            # Full company name patterns
            r'([А-ЯЃЌЉЊЏШЧЖа-яѓќљњџшчж][А-ЯЃЌЉЊЏШЧЖа-яѓќљњџшчж\s\-\.]{5,80}(?:ДООЕЛ|ДОО|АД|ДПТУ|ООД))',
            r'(Друштво[^,\n]{10,100}(?:ДООЕЛ|ДОО|АД|ДПТУ|ООД)[^,\n]{0,50})',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.UNICODE)
            for match in matches:
                company = cls._clean_company_name(match)
                if cls._validate_company_name(company):
                    companies.add(company)

        return sorted(list(companies))

    @classmethod
    def _clean_company_name(cls, name: str) -> str:
        """Clean company name"""
        name = re.sub(r'\s+', ' ', name)
        name = name.strip('.-,; ')
        return name

    @classmethod
    def _validate_company_name(cls, name: str) -> bool:
        """Validate company name"""
        if len(name) < 10 or len(name) > 300:
            return False

        if not any(form in name for form in cls.LEGAL_FORMS):
            return False

        return True


async def extract_contacts_from_documents():
    """Main extraction function"""

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Get all documents with content
        logger.info("Fetching documents with extracted content...")

        docs = await conn.fetch("""
            SELECT d.doc_id, d.tender_id, d.doc_type, d.content_text,
                   t.procuring_entity, t.source_url
            FROM documents d
            JOIN tenders t ON t.tender_id = d.tender_id
            WHERE d.content_text IS NOT NULL
              AND d.content_text != ''
        """)

        logger.info(f"Found {len(docs)} documents with content")

        total_emails = 0
        total_companies = 0
        contacts_inserted = 0

        for doc in docs:
            doc_id = doc['doc_id']
            tender_id = doc['tender_id']
            content = doc['content_text']
            procuring_entity = doc['procuring_entity']
            source_url = doc['source_url']

            # Extract contacts
            emails = ContactExtractor.extract_emails(content)
            phones = ContactExtractor.extract_phones(content)
            companies = ContactExtractor.extract_companies(content)

            logger.info(f"Doc {tender_id}: {len(emails)} emails, {len(phones)} phones, {len(companies)} companies")

            total_emails += len(emails)
            total_companies += len(companies)

            # Insert companies as bidder/winner contacts
            for company in companies:
                # Try to find associated email/phone in the text near company name
                company_email = None
                company_phone = None

                # Look for email near company name in text
                company_pos = content.find(company)
                if company_pos >= 0:
                    # Look in surrounding text (500 chars before/after)
                    start = max(0, company_pos - 500)
                    end = min(len(content), company_pos + len(company) + 500)
                    nearby_text = content[start:end]

                    nearby_emails = ContactExtractor.extract_emails(nearby_text)
                    nearby_phones = ContactExtractor.extract_phones(nearby_text)

                    if nearby_emails:
                        company_email = nearby_emails[0]
                    if nearby_phones:
                        company_phone = nearby_phones[0]

                # Insert into contacts table
                try:
                    await conn.execute("""
                        INSERT INTO contacts (
                            contact_type, entity_name, entity_type,
                            email, phone, source_tender_id, source_url
                        )
                        VALUES ('bidder', $1, 'company', $2, $3, $4, $5)
                        ON CONFLICT (email) WHERE email IS NOT NULL AND email != ''
                        DO UPDATE SET
                            entity_name = EXCLUDED.entity_name,
                            phone = COALESCE(EXCLUDED.phone, contacts.phone),
                            updated_at = NOW()
                    """, company, company_email, company_phone, tender_id, source_url)
                    contacts_inserted += 1
                except Exception as e:
                    # If no email, insert with unique entity name
                    if company_email is None:
                        try:
                            # Check if already exists
                            existing = await conn.fetchval("""
                                SELECT contact_id FROM contacts
                                WHERE entity_name = $1 AND contact_type = 'bidder'
                            """, company)

                            if not existing:
                                await conn.execute("""
                                    INSERT INTO contacts (
                                        contact_type, entity_name, entity_type,
                                        phone, source_tender_id, source_url
                                    )
                                    VALUES ('bidder', $1, 'company', $2, $3, $4)
                                """, company, company_phone, tender_id, source_url)
                                contacts_inserted += 1
                        except Exception as e2:
                            logger.debug(f"Skip duplicate: {company[:50]}")

            # Insert standalone emails (not matched to companies) as unknown contacts
            for email in emails:
                # Skip if we already used this email for a company
                existing = await conn.fetchval("""
                    SELECT contact_id FROM contacts WHERE email = $1
                """, email)

                if not existing:
                    try:
                        await conn.execute("""
                            INSERT INTO contacts (
                                contact_type, entity_name, entity_type,
                                email, source_tender_id, source_url
                            )
                            VALUES ('bidder', $1, 'company', $1, $2, $3)
                            ON CONFLICT (email) WHERE email IS NOT NULL AND email != ''
                            DO NOTHING
                        """, email, tender_id, source_url)
                        contacts_inserted += 1
                    except Exception as e:
                        logger.debug(f"Skip email: {email}")

        # Get final counts
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE email IS NOT NULL AND email != '') as with_email,
                COUNT(*) FILTER (WHERE contact_type = 'procuring_entity') as procuring,
                COUNT(*) FILTER (WHERE contact_type IN ('winner', 'bidder')) as bidders
            FROM contacts
        """)

        logger.info("=" * 60)
        logger.info("EXTRACTION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Documents processed: {len(docs)}")
        logger.info(f"Emails found in docs: {total_emails}")
        logger.info(f"Companies found in docs: {total_companies}")
        logger.info(f"Contacts inserted/updated: {contacts_inserted}")
        logger.info("")
        logger.info("CONTACTS TABLE SUMMARY:")
        logger.info(f"  Total contacts: {stats['total']}")
        logger.info(f"  With email: {stats['with_email']}")
        logger.info(f"  Procuring entities: {stats['procuring']}")
        logger.info(f"  Bidders/Winners: {stats['bidders']}")

    finally:
        await conn.close()


async def show_contacts_summary():
    """Show current contacts summary"""
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Summary
        summary = await conn.fetch("""
            SELECT contact_type, COUNT(*) as count,
                   COUNT(*) FILTER (WHERE email IS NOT NULL AND email != '') as with_email
            FROM contacts
            GROUP BY contact_type
            ORDER BY contact_type
        """)

        print("\n" + "=" * 60)
        print("CONTACTS SUMMARY")
        print("=" * 60)
        for row in summary:
            print(f"  {row['contact_type']}: {row['count']} total, {row['with_email']} with email")

        # Sample contacts with emails
        samples = await conn.fetch("""
            SELECT contact_type, entity_name, email, phone
            FROM contacts
            WHERE email IS NOT NULL AND email != ''
            ORDER BY contact_type, entity_name
            LIMIT 20
        """)

        print("\nSAMPLE CONTACTS WITH EMAIL:")
        for row in samples:
            print(f"  [{row['contact_type']}] {row['entity_name'][:50]}")
            print(f"      Email: {row['email']}")
            if row['phone']:
                print(f"      Phone: {row['phone']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract contacts from documents')
    parser.add_argument('--summary', action='store_true', help='Show contacts summary only')

    args = parser.parse_args()

    if args.summary:
        asyncio.run(show_contacts_summary())
    else:
        asyncio.run(extract_contacts_from_documents())
        asyncio.run(show_contacts_summary())
