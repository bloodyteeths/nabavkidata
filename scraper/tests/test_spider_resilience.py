"""
Test spider resilience mechanisms

Verifies that the spider can extract data from multiple HTML structures
"""
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapy.http import HtmlResponse, Request
from scraper.spiders.nabavki_spider import NabavkiSpider, FieldExtractor


def create_response(html, url="https://e-nabavki.gov.mk/tender/12345"):
    """Helper to create Scrapy response from HTML string"""
    request = Request(url=url)
    return HtmlResponse(
        url=url,
        request=request,
        body=html.encode('utf-8'),
        encoding='utf-8'
    )


def test_field_extractor_fallback_css():
    """Test CSS selector fallback chain"""
    print("\n" + "=" * 60)
    print("TEST: FieldExtractor - CSS Fallback")
    print("=" * 60)

    # HTML with title in h1 (second fallback)
    html = """
    <html>
        <body>
            <h1>Test Tender Title</h1>
        </body>
    </html>
    """
    response = create_response(html)

    selectors = [
        {'type': 'css', 'path': 'h1.tender-title::text'},  # Will fail
        {'type': 'css', 'path': 'h1::text'},                # Should succeed
    ]

    result = FieldExtractor.extract_with_fallbacks(response, 'title', selectors)

    assert result == "Test Tender Title", f"Expected 'Test Tender Title', got {result}"
    print("✓ CSS fallback succeeded (h1::text)")


def test_field_extractor_label_based():
    """Test label-based extraction (most resilient)"""
    print("\n" + "=" * 60)
    print("TEST: FieldExtractor - Label-Based Extraction")
    print("=" * 60)

    # HTML with label-value pattern (colon-based) - matches regex pattern
    html = """<html><body><div>Нарачател: Министерство за финансии</div></body></html>"""
    response = create_response(html)

    selectors = [
        {'type': 'css', 'path': 'div.entity::text'},        # Will fail
        {'type': 'label', 'label': 'Нарачател'},            # Should succeed
    ]

    result = FieldExtractor.extract_with_fallbacks(response, 'procuring_entity', selectors)

    assert result == "Министерство за финансии"
    print(f"✓ Label-based extraction succeeded: {result}")


def test_field_extractor_table_cells():
    """Test extraction from table cells"""
    print("\n" + "=" * 60)
    print("TEST: FieldExtractor - Table Cell Extraction")
    print("=" * 60)

    # HTML with table structure - with whitespace for regex matching
    html = """<html><body><table><tr><td>CPV</td> <td>48000000-8</td></tr></table></body></html>"""
    response = create_response(html)

    selectors = [
        {'type': 'css', 'path': 'span.cpv::text'},  # Will fail
        {'type': 'label', 'label': 'CPV'},          # Should succeed
    ]

    result = FieldExtractor.extract_with_fallbacks(response, 'cpv_code', selectors)

    assert result == "48000000-8"
    print(f"✓ Table cell extraction succeeded: {result}")


def test_spider_tender_id_from_url():
    """Test tender ID extraction from URL"""
    print("\n" + "=" * 60)
    print("TEST: Tender ID - URL Extraction")
    print("=" * 60)

    spider = NabavkiSpider()

    # Test various URL patterns
    test_cases = [
        ("https://e-nabavki.gov.mk/tender?id=ABC123", "ABC123"),
        ("https://e-nabavki.gov.mk/tender/XYZ789", "XYZ789"),
        ("https://e-nabavki.gov.mk/page?tenderid=TEST-2024", "TEST-2024"),
    ]

    for url, expected_id in test_cases:
        response = create_response("<html></html>", url=url)
        result = spider._extract_tender_id(response)
        assert result == expected_id, f"Expected {expected_id}, got {result}"
        print(f"✓ Extracted {result} from {url}")


def test_spider_category_detection():
    """Test content-based category classification"""
    print("\n" + "=" * 60)
    print("TEST: Category - Content-Based Classification")
    print("=" * 60)

    spider = NabavkiSpider()

    test_cases = [
        ("Набавка на компјутерска опрема", "IT Equipment"),
        ("Изградба на нов објект", "Construction"),
        ("Медицинска опрема за болница", "Medical"),
        ("Random tender without keywords", "Other"),
    ]

    for text, expected_category in test_cases:
        html = f"<html><body><p>{text}</p></body></html>"
        response = create_response(html)
        result = spider._extract_category(response)
        assert result == expected_category, f"Expected {expected_category}, got {result}"
        print(f"✓ Classified '{text[:30]}...' as {result}")


def test_spider_date_parsing():
    """Test multiple date format support"""
    print("\n" + "=" * 60)
    print("TEST: Date Parsing - Multiple Formats")
    print("=" * 60)

    spider = NabavkiSpider()

    test_cases = [
        ("25.11.2024", "2024-11-25"),
        ("25/11/2024", "2024-11-25"),
        ("2024-11-25", "2024-11-25"),
        ("25.11.24", "2024-11-25"),
    ]

    for input_date, expected in test_cases:
        result = spider._parse_date(input_date)
        assert str(result) == expected, f"Expected {expected}, got {result}"
        print(f"✓ Parsed '{input_date}' → {result}")


def test_spider_currency_parsing():
    """Test currency parsing with various formats"""
    print("\n" + "=" * 60)
    print("TEST: Currency Parsing - Various Formats")
    print("=" * 60)

    spider = NabavkiSpider()

    test_cases = [
        ("1.234.567,89 МКД", 1234567.89),   # European
        ("1,234,567.89 USD", 1234567.89),   # US
        ("1234567.89", 1234567.89),          # Plain
        ("€ 500.000,00", 500000.0),          # European with symbol
    ]

    for input_str, expected in test_cases:
        result = spider._parse_currency(input_str)
        assert abs(result - expected) < 0.01, f"Expected {expected}, got {result}"
        print(f"✓ Parsed '{input_str}' → {result}")


def test_spider_status_detection():
    """Test status detection from keywords"""
    print("\n" + "=" * 60)
    print("TEST: Status Detection - Keyword-Based")
    print("=" * 60)

    spider = NabavkiSpider()

    test_cases = [
        ("<html><body>Тендерот е отворен</body></html>", "open"),
        ("<html><body>Status: closed</body></html>", "closed"),
        ("<html><body>Contract awarded to Company XYZ</body></html>", "awarded"),
        ("<html><body>Откажан тендер</body></html>", "cancelled"),
    ]

    for html, expected_status in test_cases:
        response = create_response(html)
        result = spider._extract_status(response)
        assert result == expected_status, f"Expected {expected_status}, got {result}"
        print(f"✓ Detected status: {result}")


def test_spider_extraction_tracking():
    """Test that extraction success is tracked"""
    print("\n" + "=" * 60)
    print("TEST: Extraction Success Tracking")
    print("=" * 60)

    spider = NabavkiSpider()

    from scraper.items import TenderItem

    # Create tender with some fields
    tender = TenderItem()
    tender['tender_id'] = 'TEST-001'
    tender['title'] = 'Test Tender'
    tender['description'] = None  # Missing field
    tender['procuring_entity'] = 'Test Entity'
    tender['category'] = None  # Missing field

    # Track extraction
    spider._track_extraction_success(tender)

    # Verify tracking
    assert spider.extraction_stats['successful_extractions']['tender_id'] == 1
    assert spider.extraction_stats['successful_extractions']['title'] == 1
    assert spider.extraction_stats['failed_fields']['description'] == 1
    assert spider.extraction_stats['failed_fields']['category'] == 1

    print("✓ Extraction tracking works correctly")
    print(f"  Successful: {spider.extraction_stats['successful_extractions']}")
    print(f"  Failed: {spider.extraction_stats['failed_fields']}")


def test_resilience_to_structure_changes():
    """
    Test that spider can extract data from different HTML structures
    Simulates website redesign
    """
    print("\n" + "=" * 60)
    print("TEST: Resilience to Structure Changes")
    print("=" * 60)

    spider = NabavkiSpider()

    # Original structure
    html_v1 = """
    <html>
        <body>
            <h1 class="tender-title">Original Structure</h1>
            <div class="entity">Ministry of Finance</div>
        </body>
    </html>
    """

    # Redesigned structure (different classes)
    html_v2 = """
    <html>
        <body>
            <h1>Redesigned Structure</h1>
            <div class="new-organization-class">Ministry of Finance</div>
        </body>
    </html>
    """

    # Completely different structure (label-based)
    html_v3 = """
    <html>
        <body>
            <table>
                <tr><td>Назив</td><td>Label-Based Structure</td></tr>
                <tr><td>Нарачател</td><td>Ministry of Finance</td></tr>
            </table>
        </body>
    </html>
    """

    structures = [
        (html_v1, "Original Structure"),
        (html_v2, "Redesigned Structure"),
        (html_v3, "Label-Based Structure"),
    ]

    for html, expected_title in structures:
        response = create_response(html)

        # Extract title
        title = FieldExtractor.extract_with_fallbacks(
            response, 'title', [
                {'type': 'css', 'path': 'h1.tender-title::text'},
                {'type': 'css', 'path': 'h1::text'},
                {'type': 'label', 'label': 'Назив'},
            ]
        )

        # Extract entity
        entity = FieldExtractor.extract_with_fallbacks(
            response, 'entity', [
                {'type': 'css', 'path': 'div.entity::text'},
                {'type': 'css', 'path': 'div.new-organization-class::text'},
                {'type': 'label', 'label': 'Нарачател'},
            ]
        )

        assert title == expected_title, f"Expected '{expected_title}', got {title}"
        assert entity == "Ministry of Finance", f"Expected 'Ministry of Finance', got {entity}"

        print(f"✓ Extracted from: {expected_title}")
        print(f"  Title: {title}")
        print(f"  Entity: {entity}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SPIDER RESILIENCE TEST SUITE")
    print("=" * 60)

    all_passed = True

    try:
        test_field_extractor_fallback_css()
        test_field_extractor_label_based()
        test_field_extractor_table_cells()
        test_spider_tender_id_from_url()
        test_spider_category_detection()
        test_spider_date_parsing()
        test_spider_currency_parsing()
        test_spider_status_detection()
        test_spider_extraction_tracking()
        test_resilience_to_structure_changes()

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL RESILIENCE TESTS PASSED")
        print("=" * 60)
        print("\nSpider is resilient to:")
        print("  ✓ CSS class changes")
        print("  ✓ HTML structure changes")
        print("  ✓ Table vs div layouts")
        print("  ✓ Missing fields")
        print("  ✓ Date format variations")
        print("  ✓ Currency format variations")
        print("  ✓ Multiple language labels")
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)
