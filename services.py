# proposal/services.py

import json
import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from openai import OpenAI
from core.models import RFP
from vendor.models import Vendor
from .models import Proposal

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.OPENAI_API_KEY)


def send_rfp_email(rfp: RFP, vendor: Vendor) -> bool:
    """Send RFP to a single vendor via email."""
    try:
        subject = f"RFP: {rfp.title}"
        body = f"""
Dear {vendor.contact_person or vendor.name},

Please submit a quote for the following procurement request:

"{rfp.raw_description}"

Best regards,
Procurement Team
        """.strip()

        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[vendor.email]
        )
        email.send()
        logger.info(f"RFP #{rfp.id} sent to {vendor.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send RFP to {vendor.email}: {e}")
        return False


def parse_proposal_with_ai(email_body: str) -> dict:
    """Parse vendor email response into structured data."""
    prompt = f"""
You are a procurement analyst. Extract key details from this vendor proposal.
Return ONLY valid JSON with these optional keys:
- quoted_items: list of {{ "item_name": str, "unit_price": float, "quantity": int, "total": float }}
- total_amount: float
- delivery_days: int
- warranty_months: int
- payment_terms: str

Proposal:
{email_body}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:-3]
        return json.loads(content)
    except Exception as e:
        logger.error(f"AI parsing failed: {e}")
        return {}


def generate_recommendation(rfp: RFP, proposals: list) -> dict:
    """Generate AI-powered vendor recommendation."""
    context = {
        "rfp": rfp.structured_data,
        "proposals": [
            {"vendor": p.vendor.name, "data": p.parsed_data}
            for p in proposals if p.parsed_data
        ]
    }
    prompt = f"""
As a procurement expert, recommend the best vendor based on the RFP and proposals below.
Consider price, completeness, delivery, and warranty.
Return ONLY JSON: {{"recommendation": "Vendor Name", "reason": "Brief explanation"}}

Context:
{json.dumps(context, indent=2)}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:-3]
        return json.loads(content)
    except Exception as e:
        logger.error(f"Recommendation failed: {e}")
        return {
            "recommendation": "Unable to decide",
            "reason": "AI evaluation failed due to missing or invalid data."
        }