#!/usr/bin/env python3
"""
Test script to verify Gemini extraction works for all document types.

This script tests the unified Gemini extractor on sample text from each document category.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from gemini_extractor import GeminiExtractor

# Sample texts for each document type
SAMPLE_TEXTS = {
    'contract': """
ДОГОВОР ЗА ЈАВНА НАБАВКА БР. 123/2025

Меѓу:
1. Купувач: Јавна здравствена установа "Градска Болница", Скопје
2. Добавувач: Медикал Опрема ДООЕЛ, Скопје

ПРЕДМЕТ НА ДОГОВОРОТ:

Добавувачот се обврзува да испорача:

Дел 1: Медицинска опрема
1. Ултразвучен апарат - 2 парче - Единечна цена: 850.000,00 МКД - Вкупно: 1.700.000,00 МКД
   Спецификација: Фреквенција 3.5-5 MHz, Дисплеј 15 инчи, Doppler функција

2. ЕКГ апарат - 5 парче - Единечна цена: 120.000,00 МКД - Вкупно: 600.000,00 МКД
   Спецификација: 12-канален, со принтер, CE сертификат

ВКУПНА ВРЕДНОСТ: 2.300.000,00 МКД
""",

    'technical_specs': """
ТЕХНИЧКА СПЕЦИФИКАЦИЈА
Јавна Набавка бр. 456/2025 - Медицински Инструменти

БАРАНИ ПРОИЗВОДИ:

1. Хируршки инструменти - комплет
   Количина: 10 сетови
   Технички барања:
   - Материјал: Нерѓосувачки челик AISI 420
   - Стерилизација: До 134°C
   - Стандард: EN ISO 13402
   - Сертификат: CE

2. Инфузиони пумпи
   Количина: 8 парчиња
   Технички барања:
   - Точност: ±2%
   - Проток: 0.1-1200 ml/h
   - Батерија: Минимум 4 часа
   - Аларми: За оклузија, воздух, празна батерија
""",

    'bid': """
ПОНУДА ЗА ЈАВНА НАБАВКА бр. 789/2025
Понудувач: ИТ Солушнс ДООЕЛ

ЦЕНОВНА ПОНУДА:

Дел 1: Компјутерска опрема

Р.бр. | Назив | Количина | Единица | Единечна цена | Вкупно
1 | Лаптоп Dell Latitude 5540 | 25 | парче | 48.500,00 | 1.212.500,00
   Спецификација: Intel i5-1345U, 16GB RAM, 512GB SSD

2 | Монитор Dell P2423DE | 25 | парче | 15.800,00 | 395.000,00
   Спецификација: 24 инчи, QHD, IPS, USB-C

3 | Тастатура и глувче | 25 | сет | 2.200,00 | 55.000,00
   Спецификација: Безжична, ергономска

ВКУПНО БЕЗ ДДВ: 1.662.500,00 МКД
ДДВ 18%: 299.250,00 МКД
ВКУПНО СО ДДВ: 1.961.750,00 МКД
""",

    'tender_docs': """
ТЕНДЕРСКА ДОКУМЕНТАЦИЈА
Јавна набавка: Градежни материјали бр. 321/2025

ОПИС НА ПОТРЕБИТЕ:

1. Цемент CEM II/A-M 42.5R
   Количина: 500 тони
   Стандард: EN 197-1
   Рок на испорака: 30 дена
   Проценета вредност: 5.500,00 МКД/тона

2. Арматурни шипки Ø12мм
   Количина: 50 тони
   Стандард: EN 10080
   Квалитет: B500B
   Проценета вредност: 48.000,00 МКД/тона

3. Бетонски плочки 40x40см
   Количина: 10.000 парчиња
   Дебелина: 4см
   Отпорност: минимум C30/37
   Проценета вредност: 280,00 МКД/парче

КРИТЕРИУМИ:
- Најниска цена
- Квалитет според стандарди
- Рок на испорака
""",

    'other': """
ЗАПИСНИК ОД ОТВОРАЊЕ НА ПОНУДИ
Јавна набавка бр. 555/2025

Датум: 15.03.2025

ПРЕДМЕТ: Канцелариски материјали и консултантски услуги

Примени понуди:
1. Офис Експрес ДООЕЛ - Канцелариски материјали (500 пакети хартија А4, 200 парчиња тонери, 100 сетови пенкала)
2. Консалтинг Групација ДОО - ИТ консултантски услуги (12 месеци x 45.000 МКД = 540.000 МКД)

Техничка оценка во тек.
"""
}


def test_gemini_extraction():
    """Test Gemini extraction for all document types"""
    extractor = GeminiExtractor()

    if not extractor.is_available():
        print("ERROR: Gemini API key not set!")
        print("Please set GEMINI_API_KEY environment variable")
        return False

    print("=" * 80)
    print("TESTING GEMINI EXTRACTION FOR ALL DOCUMENT TYPES")
    print("=" * 80)

    results = {}

    for doc_type, sample_text in SAMPLE_TEXTS.items():
        print(f"\n\n{'='*80}")
        print(f"Testing: {doc_type.upper()}")
        print('='*80)
        print(f"Sample text length: {len(sample_text)} chars")

        try:
            items = extractor.extract_and_normalize(sample_text, doc_type)

            if items:
                print(f"\n✓ SUCCESS: Extracted {len(items)} items\n")

                for i, item in enumerate(items, 1):
                    print(f"Item {i}:")
                    print(f"  Name: {item.get('name', 'N/A')}")
                    print(f"  Quantity: {item.get('quantity', 'N/A')}")
                    print(f"  Unit: {item.get('unit', 'N/A')}")
                    print(f"  Unit Price: {item.get('unit_price', 'N/A')}")
                    print(f"  Total Price: {item.get('total_price', 'N/A')}")
                    print(f"  Specifications: {item.get('specifications', 'N/A')[:100]}...")
                    print()

                results[doc_type] = len(items)
            else:
                print(f"\n✗ FAILED: No items extracted")
                results[doc_type] = 0

        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            results[doc_type] = -1

    # Summary
    print("\n\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    for doc_type, count in results.items():
        status = "✓ PASS" if count > 0 else "✗ FAIL"
        print(f"{doc_type:20s} {status:8s} - {count if count >= 0 else 'ERROR'} items")

    total_items = sum(c for c in results.values() if c > 0)
    print(f"\nTotal items extracted: {total_items}")

    # Check if all document types worked
    all_passed = all(count > 0 for count in results.values())

    if all_passed:
        print("\n✓ ALL DOCUMENT TYPES WORKING!")
        return True
    else:
        print("\n✗ Some document types failed")
        return False


if __name__ == '__main__':
    success = test_gemini_extraction()
    sys.exit(0 if success else 1)
