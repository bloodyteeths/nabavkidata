"""
Contact Form API Endpoint
Sends contact form submissions via Postmark to support@nabavkidata.com
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

from services.postmark import postmark_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/contact",
    tags=["Contact"]
)


class ContactFormRequest(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    phone: Optional[str] = None
    message: str
    plan: Optional[str] = None  # e.g., "enterprise" for enterprise inquiries


@router.post("", status_code=status.HTTP_200_OK)
async def submit_contact_form(form_data: ContactFormRequest):
    """
    Submit contact form - sends email to support@nabavkidata.com
    """
    try:
        # Build email content
        is_enterprise = form_data.plan == "enterprise"

        subject = "Enterprise Plan Inquiry" if is_enterprise else "Contact Form Submission"
        subject = f"[nabavkidata.com] {subject} - {form_data.name}"

        # Build details table
        details_rows = f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280; width: 120px;">Име:</td>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-weight: 600;">{form_data.name}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">Email:</td>
            <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">
                <a href="mailto:{form_data.email}" style="color: #2563eb;">{form_data.email}</a>
            </td>
        </tr>
        """

        if form_data.company:
            details_rows += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">Компанија:</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">{form_data.company}</td>
            </tr>
            """

        if form_data.phone:
            details_rows += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">Телефон:</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">
                    <a href="tel:{form_data.phone}" style="color: #2563eb;">{form_data.phone}</a>
                </td>
            </tr>
            """

        if form_data.plan:
            details_rows += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; color: #6b7280;">План:</td>
                <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #7c3aed;">{form_data.plan.upper()}</td>
            </tr>
            """

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="margin: 0; padding: 20px; font-family: Arial, sans-serif; background-color: #f4f4f7;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <div style="background: {'linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%)' if is_enterprise else 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)'}; padding: 30px; text-align: center;">
            <h1 style="margin: 0; color: white; font-size: 24px;">
                {'🏢 Enterprise Inquiry' if is_enterprise else '📧 New Contact Message'}
            </h1>
        </div>

        <div style="padding: 30px;">
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                {details_rows}
            </table>

            <div style="margin-top: 20px; padding: 20px; background-color: #f9fafb; border-radius: 8px; border-left: 4px solid #2563eb;">
                <h3 style="margin: 0 0 10px 0; color: #374151;">Порака:</h3>
                <p style="margin: 0; color: #4b5563; white-space: pre-wrap; line-height: 1.6;">{form_data.message}</p>
            </div>

            <div style="margin-top: 30px; text-align: center;">
                <a href="mailto:{form_data.email}?subject=Re: {subject}"
                   style="display: inline-block; padding: 12px 30px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 6px; font-weight: 600;">
                    Reply to {form_data.name}
                </a>
            </div>
        </div>

        <div style="padding: 20px; background-color: #f9fafb; text-align: center; color: #6b7280; font-size: 12px;">
            This message was sent from the nabavkidata.com contact form
        </div>
    </div>
</body>
</html>
"""

        # Send to support email
        success = await postmark_service.send_email(
            to="support@nabavkidata.com",
            subject=subject,
            html_content=html_content,
            tag="contact-form",
            reply_to=form_data.email
        )

        if not success:
            logger.error(f"Failed to send contact form email from {form_data.email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send message. Please try again or email us directly."
            )

        logger.info(f"Contact form submitted by {form_data.email} (plan: {form_data.plan})")

        return {
            "success": True,
            "message": "Your message has been sent successfully!"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contact form error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred. Please try again later."
        )
