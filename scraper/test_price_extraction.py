#!/usr/bin/env python3
"""
Test script for improved price extraction in spec_extractor.py

Tests the Macedonian number format parser and price extraction from tables.
"""

import sys
import logging
from decimal import Decimal
from spec_extractor import SpecificationExtractor

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_macedonian_number_parser():
    """Test the Macedonian number format parser"""
    print("\n" + "="*80)
    print("Testing Macedonian Number Parser")
    print("="*80)

    extractor = SpecificationExtractor()

    test_cases = [
        ("2.000,00", Decimal("2000.00"), "Macedonian format with thousands and decimals"),
        ("19.399,00", Decimal("19399.00"), "Macedonian format - typical price"),
        ("1.234.567,89", Decimal("1234567.89"), "Large number with multiple thousands"),
        ("500", Decimal("500"), "Simple integer"),
        ("500,50", Decimal("500.50"), "Decimal with comma"),
        ("1.000", Decimal("1000"), "Thousands separator only"),
        ("100,00", Decimal("100.00"), "Small number with decimal"),
        ("", None, "Empty string"),
        ("-", None, "Dash placeholder"),
        ("н/а", None, "N/A in Cyrillic"),
        ("2.000,00 ден", Decimal("2000.00"), "Price with currency suffix"),
    ]

    passed = 0
    failed = 0

    for input_val, expected, description in test_cases:
        result = extractor._parse_macedonian_number(input_val)
        status = "✓" if result == expected else "✗"

        if result == expected:
            passed += 1
            print(f"{status} PASS: '{input_val}' -> {result} ({description})")
        else:
            failed += 1
            print(f"{status} FAIL: '{input_val}' -> Expected: {expected}, Got: {result} ({description})")

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_table_price_extraction():
    """Test price extraction from a mock table"""
    print("\n" + "="*80)
    print("Testing Table Price Extraction")
    print("="*80)

    extractor = SpecificationExtractor()

    # Mock table with Macedonian headers and data
    table = [
        # Header row
        ["Р.бр.", "Назив на ставка", "Мерна единица", "Количина", "Единечна цена", "Вкупна цена"],
        # Data rows
        ["1", "Лек Nilotinib 200mg капсула", "Капсула", "5.376", "1.210,00", "6.504.960,00"],
        ["2", "Медицински инструмент", "Парче", "100", "2.500,00", "250.000,00"],
        ["3", "Канцелариски материјал", "Комплет", "50", "350,50", "17.525,00"],
    ]

    items = extractor.extract_from_tables([table], tender_id="TEST001")

    print(f"\nExtracted {len(items)} items:")
    for item in items:
        print(f"  - {item.name}")
        print(f"    Quantity: {item.quantity} {item.unit}")
        print(f"    Unit Price: {item.unit_price}")
        print(f"    Total Price: {item.total_price}")
        print()

    # Verify we extracted prices
    items_with_prices = sum(1 for item in items if item.unit_price or item.total_price)
    success = items_with_prices > 0

    if success:
        print(f"✓ SUCCESS: Extracted prices from {items_with_prices}/{len(items)} items")
    else:
        print(f"✗ FAILURE: No prices extracted from {len(items)} items")

    return success


def test_column_identification():
    """Test column identification with various header formats"""
    print("\n" + "="*80)
    print("Testing Column Identification")
    print("="*80)

    extractor = SpecificationExtractor()

    test_headers = [
        (["Назив", "Количина", "Единечна цена", "Вкупна цена"], "Standard Macedonian"),
        (["Name", "Quantity", "Unit price", "Total price"], "English"),
        (["Назив на ставка", "Кол.", "Ед. цена", "Вкупно"], "Abbreviated Macedonian"),
        (["Опис", "Број", "Цена по единица", "Вкупна цена без ДДВ"], "Alternative format"),
    ]

    all_passed = True
    for header, description in test_headers:
        print(f"\nTesting: {description}")
        print(f"Header: {header}")

        mapping = extractor._identify_columns(header)

        has_name = 'name' in mapping
        has_price = 'unit_price' in mapping or 'total_price_no_vat' in mapping

        if has_name and has_price:
            print(f"✓ PASS: Found name={mapping.get('name')}, prices={[k for k in mapping.keys() if 'price' in k]}")
        elif has_name:
            print(f"⚠ PARTIAL: Found name but no prices. Mapping: {mapping}")
            all_passed = False
        else:
            print(f"✗ FAIL: Missing required columns. Mapping: {mapping}")
            all_passed = False

    return all_passed


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("SPEC_EXTRACTOR PRICE EXTRACTION TEST SUITE")
    print("="*80)

    results = []

    # Run tests
    results.append(("Number Parser", test_macedonian_number_parser()))
    results.append(("Column Identification", test_column_identification()))
    results.append(("Table Price Extraction", test_table_price_extraction()))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
