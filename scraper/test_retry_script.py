#!/usr/bin/env python3
"""
Quick test script for retry_failed_docs.py

Tests the failure analyzer and retry strategies without database access.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from retry_failed_docs import FailureAnalyzer

def test_failure_analyzer():
    """Test the failure analyzer logic"""
    print("Testing FailureAnalyzer...\n")

    # Create a test file
    test_dir = Path(__file__).parent / 'test_files'
    test_dir.mkdir(exist_ok=True)
    test_file = test_dir / 'test.pdf'
    test_file.touch()

    # Test case 1: OCR required with existing file
    doc1 = {
        'doc_id': 'test-1',
        'extraction_status': 'ocr_required',
        'file_path': str(test_file),
        'file_url': 'https://e-nabavki.gov.mk/test.pdf'
    }
    result1 = FailureAnalyzer.analyze_failure(doc1)
    print("Test 1 - OCR required (file exists):")
    print(f"  Strategy: {result1['strategy']}")
    print(f"  Reason: {result1['reason']}")
    print(f"  Force OCR: {result1['force_ocr']}")
    print(f"  Expected: strategy='ocr', force_ocr=True")
    assert result1['strategy'] == 'ocr'
    assert result1['force_ocr'] == True
    print("  ✓ PASS\n")

    # Test case 2: Download failed
    doc2 = {
        'doc_id': 'test-2',
        'extraction_status': 'download_failed',
        'file_path': None,
        'file_url': 'https://e-nabavki.gov.mk/test2.pdf'
    }
    result2 = FailureAnalyzer.analyze_failure(doc2)
    print("Test 2 - Download failed:")
    print(f"  Strategy: {result2['strategy']}")
    print(f"  Reason: {result2['reason']}")
    print(f"  Retry download: {result2['retry_download']}")
    print(f"  Expected: strategy='redownload', retry_download=True")
    assert result2['strategy'] == 'redownload'
    assert result2['retry_download'] == True
    print("  ✓ PASS\n")

    # Test case 3: Generic failure with existing file
    test_file3 = test_dir / 'test3.pdf'
    test_file3.touch()
    doc3 = {
        'doc_id': 'test-3',
        'extraction_status': 'failed',
        'file_path': str(test_file3),
        'file_url': 'https://e-nabavki.gov.mk/test3.pdf'
    }
    result3 = FailureAnalyzer.analyze_failure(doc3)
    print("Test 3 - Generic failure (file exists):")
    print(f"  Strategy: {result3['strategy']}")
    print(f"  Reason: {result3['reason']}")
    print(f"  Retry extraction: {result3['retry_extraction']}")
    print(f"  Expected: strategy='retry_extraction', retry_extraction=True")
    assert result3['strategy'] == 'retry_extraction'
    assert result3['retry_extraction'] == True
    print("  ✓ PASS\n")

    # Test case 4: Generic failure without file
    doc4 = {
        'doc_id': 'test-4',
        'extraction_status': 'failed',
        'file_path': None,
        'file_url': 'https://e-nabavki.gov.mk/test4.pdf'
    }
    result4 = FailureAnalyzer.analyze_failure(doc4)
    print("Test 4 - Generic failure (file missing):")
    print(f"  Strategy: {result4['strategy']}")
    print(f"  Reason: {result4['reason']}")
    print(f"  Retry download: {result4['retry_download']}")
    print(f"  Expected: strategy='redownload_then_extract', retry_download=True")
    assert result4['strategy'] == 'redownload_then_extract'
    assert result4['retry_download'] == True
    print("  ✓ PASS\n")

    # Test case 5: Download failed with no URL (should skip)
    doc5 = {
        'doc_id': 'test-5',
        'extraction_status': 'download_failed',
        'file_path': None,
        'file_url': ''
    }
    result5 = FailureAnalyzer.analyze_failure(doc5)
    print("Test 5 - Download failed (no URL):")
    print(f"  Strategy: {result5['strategy']}")
    print(f"  Reason: {result5['reason']}")
    print(f"  Expected: strategy='skip'")
    assert result5['strategy'] == 'skip'
    print("  ✓ PASS\n")

    print("="*60)
    print("All tests passed! ✓")
    print("="*60)
    print("\nFailureAnalyzer is working correctly.")
    print("\nNext steps:")
    print("1. Install Tesseract OCR: sudo apt-get install tesseract-ocr tesseract-ocr-mkd")
    print("2. Install Python deps: pip install pytesseract pillow")
    print("3. Test with dry run: python3 retry_failed_docs.py --dry-run --limit 5")
    print("4. Run real retry: python3 retry_failed_docs.py --status ocr_required --limit 10")

if __name__ == '__main__':
    test_failure_analyzer()
