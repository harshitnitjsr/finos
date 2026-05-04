"""
Invoice Intelligence Agent
Handles: OCR extraction, vendor matching, duplicate detection, tax extraction, field structuring.
Model: GPT-4o-mini for extraction, GPT-4o for complex reasoning.
"""
import json
import time
import base64
import re
from datetime import datetime
from typing import Optional
from loguru import logger

from app.core.model_router import model_router, ModelTask


EXTRACTION_SYSTEM_PROMPT = """You are an expert invoice extraction AI. Your job is to extract structured data from invoice text with extreme precision.

Extract ALL of the following fields:
- invoice_number: Invoice/bill number. For travel invoices, use the Booking Reference, PNR, or Ticket Number if a formal 'Invoice Number' is missing.
- vendor_name: Supplier/vendor name (e.g., "Air India Express", "Amazon", "Stripe")
- vendor_email: Vendor email if present
- invoice_date: Date of invoice (ISO format YYYY-MM-DD)
- due_date: Payment due date (ISO format YYYY-MM-DD)
- amount: Subtotal amount (number only, no currency symbol)
- tax_amount: Tax/GST/VAT amount (number only)
- total_amount: Total payable amount (number only)
- currency: Currency code (USD, INR, EUR, GBP, etc.)
- description: Brief description of goods/services. If travel, include flight/route details.
- line_items: Array of {description, quantity, unit_price, total}
- payment_terms: Payment terms if specified
- po_number: Purchase order number if present

Return ONLY a valid JSON object. Use null for missing fields. 
For currency: detect from symbols ($ → USD, ₹ → INR, € → EUR, £ → GBP, ¥ → JPY) or text.
For amounts: extract numeric value only (e.g., "1,234.56" → 1234.56).
"""

DUPLICATE_CHECK_PROMPT = """You are a financial fraud detection AI. Analyze whether this invoice is a duplicate of any existing invoice.

Compare: invoice number, vendor name, amount, date, and description.
Return JSON: {"is_duplicate": bool, "duplicate_id": string|null, "confidence": float, "reason": string}
"""

RISK_ANALYSIS_PROMPT = """You are a financial risk analyst AI. Analyze this invoice for risk factors.

Consider:
- Unusual amounts
- Unknown vendors
- Missing required fields
- Suspicious patterns
- Policy violations

Return JSON: {
  "risk_level": "low|medium|high|critical",
  "risk_score": float (0-100),
  "risk_factors": [{"factor": str, "severity": str, "description": str}],
  "policy_violations": [{"policy": str, "violation": str}],
  "recommendation": "approve|review|reject|escalate"
}
"""


class InvoiceAgent:
    """AI agent for intelligent invoice processing."""

    async def extract_from_text(self, raw_text: str) -> dict:
        """Extract structured invoice data from OCR text."""
        start = time.time()
        
        try:
            response = await model_router.complete(
                task=ModelTask.EXTRACTION,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                user_prompt=f"Extract invoice data from this text:\n\n{raw_text[:4000]}",
                temperature=0.1,
                max_tokens=2000,
            )
            
            # Parse JSON response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                extracted = json.loads(json_match.group())
            else:
                extracted = json.loads(response)

            latency_ms = int((time.time() - start) * 1000)
            logger.info(f"InvoiceAgent: extracted fields in {latency_ms}ms")
            return extracted

        except Exception as e:
            logger.error(f"InvoiceAgent extraction failed: {e}")
            return self._fallback_extraction(raw_text)

    def _fallback_extraction(self, text: str) -> dict:
        """Regex-based fallback extraction when AI fails."""
        result = {
            "invoice_number": None,
            "vendor_name": None,
            "amount": None,
            "currency": "USD",
            "total_amount": None,
            "tax_amount": None,
            "invoice_date": None,
            "due_date": None,
            "description": None,
            "line_items": [],
        }

        # Try to extract invoice number
        inv_match = re.search(r'invoice[#\s:]+([A-Z0-9\-]+)', text, re.IGNORECASE)
        if inv_match:
            result["invoice_number"] = inv_match.group(1)

        # Try to extract amounts
        amount_matches = re.findall(r'[\$₹€£¥]?\s*([\d,]+\.?\d*)', text)
        if amount_matches:
            amounts = [float(a.replace(',', '')) for a in amount_matches if a]
            if amounts:
                result["total_amount"] = max(amounts)

        # Currency detection
        if '₹' in text or 'INR' in text:
            result["currency"] = "INR"
        elif '€' in text or 'EUR' in text:
            result["currency"] = "EUR"
        elif '£' in text or 'GBP' in text:
            result["currency"] = "GBP"

        return result

    async def analyze_risk(
        self,
        extracted_fields: dict,
        vendor_history: Optional[dict] = None,
        org_policies: Optional[list] = None,
    ) -> dict:
        """Analyze invoice risk using GPT-4o."""
        context = {
            "invoice": extracted_fields,
            "vendor_history": vendor_history or {},
            "policies": org_policies or [],
        }

        try:
            response = await model_router.complete(
                task=ModelTask.COMPLIANCE,
                system_prompt=RISK_ANALYSIS_PROMPT,
                user_prompt=f"Analyze this invoice for risk:\n\n{json.dumps(context, indent=2, default=str)[:3000]}",
                temperature=0.2,
                max_tokens=1000,
            )

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"InvoiceAgent risk analysis failed: {e}")

        return {
            "risk_level": "low",
            "risk_score": 10.0,
            "risk_factors": [],
            "policy_violations": [],
            "recommendation": "approve",
        }

    async def check_duplicate(
        self,
        invoice_data: dict,
        existing_invoices: list[dict],
    ) -> dict:
        """Check if invoice is a duplicate using AI comparison."""
        if not existing_invoices:
            return {"is_duplicate": False, "duplicate_id": None, "confidence": 0.0, "reason": "No existing invoices"}

        prompt = f"""
New invoice: {json.dumps(invoice_data, default=str)}

Existing invoices (last 50): {json.dumps(existing_invoices[:50], default=str)[:3000]}

Check if the new invoice is a duplicate of any existing invoice.
"""
        try:
            response = await model_router.complete(
                task=ModelTask.CLASSIFICATION,
                system_prompt=DUPLICATE_CHECK_PROMPT,
                user_prompt=prompt,
                temperature=0.1,
                max_tokens=200,
            )
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")

        return {"is_duplicate": False, "duplicate_id": None, "confidence": 0.0, "reason": "Check failed"}

    async def generate_insights(self, invoice_data: dict, vendor_history: dict) -> str:
        """Generate AI insights about this invoice."""
        try:
            return await model_router.complete(
                task=ModelTask.REASONING,
                system_prompt="You are a financial analyst. Provide brief, actionable insights about this invoice in 2-3 sentences.",
                user_prompt=f"Invoice: {json.dumps(invoice_data, default=str)}\nVendor history: {json.dumps(vendor_history, default=str)[:1000]}",
                temperature=0.3,
                max_tokens=200,
            )
        except Exception:
            return "Invoice processed successfully. No additional insights available."


invoice_agent = InvoiceAgent()
