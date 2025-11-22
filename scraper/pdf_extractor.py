"""PDF text extraction with Cyrillic support"""
import fitz  # PyMuPDF - best for Cyrillic
import logging

logger = logging.getLogger(__name__)

def extract_pdf_text(pdf_path: str) -> str:
    """
    Extract text from PDF using PyMuPDF.
    Handles Macedonian Cyrillic (UTF-8) natively.
    """
    try:
        doc = fitz.open(pdf_path)
        text_pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            # Extract with UTF-8 encoding preserved
            text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            text_pages.append(text)

        doc.close()
        full_text = "\n\n".join(text_pages)

        # Verify Cyrillic preserved
        if any(ord(char) >= 0x0400 and ord(char) <= 0x04FF for char in full_text):
            logger.info(f"Cyrillic text detected and preserved in {pdf_path}")

        return full_text.strip()

    except Exception as e:
        logger.error(f"PDF extraction failed for {pdf_path}: {e}")
        return ""
