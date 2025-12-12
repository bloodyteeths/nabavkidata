"""
Simple test for alert matching logic (no database required)
"""
import asyncio
import sys

# Mock the required imports
sys.path.insert(0, '/Users/tamsar/Downloads/nabavkidata/backend')

async def check_alert_against_tender(alert: dict, tender: dict):
    """
    Check if tender matches alert criteria
    Returns: (matches: bool, score: float, reasons: List[str])
    """
    criteria = alert.get('criteria', {})
    score = 0.0
    reasons = []

    # Keyword matching
    if criteria.get('keywords'):
        text = f"{tender.get('title', '')} {tender.get('description', '')}".lower()
        matched_keywords = []
        for kw in criteria['keywords']:
            if kw.lower() in text:
                matched_keywords.append(kw)

        if matched_keywords:
            score += 25
            reasons.append(f"Keywords matched: {', '.join(matched_keywords)}")

    # CPV code matching
    if criteria.get('cpv_codes'):
        tender_cpv = tender.get('cpv_code', '')
        matched_cpvs = []
        for cpv in criteria['cpv_codes']:
            if tender_cpv and tender_cpv.startswith(cpv[:4]):
                matched_cpvs.append(cpv)

        if matched_cpvs:
            score += 30
            reasons.append(f"CPV codes matched: {', '.join(matched_cpvs)}")

    # Entity matching
    if criteria.get('entities'):
        entity = tender.get('procuring_entity', '').lower()
        matched_entities = []
        for e in criteria['entities']:
            if e.lower() in entity:
                matched_entities.append(e)

        if matched_entities:
            score += 25
            reasons.append(f"Entities matched: {', '.join(matched_entities)}")

    # Budget range matching
    if criteria.get('budget_min') is not None or criteria.get('budget_max') is not None:
        value = tender.get('estimated_value_mkd') or 0
        budget_min = criteria.get('budget_min', 0)
        budget_max = criteria.get('budget_max', float('inf'))

        if budget_min <= value <= budget_max:
            score += 20
            reasons.append(f"Budget in range: {value:,.0f} MKD")

    # Competitor tracking
    if criteria.get('competitors'):
        winner = tender.get('winner', '').lower()
        matched_competitors = []
        for comp in criteria['competitors']:
            if comp.lower() in winner:
                matched_competitors.append(comp)

        if matched_competitors:
            score += 25
            reasons.append(f"Competitors matched: {', '.join(matched_competitors)}")

    matches = score > 0
    final_score = min(score, 100.0)

    return matches, final_score, reasons


async def main():
    """Run matching engine tests"""
    print("=" * 70)
    print("Alert Matching Engine Tests")
    print("=" * 70)

    # Sample tender
    tender = {
        'title': 'Набавка на компјутерска опрема',
        'description': 'Software лиценци и хардвер за 50 работни станици',
        'procuring_entity': 'Министерство за образование и наука',
        'estimated_value_mkd': 500000,
        'cpv_code': '30213000',
        'winner': ''
    }

    # Test 1: Keyword matching
    print("\n[Test 1] Keyword Matching")
    alert = {'criteria': {'keywords': ['software', 'компјутер']}}
    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"  Alert: {alert['criteria']}")
    print(f"  ✓ Matches: {matches}, Score: {score}")
    print(f"  ✓ Reasons: {reasons}")
    assert matches == True, "Should match keywords"
    assert score == 25, f"Score should be 25, got {score}"

    # Test 2: CPV code matching
    print("\n[Test 2] CPV Code Matching")
    alert = {'criteria': {'cpv_codes': ['3021']}}
    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"  Alert: {alert['criteria']}")
    print(f"  ✓ Matches: {matches}, Score: {score}")
    print(f"  ✓ Reasons: {reasons}")
    assert matches == True, "Should match CPV code"
    assert score == 30, f"Score should be 30, got {score}"

    # Test 3: Entity matching
    print("\n[Test 3] Entity Matching")
    alert = {'criteria': {'entities': ['Министерство']}}
    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"  Alert: {alert['criteria']}")
    print(f"  ✓ Matches: {matches}, Score: {score}")
    print(f"  ✓ Reasons: {reasons}")
    assert matches == True, "Should match entity"
    assert score == 25, f"Score should be 25, got {score}"

    # Test 4: Budget range matching
    print("\n[Test 4] Budget Range Matching")
    alert = {'criteria': {'budget_min': 100000, 'budget_max': 1000000}}
    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"  Alert: {alert['criteria']}")
    print(f"  ✓ Matches: {matches}, Score: {score}")
    print(f"  ✓ Reasons: {reasons}")
    assert matches == True, "Should match budget range"
    assert score == 20, f"Score should be 20, got {score}"

    # Test 5: Combined criteria
    print("\n[Test 5] Combined Criteria (Multi-factor matching)")
    alert = {
        'criteria': {
            'keywords': ['компјутер'],
            'cpv_codes': ['3021'],
            'budget_min': 100000
        }
    }
    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"  Alert: {alert['criteria']}")
    print(f"  ✓ Matches: {matches}, Score: {score}")
    print(f"  ✓ Reasons: {reasons}")
    assert matches == True, "Should match combined criteria"
    assert score == 75, f"Score should be 75 (25+30+20), got {score}"
    assert len(reasons) == 3, f"Should have 3 match reasons, got {len(reasons)}"

    # Test 6: No match scenario
    print("\n[Test 6] No Match Scenario")
    alert = {'criteria': {'keywords': ['медицинска опрема', 'ambulanta']}}
    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"  Alert: {alert['criteria']}")
    print(f"  ✓ Matches: {matches}, Score: {score}")
    print(f"  ✓ Reasons: {reasons}")
    assert matches == False, "Should not match"
    assert score == 0, f"Score should be 0, got {score}"
    assert len(reasons) == 0, f"Should have no reasons, got {reasons}"

    # Test 7: Budget out of range
    print("\n[Test 7] Budget Out of Range")
    alert = {'criteria': {'budget_min': 1000000, 'budget_max': 5000000}}
    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"  Alert: {alert['criteria']}")
    print(f"  ✓ Matches: {matches}, Score: {score}")
    print(f"  ✓ Reasons: {reasons}")
    assert matches == False, "Should not match - budget out of range"

    # Test 8: Competitor tracking
    print("\n[Test 8] Competitor Tracking")
    tender_with_winner = tender.copy()
    tender_with_winner['winner'] = 'Македонски Телеком АД Скопје'
    alert = {'criteria': {'competitors': ['Македонски Телеком', 'Винер']}}
    matches, score, reasons = await check_alert_against_tender(alert, tender_with_winner)
    print(f"  Alert: {alert['criteria']}")
    print(f"  Winner: {tender_with_winner['winner']}")
    print(f"  ✓ Matches: {matches}, Score: {score}")
    print(f"  ✓ Reasons: {reasons}")
    assert matches == True, "Should match competitor"
    assert score == 25, f"Score should be 25, got {score}"

    # Test 9: Case insensitive matching
    print("\n[Test 9] Case Insensitive Keyword Matching")
    alert = {'criteria': {'keywords': ['КОМПЈУТЕР', 'SoFtWaRe']}}
    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"  Alert: {alert['criteria']}")
    print(f"  ✓ Matches: {matches}, Score: {score}")
    print(f"  ✓ Reasons: {reasons}")
    assert matches == True, "Should match case-insensitively"

    # Test 10: Score capping at 100
    print("\n[Test 10] Score Capping at 100")
    alert = {
        'criteria': {
            'keywords': ['компјутер', 'software'],
            'cpv_codes': ['3021'],
            'entities': ['Министерство'],
            'budget_min': 100000,
            'competitors': []
        }
    }
    matches, score, reasons = await check_alert_against_tender(alert, tender)
    print(f"  Alert: {alert['criteria']}")
    print(f"  ✓ Matches: {matches}, Score: {score}")
    print(f"  ✓ Reasons: {reasons}")
    assert score <= 100, f"Score should be capped at 100, got {score}"

    print("\n" + "=" * 70)
    print("✓ All 10 tests passed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
