#!/usr/bin/env python3
"""
Unified Gemini AI extraction for all document types in public procurement.

This module provides Gemini-based extraction for:
- contract: Awarded contract documents with final prices
- technical_specs: Technical specifications and requirements
- bid: Financial bid documents from suppliers
- tender_docs: Tender documentation and requirements
- other: Any other procurement-related documents

Each document type has a specialized prompt to maximize extraction accuracy.
"""
import json
import logging
import os
import re
from typing import Optional, List, Dict, Any
from decimal import Decimal

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Gemini configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')

# Initialize Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not set - Gemini extraction will be unavailable")


def parse_european_number(value) -> Optional[float]:
    """Parse European-style numbers like 2.100,00 or 2100.00"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    # Remove currency symbols and whitespace
    s = re.sub(r'[МКД€$\s]', '', s)
    if not s:
        return None
    # European format: 2.100,00 -> 2100.00
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    # Just comma as decimal: 2100,00 -> 2100.00
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return None


# Document-type-specific extraction prompts
EXTRACTION_PROMPTS = {
    'contract': """You are an expert at extracting product/service items from Macedonian public procurement contracts.

Analyze the following CONTRACT document (which may have OCR errors) and extract ALL items/products/services that were purchased.

For each item, extract:
- name: The product or service name (in original Macedonian)
- quantity: Number of units (if mentioned)
- unit: Unit of measurement (e.g., "парче", "kg", "литар", "месец")
- unit_price: Price per unit in MKD (if mentioned)
- total_price: Total price in MKD (if mentioned)
- specifications: Any technical specifications or descriptions

Important:
- Extract items even if some fields are missing
- Handle OCR errors intelligently (e.g., "xoMniyTepH" should be recognized as "компјутери")
- Include services (maintenance, consulting, etc.) not just physical products
- Prices are in Macedonian Denars (MKD/денари)
- This is a CONTRACT - focus on awarded/purchased items with final prices

Contract text:
{document_text}

Respond with a JSON array of items. Example format:
[
  {{"name": "Лаптоп компјутер", "quantity": 10, "unit": "парче", "unit_price": 45000, "total_price": 450000, "specifications": "Intel i5, 8GB RAM, 256GB SSD"}},
  {{"name": "Сервисирање на возила", "quantity": 12, "unit": "месец", "unit_price": 15000, "total_price": 180000, "specifications": "Месечно одржување"}}
]

If no items can be extracted, return an empty array: []

JSON response:""",

    'technical_specs': """You are an expert at extracting product/service requirements from Macedonian public procurement technical specifications.

Analyze the following TECHNICAL SPECIFICATION document (which may have OCR errors) and extract ALL items/products/services that are being requested.

For each item, extract:
- name: The product or service name (in original Macedonian)
- quantity: Number of units required (if mentioned)
- unit: Unit of measurement (e.g., "парче", "kg", "литар", "месец")
- unit_price: Estimated price per unit in MKD (if mentioned - may be blank in specs)
- total_price: Estimated total price in MKD (if mentioned - may be blank in specs)
- specifications: Technical requirements, dimensions, capacity, standards, certifications, etc.

Important:
- Extract items even if prices are not mentioned (technical specs often don't include prices)
- Handle OCR errors intelligently
- Capture ALL technical requirements in the specifications field
- Include medical devices, equipment, materials, services, etc.
- Prices (if present) are in Macedonian Denars (MKD/денари)
- This is a TECHNICAL SPEC - focus on requirements and specifications

Document text:
{document_text}

Respond with a JSON array of items. Example format:
[
  {{"name": "Ултразвучен апарат", "quantity": 1, "unit": "парче", "unit_price": null, "total_price": null, "specifications": "Фреквенција 3.5-5 MHz, дисплеј минимум 15 инчи, со Doppler, CE сертификат"}},
  {{"name": "Хируршки инструменти сет", "quantity": 5, "unit": "сет", "unit_price": null, "total_price": null, "specifications": "Нерѓосувачки челик, стерилизација 134°C, EN ISO 13402"}}
]

If no items can be extracted, return an empty array: []

JSON response:""",

    'bid': """You are an expert at extracting bid items from Macedonian public procurement financial bid documents.

Analyze the following FINANCIAL BID document (which may have OCR errors) and extract ALL items that the bidder is offering.

For each item, extract:
- name: The product or service name (in original Macedonian)
- quantity: Number of units offered (if mentioned)
- unit: Unit of measurement (e.g., "парче", "kg", "литар", "месец")
- unit_price: Bid price per unit in MKD
- total_price: Total bid price in MKD
- specifications: Any specifications or notes from the bidder

Important:
- This is a BID - extract the supplier's offered prices
- Handle OCR errors intelligently
- Include lot numbers if present
- Prices are in Macedonian Denars (MKD/денари)
- Look for bid tables with item descriptions and prices
- Extract VAT information if mentioned

Document text:
{document_text}

Respond with a JSON array of items. Example format:
[
  {{"name": "Лаптоп компјутер HP EliteBook", "quantity": 10, "unit": "парче", "unit_price": 42000, "total_price": 420000, "specifications": "Intel i5-1135G7, 8GB RAM, 256GB SSD"}},
  {{"name": "Монитор Dell 24 инчи", "quantity": 10, "unit": "парче", "unit_price": 8500, "total_price": 85000, "specifications": "Full HD, IPS панел"}}
]

If no items can be extracted, return an empty array: []

JSON response:""",

    'tender_docs': """You are an expert at extracting item requirements from Macedonian public procurement tender documents.

Analyze the following TENDER DOCUMENT (which may have OCR errors) and extract ALL items/products/services that are being requested.

For each item, extract:
- name: The product or service name (in original Macedonian)
- quantity: Number of units requested (if mentioned)
- unit: Unit of measurement (e.g., "парче", "kg", "литар", "месец")
- unit_price: Estimated/budgeted price per unit in MKD (if mentioned)
- total_price: Estimated/budgeted total in MKD (if mentioned)
- specifications: Requirements, standards, qualifications needed

Important:
- Extract items even if prices are not mentioned
- Handle OCR errors intelligently
- Include eligibility criteria and minimum requirements in specifications
- This is a TENDER DOC - focus on what is being requested
- Prices (if present) are in Macedonian Denars (MKD/денари)

Document text:
{document_text}

Respond with a JSON array of items. Example format:
[
  {{"name": "Градежни материјали - цемент", "quantity": 100, "unit": "тон", "unit_price": 5500, "total_price": 550000, "specifications": "CEM II/A-M 42.5R, EN 197-1"}},
  {{"name": "Транспортни услуги", "quantity": 12, "unit": "месец", "unit_price": 25000, "total_price": 300000, "specifications": "Возила со минимум 3 тони носивост"}}
]

If no items can be extracted, return an empty array: []

JSON response:""",

    'other': """You are an expert at extracting information from Macedonian public procurement documents.

Analyze the following document (which may have OCR errors) and extract ANY items/products/services mentioned.

For each item, extract:
- name: The product or service name (in original Macedonian)
- quantity: Number of units (if mentioned)
- unit: Unit of measurement (e.g., "парче", "kg", "литар", "месец")
- unit_price: Price per unit in MKD (if mentioned)
- total_price: Total price in MKD (if mentioned)
- specifications: Any relevant details

Important:
- Extract items even if some fields are missing
- Handle OCR errors intelligently
- Include any products, services, materials, equipment mentioned
- Prices (if present) are in Macedonian Denars (MKD/денари)

Document text:
{document_text}

Respond with a JSON array of items. Example format:
[
  {{"name": "Канцелариски материјали", "quantity": 50, "unit": "парче", "unit_price": 150, "total_price": 7500, "specifications": "Хартија А4, 500 листови"}},
  {{"name": "Консултантски услуги", "quantity": 6, "unit": "месец", "unit_price": 35000, "total_price": 210000, "specifications": "IT консалтинг и поддршка"}}
]

If no items can be extracted, return an empty array: []

JSON response:"""
}


class GeminiExtractor:
    """Unified Gemini AI extractor for all document types"""

    def __init__(self):
        """Initialize Gemini extractor"""
        self.available = GEMINI_API_KEY is not None
        if self.available:
            self.model = genai.GenerativeModel(GEMINI_MODEL)
        else:
            self.model = None
            logger.warning("Gemini extractor initialized but API key not available")

    def is_available(self) -> bool:
        """Check if Gemini extraction is available"""
        return self.available

    def extract_items(self, document_text: str, doc_category: str = 'other',
                     max_length: int = 15000) -> List[Dict[str, Any]]:
        """
        Extract items from document text using Gemini AI.

        Args:
            document_text: Text content of the document
            doc_category: Document category ('contract', 'technical_specs', 'bid', 'tender_docs', 'other')
            max_length: Maximum text length to send to Gemini (will truncate if longer)

        Returns:
            List of extracted items as dictionaries with keys:
            - name, quantity, unit, unit_price, total_price, specifications
        """
        if not self.available:
            logger.warning("Gemini extraction unavailable - API key not set")
            return []

        if not document_text or len(document_text) < 100:
            logger.info("Document text too short for Gemini extraction")
            return []

        try:
            # Truncate very long texts
            if len(document_text) > max_length:
                logger.info(f"Truncating document from {len(document_text)} to {max_length} chars")
                document_text = document_text[:max_length] + "\n... [truncated]"

            # Get appropriate prompt for document type
            prompt_template = EXTRACTION_PROMPTS.get(doc_category, EXTRACTION_PROMPTS['other'])
            prompt = prompt_template.format(document_text=document_text)

            logger.info(f"Sending {len(document_text)} chars to Gemini for {doc_category} extraction")

            # Call Gemini API
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=16384,
                    response_mime_type="application/json",
                )
            )

            # Parse JSON response
            response_text = response.text.strip()

            # Handle markdown code blocks
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text

            items = self._parse_json_with_repair(response_text)

            if not isinstance(items, list):
                logger.warning(f"Expected list from Gemini, got {type(items)}")
                return []

            logger.info(f"Gemini extracted {len(items)} items from {doc_category} document")
            return items

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Gemini response as JSON: {e}")
            logger.debug(f"Response was: {response_text[:500]}")
            return []
        except Exception as e:
            logger.error(f"Gemini extraction failed: {e}")
            return []

    @staticmethod
    def _parse_json_with_repair(text: str) -> Any:
        """Parse JSON with repair for truncated responses."""
        # First try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to repair truncated JSON arrays
        # Find the last complete object (ends with })
        last_brace = text.rfind('}')
        if last_brace > 0:
            # Try closing the array after the last complete object
            candidate = text[:last_brace + 1].rstrip().rstrip(',') + ']'
            try:
                result = json.loads(candidate)
                if isinstance(result, list):
                    logger.info(f"Repaired truncated JSON: recovered {len(result)} items")
                    return result
            except json.JSONDecodeError:
                pass

        # Last resort: extract individual JSON objects with regex
        items = []
        for m in re.finditer(r'\{[^{}]*\}', text):
            try:
                obj = json.loads(m.group())
                if 'name' in obj:
                    items.append(obj)
            except json.JSONDecodeError:
                continue
        if items:
            logger.info(f"Extracted {len(items)} items via regex fallback")
            return items

        raise json.JSONDecodeError("Could not repair JSON", text, 0)

    def extract_and_normalize(self, document_text: str, doc_category: str = 'other') -> List[Dict[str, Any]]:
        """
        Extract items and normalize numeric fields.

        Returns items with normalized fields ready for database insertion.
        """
        items = self.extract_items(document_text, doc_category)

        # Normalize numeric fields
        for item in items:
            # Normalize prices
            if 'unit_price' in item and item['unit_price'] is not None:
                item['unit_price'] = parse_european_number(item['unit_price'])

            if 'total_price' in item and item['total_price'] is not None:
                item['total_price'] = parse_european_number(item['total_price'])

            # Normalize quantity
            if 'quantity' in item and item['quantity'] is not None:
                try:
                    qty = item['quantity']
                    if isinstance(qty, str):
                        qty = qty.replace(',', '.').replace(' ', '')
                    item['quantity'] = float(qty)
                except (ValueError, TypeError):
                    item['quantity'] = None

        return items


# Convenience function
def extract_with_gemini(document_text: str, doc_category: str = 'other') -> List[Dict[str, Any]]:
    """
    Convenience function to extract items using Gemini.

    Args:
        document_text: Text content of the document
        doc_category: Document category ('contract', 'technical_specs', 'bid', 'tender_docs', 'other')

    Returns:
        List of extracted items
    """
    extractor = GeminiExtractor()
    return extractor.extract_and_normalize(document_text, doc_category)
