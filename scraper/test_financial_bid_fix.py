#!/usr/bin/env python3
"""
Test script to validate the financial_bid_extractor fixes.

This tests the specific case where:
- CPV code is split: "50421200" and "-4" on separate lines
- Product name is on one line: "Николет"
- Unit is split: "Работен" and "час" on separate lines
- Numbers follow: 1,00 2.000,00 2.000,00 360,00 2.360,00
"""

from financial_bid_extractor import FinancialBidExtractor

# Sample PDF text with line-by-line format
SAMPLE_BID_TEXT = """
Дел I Финансиска понуда

Врз основа на огласот 123/2024 објавен од страна на Тест Компанија, за набавка на услуги, со спроведување...

Финансиска понуда

Шифра
Назив на ставка
Мерна
единица
Количина
Единечна
цена
Вкупна цена без ДДВ
ДДВ
Цена со ДДВ

50421200
-4
Николет
Работен
час
1,00
2.000,00
2.000,00
360,00
2.360,00

Вкупно: 2.000,00 ден | 360,00 ден | 2.360,00 ден

Вкупната цена на нашата понуда за извршување на предметот на набавката изнесува: 2.360,00 (Две илјади триста шеесет) денари.
"""


def test_extraction():
    """Test that the extractor properly handles line-by-line PDF text"""
    extractor = FinancialBidExtractor()

    # Verify it's recognized as a financial bid
    assert extractor.is_financial_bid(SAMPLE_BID_TEXT), "Document should be recognized as financial bid"

    # Extract the bid
    bid = extractor.extract(SAMPLE_BID_TEXT, "test_document.pdf")

    assert bid is not None, "Bid should be extracted"

    # Check basic info
    print(f"\n=== Extraction Results ===")
    print(f"Tender ID: {bid.tender_id}")
    print(f"Procuring Entity: {bid.procuring_entity}")
    print(f"Number of items: {len(bid.items)}")
    print(f"Confidence: {bid.extraction_confidence:.2f}")

    # Should have at least 1 item
    assert len(bid.items) >= 1, f"Should extract at least 1 item, got {len(bid.items)}"

    # Check the first item
    item = bid.items[0]
    print(f"\n=== Item 1 ===")
    print(f"CPV Code: {item.cpv_code}")
    print(f"Name: {item.name}")
    print(f"Unit: {item.unit}")
    print(f"Quantity: {item.quantity}")
    print(f"Unit Price: {item.unit_price_mkd}")
    print(f"Total Price: {item.total_price_mkd}")
    print(f"VAT: {item.vat_amount_mkd}")
    print(f"Total with VAT: {item.total_with_vat_mkd}")

    # Validate expected values
    assert item.cpv_code == "50421200-4", f"CPV code should be '50421200-4', got '{item.cpv_code}'"
    assert "Николет" in item.name, f"Name should contain 'Николет', got '{item.name}'"
    assert item.unit is not None, f"Unit should be extracted"
    assert "Работен" in item.unit or "час" in item.unit, f"Unit should contain 'Работен' or 'час', got '{item.unit}'"
    assert item.quantity is not None, f"Quantity should be extracted"
    assert item.unit_price_mkd is not None, f"Unit price should be extracted"

    # Check number parsing (Macedonian format: 2.000,00 = 2000.00)
    assert float(item.unit_price_mkd) == 2000.00, f"Unit price should be 2000.00, got {item.unit_price_mkd}"
    assert float(item.total_price_mkd) == 2000.00, f"Total price should be 2000.00, got {item.total_price_mkd}"
    assert float(item.vat_amount_mkd) == 360.00, f"VAT should be 360.00, got {item.vat_amount_mkd}"
    assert float(item.total_with_vat_mkd) == 2360.00, f"Total with VAT should be 2360.00, got {item.total_with_vat_mkd}"

    print(f"\n=== All Tests Passed! ===")
    return bid


if __name__ == "__main__":
    try:
        bid = test_extraction()
        print("\n✓ Financial bid extractor is working correctly!")
        print(f"✓ Successfully extracted {len(bid.items)} item(s) from line-by-line PDF text")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
