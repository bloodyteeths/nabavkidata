"""
Test document parser resilience and extraction features
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from document_parser import (
    CPVExtractor,
    CompanyExtractor,
    PDFAnalyzer,
    ExtractionResult
)


def test_cpv_extraction_standard_format():
    """Test CPV code extraction - standard format"""
    print("\n" + "=" * 60)
    print("TEST: CPV Extraction - Standard Format")
    print("=" * 60)

    text = """
    Набавка на опрема
    CPV код: 45000000-7
    Дополнително: 48000000-8
    """

    cpv_codes = CPVExtractor.extract_cpv_codes(text)

    assert '45000000-7' in cpv_codes
    assert '48000000-8' in cpv_codes
    print(f"✓ Extracted CPV codes: {cpv_codes}")


def test_cpv_extraction_multiple_patterns():
    """Test CPV extraction with various formats"""
    print("\n" + "=" * 60)
    print("TEST: CPV Extraction - Multiple Patterns")
    print("=" * 60)

    test_cases = [
        ("CPV: 45000000-7", "45000000-7"),
        ("CPV код: 48000000-8", "48000000-8"),
        ("Код: 30200000-1", "30200000-1"),
        ("45000000-7 и 48000000-8", ["45000000-7", "48000000-8"]),
        ("450000007", "45000000-7"),  # Without hyphen
    ]

    for text, expected in test_cases:
        cpv_codes = CPVExtractor.extract_cpv_codes(text)
        if isinstance(expected, list):
            for code in expected:
                assert code in cpv_codes
        else:
            assert expected in cpv_codes
        print(f"✓ '{text}' → {cpv_codes}")


def test_cpv_validation():
    """Test CPV code validation"""
    print("\n" + "=" * 60)
    print("TEST: CPV Code Validation")
    print("=" * 60)

    valid_codes = [
        "45000000-7",
        "48000000-8",
        "30200000-1",
    ]

    invalid_codes = [
        "1234567-8",    # Only 7 digits
        "12345678-89",  # 2 check digits
        "abcdefgh-1",   # Non-numeric
    ]

    for code in valid_codes:
        assert CPVExtractor._validate_cpv(code), f"{code} should be valid"
        print(f"✓ Valid: {code}")

    for code in invalid_codes:
        assert not CPVExtractor._validate_cpv(code), f"{code} should be invalid"
        print(f"✓ Invalid (correctly rejected): {code}")


def test_company_extraction_macedonian():
    """Test company name extraction - Macedonian"""
    print("\n" + "=" * 60)
    print("TEST: Company Extraction - Macedonian")
    print("=" * 60)

    test_cases = [
        ("Добитник: Технолошки Решенија ДООЕЛ", "Технолошки Решенија ДООЕЛ"),
        ("Доделено на: Градежна Компанија АД", "Градежна Компанија АД"),
        ("Компанија: Инженеринг ДОО", "Инженеринг ДОО"),
    ]

    for text, expected in test_cases:
        companies = CompanyExtractor.extract_companies(text)
        assert expected in companies, f"Expected '{expected}' in {companies}"
        print(f"✓ '{text}' → {expected}")


def test_company_extraction_english():
    """Test company name extraction - English"""
    print("\n" + "=" * 60)
    print("TEST: Company Extraction - English")
    print("=" * 60)

    test_cases = [
        ("Winner: Tech Solutions LLC", "Tech Solutions LLC"),
        ("Awarded to: Construction Company Ltd", "Construction Company Ltd"),
        ("Contractor: Engineering Corp", "Engineering Corp"),
    ]

    for text, expected in test_cases:
        companies = CompanyExtractor.extract_companies(text)
        assert expected in companies, f"Expected '{expected}' in {companies}"
        print(f"✓ '{text}' → {expected}")


def test_company_extraction_mixed():
    """Test company extraction with mixed languages"""
    print("\n" + "=" * 60)
    print("TEST: Company Extraction - Mixed Languages")
    print("=" * 60)

    text = """
    Добитник: Технолошки Решенија ДООЕЛ Скопје
    Also awarded to: Tech Solutions LLC New York
    Компанија: Градежна АД
    Contractor: Building Corp
    """

    companies = CompanyExtractor.extract_companies(text)

    expected_companies = [
        "Технолошки Решенија ДООЕЛ",
        "Tech Solutions LLC",
        "Градежна АД",
        "Building Corp",
    ]

    for expected in expected_companies:
        # Partial match (company name may include location)
        assert any(expected in company for company in companies), \
            f"Expected '{expected}' in {companies}"

    print(f"✓ Extracted {len(companies)} companies from mixed text:")
    for company in sorted(companies):
        print(f"  - {company}")


def test_company_validation():
    """Test company name validation"""
    print("\n" + "=" * 60)
    print("TEST: Company Name Validation")
    print("=" * 60)

    valid_companies = [
        "Tech Solutions LLC",
        "Технолошки Решенија ДООЕЛ",
        "Building Corp",
        "Градежна АД Скопје",
    ]

    invalid_companies = [
        "ABC",              # Too short
        "Company",          # No legal form
        "A" * 250,          # Too long
    ]

    for company in valid_companies:
        assert CompanyExtractor._validate_company_name(company), \
            f"{company} should be valid"
        print(f"✓ Valid: {company}")

    for company in invalid_companies:
        assert not CompanyExtractor._validate_company_name(company), \
            f"{company} should be invalid"
        print(f"✓ Invalid (correctly rejected): {company[:30]}...")


def test_company_cleaning():
    """Test company name cleaning"""
    print("\n" + "=" * 60)
    print("TEST: Company Name Cleaning")
    print("=" * 60)

    test_cases = [
        ("Tech  Solutions  LLC", "Tech Solutions LLC"),
        ("Building Corp.", "Building Corp"),
        ("Company Name  -  ", "Company Name"),
    ]

    for input_name, expected in test_cases:
        cleaned = CompanyExtractor._clean_company_name(input_name)
        assert cleaned == expected, f"Expected '{expected}', got '{cleaned}'"
        print(f"✓ '{input_name}' → '{cleaned}'")


def test_extraction_result_structure():
    """Test ExtractionResult data structure"""
    print("\n" + "=" * 60)
    print("TEST: ExtractionResult Structure")
    print("=" * 60)

    result = ExtractionResult(
        text="Sample text content",
        engine_used="pymupdf",
        page_count=5,
        has_tables=True,
        tables=[
            [['Header 1', 'Header 2'], ['Cell 1', 'Cell 2']]
        ],
        cpv_codes=['45000000-7'],
        company_names=['Tech Solutions LLC'],
        metadata={'has_cyrillic': True}
    )

    assert result.text == "Sample text content"
    assert result.engine_used == "pymupdf"
    assert result.page_count == 5
    assert result.has_tables == True
    assert len(result.tables) == 1
    assert len(result.cpv_codes) == 1
    assert len(result.company_names) == 1

    print("✓ ExtractionResult structure validated")
    print(f"  Text: {result.text[:20]}...")
    print(f"  Engine: {result.engine_used}")
    print(f"  Pages: {result.page_count}")
    print(f"  Tables: {len(result.tables)}")
    print(f"  CPV codes: {result.cpv_codes}")
    print(f"  Companies: {result.company_names}")


def test_multiple_cpv_codes_in_document():
    """Test extracting multiple CPV codes from realistic document text"""
    print("\n" + "=" * 60)
    print("TEST: Multiple CPV Codes Extraction")
    print("=" * 60)

    document_text = """
    ТЕНДЕРСКА ДОКУМЕНТАЦИЈА

    Набавка на компјутерска опрема и услуги

    CPV код: 48000000-8 (Софтверски пакети и информациски системи)

    Дополнителни категории:
    - Хардвер: 30200000-1
    - Услуги: 72000000-5
    - Одржување: Код 50000000-5

    Проценета вредност: 5.000.000 МКД
    """

    cpv_codes = CPVExtractor.extract_cpv_codes(document_text)

    expected_codes = ['30200000-1', '48000000-8', '50000000-5', '72000000-5']

    for code in expected_codes:
        assert code in cpv_codes, f"Expected {code} in {cpv_codes}"

    print(f"✓ Extracted all {len(expected_codes)} CPV codes:")
    for code in sorted(cpv_codes):
        print(f"  - {code}")


def test_award_decision_parsing():
    """Test realistic award decision document parsing"""
    print("\n" + "=" * 60)
    print("TEST: Award Decision Document Parsing")
    print("=" * 60)

    award_text = """
    ОДЛУКА ЗА ДОДЕЛУВАЊЕ

    Врз основа на спроведената постапка за јавна набавка,
    договорот се доделува на:

    Добитник: Технолошки Решенија ДООЕЛ Скопје

    CPV код: 48000000-8
    Вредност: 4.850.000 МКД

    Комисијата го одобри понудувачот како најповолен.
    """

    # Extract companies
    companies = CompanyExtractor.extract_companies(award_text)
    assert any('Технолошки Решенија ДООЕЛ' in c for c in companies)

    # Extract CPV codes
    cpv_codes = CPVExtractor.extract_cpv_codes(award_text)
    assert '48000000-8' in cpv_codes

    print("✓ Award decision parsed successfully:")
    print(f"  Winner: {[c for c in companies if 'Технолошки' in c][0]}")
    print(f"  CPV: {cpv_codes}")


def test_resilience_to_format_variations():
    """Test that extraction works with format variations"""
    print("\n" + "=" * 60)
    print("TEST: Resilience to Format Variations")
    print("=" * 60)

    # CPV code variations
    cpv_variations = [
        "CPV: 45000000-7",
        "CPV код: 45000000-7",
        "Код: 45000000-7",
        "45000000-7",
        "450000007",
    ]

    for text in cpv_variations:
        codes = CPVExtractor.extract_cpv_codes(text)
        assert '45000000-7' in codes
        print(f"✓ CPV extracted from: '{text}'")

    # Company name variations
    company_variations = [
        "Добитник: Company ДООЕЛ",
        "Доделено на: Company ДООЕЛ",
        "Компанија: Company ДООЕЛ",
        "Company ДООЕЛ",  # No label
    ]

    for text in company_variations:
        companies = CompanyExtractor.extract_companies(text)
        assert any('Company ДООЕЛ' in c for c in companies)
        print(f"✓ Company extracted from: '{text}'")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("DOCUMENT PARSER TEST SUITE")
    print("=" * 60)

    all_passed = True

    try:
        test_cpv_extraction_standard_format()
        test_cpv_extraction_multiple_patterns()
        test_cpv_validation()
        test_company_extraction_macedonian()
        test_company_extraction_english()
        test_company_extraction_mixed()
        test_company_validation()
        test_company_cleaning()
        test_extraction_result_structure()
        test_multiple_cpv_codes_in_document()
        test_award_decision_parsing()
        test_resilience_to_format_variations()

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
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nDocument parser is resilient to:")
        print("  ✓ Multiple CPV code formats")
        print("  ✓ Macedonian + English company names")
        print("  ✓ Various legal forms (ДООЕЛ, ДОО, АД, LLC, Ltd)")
        print("  ✓ Award decision variations")
        print("  ✓ Format inconsistencies")
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)
