#!/usr/bin/env python3
"""
Cross-reference known corruption cases against the tender database.

This script searches for matching tenders based on:
- Institution names (Cyrillic and Latin)
- Company names
- Year ranges
- Keywords from case descriptions
"""

import asyncio
import asyncpg
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import json
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from backend.utils.transliteration import latin_to_cyrillic, get_search_variants

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")


@dataclass
class MatchResult:
    """Result of matching a corruption case to tenders."""
    case_id: str
    case_name: str
    tender_id: str
    tender_title: str
    procuring_entity: str
    winner: Optional[str]
    estimated_value_mkd: Optional[float]
    publication_date: Optional[str]
    match_confidence: str  # exact, partial, possible
    match_reasons: List[str]
    has_corruption_flags: bool
    anomaly_score: Optional[float]


# Define search criteria for each case
CASE_SEARCH_CRITERIA = {
    "MK-2023-001": {
        "name": "Tank Case (Mercedes)",
        "institution_keywords": [
            "Министерство за внатрешни работи",
            "МВР", "MVR",
            "Ministry of Internal Affairs",
            "внатрешни работи"
        ],
        "product_keywords": [
            "возило", "vehicle", "мерцедес", "mercedes", "оклопено",
            "armored", "S-600", "Guard", "луксузен"
        ],
        "year_range": (2011, 2013),
        "min_value_eur": 400000,
        "max_value_eur": 800000,
    },
    "MK-2021-001": {
        "name": "Software Case (Biometric)",
        "institution_keywords": [
            "Генерален секретаријат",
            "General Secretariat",
            "Влада", "Government"
        ],
        "product_keywords": [
            "биометрија", "biometric", "софтвер", "software",
            "идентификација", "identification", "следење", "surveillance"
        ],
        "company_keywords": ["Gamma", "Finzi"],
        "year_range": (2015, 2018),
    },
    "MK-2021-002": {
        "name": "Trezor Case (Surveillance)",
        "institution_keywords": [
            "УБК", "UBK",
            "безбедност", "контраразузнавање",
            "Administration for Security"
        ],
        "product_keywords": [
            "прислушување", "surveillance", "опрема", "equipment",
            "телекомуникација", "telecommunication"
        ],
        "company_keywords": ["Gamma", "Finzi"],
        "year_range": (2010, 2014),
    },
    "MK-2021-003": {
        "name": "Target-Tvrdina (Mass Surveillance)",
        "institution_keywords": [
            "УБК", "UBK",
            "безбедност", "контраразузнавање"
        ],
        "product_keywords": [
            "прислушување", "surveillance", "мониторинг", "monitoring"
        ],
        "year_range": (2008, 2015),
    },
    "MK-2023-002": {
        "name": "Zekiri Consulting",
        "institution_keywords": [
            "Влада", "Government",
            "Генерален секретаријат",
            "General Secretariat"
        ],
        "product_keywords": [
            "консултантски", "consulting", "железници", "railway",
            "приватизација", "privatization"
        ],
        "company_keywords": ["хрватска", "croatia", "croatian"],
        "year_range": (2020, 2022),
        "min_value_eur": 500000,
    },
    "MK-2022-001": {
        "name": "Kamcev Land Parcels",
        "institution_keywords": [],  # No specific institution
        "product_keywords": [
            "земјиште", "land", "плацеви", "parcels",
            "Водно", "Vodno"
        ],
        "company_keywords": ["Орка", "Orka", "Камчев", "Kamcev"],
        "year_range": (2018, 2022),
    },
    "MK-2025-001": {
        "name": "ESM District Heating",
        "institution_keywords": [
            "ЕСМ", "ESM",
            "Дистрибуција на топлина",
            "District Heating",
            "топлинска"
        ],
        "product_keywords": [
            "SCADA", "СКАД", "кабинети", "cabinets",
            "GSM", "контролери", "controllers",
            "топлински", "heating"
        ],
        "year_range": (2022, 2024),
        "min_value_eur": 5000000,
    },
    "MK-2024-001": {
        "name": "TEC Negotino Fuel Oil",
        "institution_keywords": [
            "ТЕЦ Неготино", "TEC Negotino",
            "Електрани", "ESM",
            "Електрани на Северна Македонија"
        ],
        "product_keywords": [
            "мазут", "mazut", "fuel oil",
            "гориво", "fuel", "нафта", "oil"
        ],
        "company_keywords": ["RKM", "РКМ", "Pucko", "Пучко"],
        "year_range": (2020, 2024),
        "min_value_eur": 1000000,
    },
    "MK-2024-002": {
        "name": "State Lottery",
        "institution_keywords": [
            "Државна лотарија",
            "State Lottery",
            "лотарија"
        ],
        "product_keywords": [
            "канцелариски простор", "office space",
            "опрема", "equipment", "TV", "телевизор",
            "компјутер", "computer"
        ],
        "company_keywords": ["HEJ"],
        "year_range": (2021, 2024),
    },
    "MK-2024-003": {
        "name": "SOZR Tender Fraud",
        "institution_keywords": [
            "СОЗР", "SOZR",
            "Служба за општи и заеднички работи",
            "општи и заеднички"
        ],
        "product_keywords": [
            "превоз", "transportation", "возило", "vehicle"
        ],
        "year_range": (2021, 2024),
    },
    "MK-2016-001": {
        "name": "Trajectory (Sinohydro Highway)",
        "institution_keywords": [
            "државни патишта",
            "State Roads",
            "ЈПДП", "патишта"
        ],
        "product_keywords": [
            "автопат", "highway", "патишта", "roads",
            "Милaдиновци", "Штип", "Кичево", "Охрид"
        ],
        "company_keywords": ["Sinohydro", "Синохидро", "кинеска"],
        "year_range": (2010, 2016),
        "min_value_eur": 100000000,
    },
}


async def search_tenders_for_case(conn: asyncpg.Connection, case_id: str, criteria: dict) -> List[MatchResult]:
    """Search for tenders matching the given case criteria."""
    matches = []

    # Build search conditions
    conditions = []
    params = []
    param_count = 0

    # Year range filter
    year_start, year_end = criteria.get("year_range", (2008, 2025))

    # Search by institution keywords
    institution_keywords = criteria.get("institution_keywords", [])
    if institution_keywords:
        institution_conditions = []
        for keyword in institution_keywords:
            variants = get_search_variants(keyword)
            for variant in variants:
                param_count += 1
                institution_conditions.append(f"procuring_entity ILIKE ${param_count}")
                params.append(f"%{variant}%")
        if institution_conditions:
            conditions.append(f"({' OR '.join(institution_conditions)})")

    # Search by product keywords in title
    product_keywords = criteria.get("product_keywords", [])
    if product_keywords:
        product_conditions = []
        for keyword in product_keywords:
            variants = get_search_variants(keyword)
            for variant in variants:
                param_count += 1
                product_conditions.append(f"title ILIKE ${param_count}")
                params.append(f"%{variant}%")
        if product_conditions:
            conditions.append(f"({' OR '.join(product_conditions)})")

    # Search by company keywords in winner
    company_keywords = criteria.get("company_keywords", [])
    winner_conditions = []
    if company_keywords:
        for keyword in company_keywords:
            variants = get_search_variants(keyword)
            for variant in variants:
                param_count += 1
                winner_conditions.append(f"winner ILIKE ${param_count}")
                params.append(f"%{variant}%")

    # Build the query
    if not conditions:
        # If no institution or product keywords, search by company only
        if winner_conditions:
            conditions = [f"({' OR '.join(winner_conditions)})"]
        else:
            return []  # No search criteria

    # Add year filter based on tender_id pattern
    year_condition = f"(SUBSTRING(tender_id FROM '[0-9]+/([0-9]+)')::int BETWEEN {year_start} AND {year_end})"

    # Value filter if specified
    value_conditions = []
    min_value_eur = criteria.get("min_value_eur")
    max_value_eur = criteria.get("max_value_eur")

    if min_value_eur:
        min_value_mkd = min_value_eur * 61.5  # Approximate EUR to MKD rate
        value_conditions.append(f"estimated_value_mkd >= {min_value_mkd}")
    if max_value_eur:
        max_value_mkd = max_value_eur * 61.5
        value_conditions.append(f"estimated_value_mkd <= {max_value_mkd}")

    where_clause = " AND ".join(conditions)
    if winner_conditions:
        where_clause = f"(({where_clause}) OR ({' OR '.join(winner_conditions)}))"

    where_clause += f" AND {year_condition}"

    if value_conditions:
        where_clause += f" AND ({' AND '.join(value_conditions)})"

    query = f"""
        SELECT
            tender_id,
            title,
            procuring_entity,
            winner,
            estimated_value_mkd,
            publication_date
        FROM tenders
        WHERE {where_clause}
        ORDER BY estimated_value_mkd DESC NULLS LAST
        LIMIT 50
    """

    try:
        rows = await conn.fetch(query, *params)

        for row in rows:
            # Determine match confidence
            match_reasons = []
            confidence_score = 0

            # Check institution match
            entity = (row['procuring_entity'] or '').lower()
            for keyword in institution_keywords:
                for variant in get_search_variants(keyword):
                    if variant.lower() in entity:
                        match_reasons.append(f"Institution: {keyword}")
                        confidence_score += 2
                        break

            # Check product match
            title = (row['title'] or '').lower()
            for keyword in product_keywords:
                for variant in get_search_variants(keyword):
                    if variant.lower() in title:
                        match_reasons.append(f"Product: {keyword}")
                        confidence_score += 1
                        break

            # Check company match
            winner = (row['winner'] or '').lower()
            for keyword in company_keywords:
                for variant in get_search_variants(keyword):
                    if variant.lower() in winner:
                        match_reasons.append(f"Company: {keyword}")
                        confidence_score += 3
                        break

            # Determine confidence level
            if confidence_score >= 5:
                confidence = "exact"
            elif confidence_score >= 3:
                confidence = "partial"
            else:
                confidence = "possible"

            # Corruption flags not yet implemented
            has_flags = False
            anomaly_score = None

            matches.append(MatchResult(
                case_id=case_id,
                case_name=criteria['name'],
                tender_id=row['tender_id'],
                tender_title=row['title'] or '',
                procuring_entity=row['procuring_entity'] or '',
                winner=row['winner'],
                estimated_value_mkd=float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                publication_date=str(row['publication_date']) if row['publication_date'] else None,
                match_confidence=confidence,
                match_reasons=match_reasons,
                has_corruption_flags=has_flags,
                anomaly_score=anomaly_score
            ))
    except Exception as e:
        print(f"Error searching for case {case_id}: {e}")

    return matches


async def get_database_stats(conn: asyncpg.Connection) -> Dict[str, Any]:
    """Get database statistics for the report."""
    stats = {}

    # Total tenders
    row = await conn.fetchrow("SELECT COUNT(*) as total FROM tenders")
    stats['total_tenders'] = row['total']

    # Tenders by year
    rows = await conn.fetch("""
        SELECT
            SUBSTRING(tender_id FROM '[0-9]+/([0-9]+)') as year,
            COUNT(*) as count
        FROM tenders
        GROUP BY year
        ORDER BY year DESC
    """)
    stats['tenders_by_year'] = {row['year']: row['count'] for row in rows if row['year']}

    # Note: corruption_flags column may not exist yet
    stats['flagged_tenders'] = 0

    return stats


async def main():
    """Main function to cross-reference cases with database."""
    print("=" * 70)
    print("CROSS-REFERENCING CORRUPTION CASES WITH TENDER DATABASE")
    print("=" * 70)
    print(f"\nStarted at: {datetime.now().isoformat()}")

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)
    print("\nConnected to database.")

    # Get database stats
    stats = await get_database_stats(conn)
    print(f"\nDatabase Statistics:")
    print(f"  Total tenders: {stats['total_tenders']:,}")
    print(f"  Flagged tenders: {stats['flagged_tenders']:,}")
    print(f"\n  Tenders by year (recent):")
    for year in sorted(stats['tenders_by_year'].keys(), reverse=True)[:10]:
        print(f"    {year}: {stats['tenders_by_year'][year]:,}")

    # Process each case
    all_matches = []
    case_summary = []

    print("\n" + "=" * 70)
    print("SEARCHING FOR MATCHING TENDERS")
    print("=" * 70)

    for case_id, criteria in CASE_SEARCH_CRITERIA.items():
        print(f"\n[{case_id}] {criteria['name']}")
        print(f"  Years: {criteria.get('year_range', 'any')}")
        print(f"  Institution keywords: {len(criteria.get('institution_keywords', []))}")
        print(f"  Product keywords: {len(criteria.get('product_keywords', []))}")
        print(f"  Company keywords: {len(criteria.get('company_keywords', []))}")

        matches = await search_tenders_for_case(conn, case_id, criteria)

        # Filter and sort by confidence
        exact_matches = [m for m in matches if m.match_confidence == "exact"]
        partial_matches = [m for m in matches if m.match_confidence == "partial"]
        possible_matches = [m for m in matches if m.match_confidence == "possible"]

        print(f"  Results: {len(exact_matches)} exact, {len(partial_matches)} partial, {len(possible_matches)} possible")

        # Show top matches
        top_matches = sorted(matches, key=lambda m: (
            0 if m.match_confidence == "exact" else (1 if m.match_confidence == "partial" else 2),
            -(m.estimated_value_mkd or 0)
        ))[:5]

        for m in top_matches:
            value_eur = m.estimated_value_mkd / 61.5 if m.estimated_value_mkd else 0
            print(f"    [{m.match_confidence.upper()}] {m.tender_id}: {m.tender_title[:60]}...")
            print(f"           Entity: {m.procuring_entity[:50]}...")
            print(f"           Value: EUR {value_eur:,.0f}")
            print(f"           Reasons: {', '.join(m.match_reasons)}")

        all_matches.extend(matches)

        case_summary.append({
            'case_id': case_id,
            'case_name': criteria['name'],
            'exact': len(exact_matches),
            'partial': len(partial_matches),
            'possible': len(possible_matches),
            'top_tender_ids': [m.tender_id for m in top_matches[:3]]
        })

    # Generate report
    print("\n" + "=" * 70)
    print("GENERATING REPORT")
    print("=" * 70)

    report = generate_report(all_matches, case_summary, stats)

    # Save report
    report_path = os.path.join(os.path.dirname(__file__), 'case_matching_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\nReport saved to: {report_path}")

    # Save tender IDs mapping for updating known_cases.py
    tender_ids_mapping = {}
    for summary in case_summary:
        if summary['top_tender_ids']:
            tender_ids_mapping[summary['case_id']] = summary['top_tender_ids']

    mapping_path = os.path.join(os.path.dirname(__file__), 'tender_ids_mapping.json')
    with open(mapping_path, 'w', encoding='utf-8') as f:
        json.dump(tender_ids_mapping, f, indent=2, ensure_ascii=False)
    print(f"Tender IDs mapping saved to: {mapping_path}")

    await conn.close()

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_exact = sum(s['exact'] for s in case_summary)
    total_partial = sum(s['partial'] for s in case_summary)
    cases_with_matches = sum(1 for s in case_summary if s['exact'] > 0 or s['partial'] > 0)

    print(f"\nTotal cases: {len(case_summary)}")
    print(f"Cases with matches: {cases_with_matches}")
    print(f"Total exact matches: {total_exact}")
    print(f"Total partial matches: {total_partial}")

    print("\nCases with matches:")
    for s in case_summary:
        if s['exact'] > 0 or s['partial'] > 0:
            print(f"  {s['case_id']}: {s['case_name']}")
            print(f"    {s['exact']} exact, {s['partial']} partial")
            if s['top_tender_ids']:
                print(f"    Top: {', '.join(s['top_tender_ids'][:3])}")

    print("\nCases without matches:")
    for s in case_summary:
        if s['exact'] == 0 and s['partial'] == 0:
            print(f"  {s['case_id']}: {s['case_name']}")

    return case_summary, tender_ids_mapping


def generate_report(all_matches: List[MatchResult], case_summary: List[dict], stats: Dict[str, Any]) -> str:
    """Generate the markdown report."""
    report = []

    report.append("# Corruption Case to Tender Matching Report")
    report.append(f"\nGenerated: {datetime.now().isoformat()}")
    report.append("")

    report.append("## Database Overview")
    report.append("")
    report.append(f"- **Total tenders in database**: {stats['total_tenders']:,}")
    report.append(f"- **Tenders with corruption flags**: {stats['flagged_tenders']:,}")
    report.append("")
    report.append("### Tenders by Year")
    report.append("")
    report.append("| Year | Count |")
    report.append("|------|-------|")
    for year in sorted(stats['tenders_by_year'].keys(), reverse=True)[:15]:
        report.append(f"| {year} | {stats['tenders_by_year'][year]:,} |")
    report.append("")

    report.append("## Summary of Results")
    report.append("")

    total_exact = sum(s['exact'] for s in case_summary)
    total_partial = sum(s['partial'] for s in case_summary)
    cases_with_matches = sum(1 for s in case_summary if s['exact'] > 0 or s['partial'] > 0)

    report.append(f"- **Total cases analyzed**: {len(case_summary)}")
    report.append(f"- **Cases with exact/partial matches**: {cases_with_matches}")
    report.append(f"- **Total exact matches**: {total_exact}")
    report.append(f"- **Total partial matches**: {total_partial}")
    report.append("")

    report.append("### Match Confidence Levels")
    report.append("")
    report.append("- **Exact**: Multiple matching criteria (institution + product + company keywords)")
    report.append("- **Partial**: Some matching criteria (institution + product OR company)")
    report.append("- **Possible**: Single matching criterion")
    report.append("")

    report.append("## Case-by-Case Results")
    report.append("")

    for summary in case_summary:
        case_id = summary['case_id']
        report.append(f"### {case_id}: {summary['case_name']}")
        report.append("")
        report.append(f"- **Exact matches**: {summary['exact']}")
        report.append(f"- **Partial matches**: {summary['partial']}")
        report.append(f"- **Possible matches**: {summary['possible']}")
        report.append("")

        # Get matches for this case
        case_matches = [m for m in all_matches if m.case_id == case_id]
        top_matches = sorted(case_matches, key=lambda m: (
            0 if m.match_confidence == "exact" else (1 if m.match_confidence == "partial" else 2),
            -(m.estimated_value_mkd or 0)
        ))[:5]

        if top_matches:
            report.append("#### Top Matches")
            report.append("")
            report.append("| Tender ID | Title | Entity | Value (EUR) | Confidence | Reasons |")
            report.append("|-----------|-------|--------|-------------|------------|---------|")

            for m in top_matches:
                value_eur = m.estimated_value_mkd / 61.5 if m.estimated_value_mkd else 0
                title = m.tender_title[:40] + "..." if len(m.tender_title) > 40 else m.tender_title
                entity = m.procuring_entity[:30] + "..." if len(m.procuring_entity) > 30 else m.procuring_entity
                reasons = ", ".join(m.match_reasons[:2])
                report.append(f"| {m.tender_id} | {title} | {entity} | {value_eur:,.0f} | {m.match_confidence} | {reasons} |")
            report.append("")
        else:
            report.append("*No matches found in database*")
            report.append("")

        report.append("---")
        report.append("")

    report.append("## Cases Without Matches")
    report.append("")
    report.append("The following cases had no exact or partial matches in the database:")
    report.append("")

    no_matches = [s for s in case_summary if s['exact'] == 0 and s['partial'] == 0]
    if no_matches:
        for s in no_matches:
            report.append(f"- **{s['case_id']}**: {s['case_name']}")
    else:
        report.append("*All cases had at least one match*")
    report.append("")

    report.append("### Possible Reasons for Missing Matches")
    report.append("")
    report.append("1. **Tender predates database coverage** (2008-2024)")
    report.append("2. **Non-public procurement** (direct contracts, classified)")
    report.append("3. **Different naming conventions** (entity names changed)")
    report.append("4. **Tender not in e-nabavki system** (different platform)")
    report.append("")

    report.append("## Recommendations")
    report.append("")
    report.append("1. **Verify matches manually** - Review matched tenders to confirm they are the actual corruption cases")
    report.append("2. **Add tender_ids to known_cases.py** - Update the ground truth file with confirmed tender IDs")
    report.append("3. **Expand search criteria** - For cases with no matches, try alternative keywords or entity names")
    report.append("4. **Check archived records** - Some cases may be in archived/cancelled tenders")
    report.append("")

    return "\n".join(report)


if __name__ == "__main__":
    asyncio.run(main())
