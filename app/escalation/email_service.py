"""
Email notification service for escalation alerts.
Sends notifications to human support agents when requests are escalated.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from datetime import datetime
import os

from dotenv import load_dotenv
load_dotenv()


def get_email_config() -> Dict[str, Any]:
    """Load email configuration from environment."""
    return {
        "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", "587")),
        "smtp_user": os.getenv("SMTP_USER", ""),
        "smtp_password": os.getenv("SMTP_PASSWORD", ""),
        "sender_email": os.getenv("SENDER_EMAIL", ""),
        "sender_name": os.getenv("SENDER_NAME", "AI Support System"),
    }


def is_email_configured() -> bool:
    """Check if email is properly configured."""
    config = get_email_config()
    return bool(config["smtp_user"] and config["smtp_password"] and config["sender_email"])


class EscalationEmailService:
    """
    Handles sending escalation notification emails to support agents.
    
    When a request is escalated, this service notifies the assigned
    human agent with relevant details about the customer request.
    """
    
    def send_escalation_notification(
        self,
        agent_email: str,
        agent_name: str,
        ticket_id: str,
        user_id: str,
        user_message: str,
        intent: str,
        escalation_reason: str,
        client_id: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Send escalation notification email to support agent.
        
        Args:
            agent_email: Email address of the support agent
            agent_name: Name of the support agent
            ticket_id: Unique ticket identifier
            user_id: Customer's user ID
            user_message: Original customer message
            intent: Detected intent category
            escalation_reason: Why request was escalated
            client_id: Client/tenant identifier
            
        Returns:
            Dict with status and details
        """
        config = get_email_config()
        
        if not is_email_configured():
            print(f"📧 [SIMULATED] Escalation email to {agent_name} ({agent_email})")
            print(f"   Ticket: {ticket_id} | Intent: {intent}")
            print(f"   Message: {user_message[:100]}...")
            return {
                "sent": False,
                "simulated": True,
                "reason": "SMTP not configured",
                "agent_email": agent_email,
                "ticket_id": ticket_id
            }
        
        try:
            subject = f"[URGENT] Support Escalation - Ticket #{ticket_id}"
            
            body = self._build_email_body(
                agent_name=agent_name,
                ticket_id=ticket_id,
                user_id=user_id,
                user_message=user_message,
                intent=intent,
                escalation_reason=escalation_reason,
                client_id=client_id
            )
            
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{config['sender_name']} <{config['sender_email']}>"
            msg["To"] = agent_email
            
            msg.attach(MIMEText(body, "html"))
            
            with smtplib.SMTP(config["smtp_host"], config["smtp_port"]) as server:
                server.starttls()
                server.login(config["smtp_user"], config["smtp_password"])
                server.send_message(msg)
            
            print(f"✅ Escalation email sent to {agent_name} ({agent_email})")
            
            return {
                "sent": True,
                "agent_email": agent_email,
                "ticket_id": ticket_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Failed to send escalation email: {e}")
            return {
                "sent": False,
                "error": str(e),
                "agent_email": agent_email,
                "ticket_id": ticket_id
            }
    
    def _build_email_body(
        self,
        agent_name: str,
        ticket_id: str,
        user_id: str,
        user_message: str,
        intent: str,
        escalation_reason: str,
        client_id: str
    ) -> str:
        """Build HTML email body for escalation notification."""
        
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #dc3545; color: white; padding: 15px; border-radius: 5px 5px 0 0; }}
        .content {{ background: #f8f9fa; padding: 20px; border: 1px solid #ddd; }}
        .field {{ margin-bottom: 15px; }}
        .label {{ font-weight: bold; color: #555; }}
        .value {{ background: white; padding: 10px; border-radius: 3px; margin-top: 5px; }}
        .message-box {{ background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; }}
        .footer {{ font-size: 12px; color: #666; margin-top: 20px; padding-top: 15px; border-top: 1px solid #ddd; }}
        .urgent {{ color: #dc3545; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2 style="margin: 0;">🚨 Support Escalation Required</h2>
        </div>
        <div class="content">
            <p>Hello {agent_name},</p>
            <p class="urgent">A support request requires your immediate attention.</p>
            
            <div class="field">
                <div class="label">Ticket ID</div>
                <div class="value">{ticket_id}</div>
            </div>
            
            <div class="field">
                <div class="label">Customer ID</div>
                <div class="value">{user_id}</div>
            </div>
            
            <div class="field">
                <div class="label">Client/Tenant</div>
                <div class="value">{client_id}</div>
            </div>
            
            <div class="field">
                <div class="label">Detected Intent</div>
                <div class="value">{intent}</div>
            </div>
            
            <div class="field">
                <div class="label">Escalation Reason</div>
                <div class="value">{escalation_reason}</div>
            </div>
            
            <div class="field">
                <div class="label">Customer Message</div>
                <div class="message-box">{user_message}</div>
            </div>
            
            <p>Please respond to this customer as soon as possible.</p>
        </div>
        <div class="footer">
            <p>This is an automated notification from the AI Support System.</p>
            <p>Timestamp: {timestamp}</p>
        </div>
    </div>
</body>
</html>
"""


_email_service: Optional[EscalationEmailService] = None


def get_email_service() -> EscalationEmailService:
    """Get the email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EscalationEmailService()
    return _email_service


def send_escalation_email(
    agent_email: str,
    agent_name: str,
    ticket_id: str,
    user_id: str,
    user_message: str,
    intent: str,
    escalation_reason: str,
    client_id: str = "unknown"
) -> Dict[str, Any]:
    """Convenience function to send escalation email."""
    service = get_email_service()
    return service.send_escalation_notification(
        agent_email=agent_email,
        agent_name=agent_name,
        ticket_id=ticket_id,
        user_id=user_id,
        user_message=user_message,
        intent=intent,
        escalation_reason=escalation_reason,
        client_id=client_id
    )
