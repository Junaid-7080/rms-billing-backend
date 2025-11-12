"""
Email service with optional configuration
"""
import os
from typing import Optional
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
import logging

logger = logging.getLogger(__name__)

# Get email settings from environment with defaults
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM")
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() == "true"

# Check if email is configured
EMAIL_ENABLED = all([MAIL_USERNAME, MAIL_PASSWORD, MAIL_FROM])

# Only create config if email is enabled
if EMAIL_ENABLED:
    try:
        conf = ConnectionConfig(
            MAIL_USERNAME=MAIL_USERNAME,
            MAIL_PASSWORD=MAIL_PASSWORD,
            MAIL_FROM=MAIL_FROM,
            MAIL_PORT=MAIL_PORT,
            MAIL_SERVER=MAIL_SERVER,
            MAIL_STARTTLS=MAIL_USE_TLS,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True
        )
        fm = FastMail(conf)
        logger.info("Email service initialized successfully")
    except Exception as e:
        EMAIL_ENABLED = False
        fm = None
        logger.warning(f"Email service initialization failed: {e}")
else:
    fm = None
    logger.warning("Email service disabled - missing configuration")


async def send_verification_email(email: str, token: str) -> bool:
    """
    Send verification email
    Returns True if sent successfully, False otherwise
    """
    if not EMAIL_ENABLED or fm is None:
        logger.warning(f"Email not sent to {email} - service disabled")
        # In production, you might want to log this to a queue for later processing
        return False
    
    try:
        # Your verification URL
        verification_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/verify?token={token}"
        
        message = MessageSchema(
            subject="Verify Your Email",
            recipients=[email],
            body=f"""
            <html>
                <body>
                    <h2>Welcome to Invoice App!</h2>
                    <p>Please click the link below to verify your email:</p>
                    <a href="{verification_url}">Verify Email</a>
                    <p>Or copy this link: {verification_url}</p>
                    <p>This link will expire in 24 hours.</p>
                </body>
            </html>
            """,
            subtype="html"
        )
        
        await fm.send_message(message)
        logger.info(f"Verification email sent to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {email}: {str(e)}")
        return False


async def send_password_reset_email(email: str, token: str) -> bool:
    """
    Send password reset email
    Returns True if sent successfully, False otherwise
    """
    if not EMAIL_ENABLED or fm is None:
        logger.warning(f"Password reset email not sent to {email} - service disabled")
        return False
    
    try:
        reset_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/reset-password?token={token}"
        
        message = MessageSchema(
            subject="Reset Your Password",
            recipients=[email],
            body=f"""
            <html>
                <body>
                    <h2>Password Reset Request</h2>
                    <p>Click the link below to reset your password:</p>
                    <a href="{reset_url}">Reset Password</a>
                    <p>Or copy this link: {reset_url}</p>
                    <p>This link will expire in 1 hour.</p>
                    <p>If you didn't request this, please ignore this email.</p>
                </body>
            </html>
            """,
            subtype="html"
        )
        
        await fm.send_message(message)
        logger.info(f"Password reset email sent to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {str(e)}")
        return False


async def send_invoice_email(email: str, invoice_data: dict) -> bool:
    """
    Send invoice email
    Returns True if sent successfully, False otherwise
    """
    if not EMAIL_ENABLED or fm is None:
        logger.warning(f"Invoice email not sent to {email} - service disabled")
        return False
    
    try:
        message = MessageSchema(
            subject=f"Invoice #{invoice_data.get('invoice_number', 'N/A')}",
            recipients=[email],
            body=f"""
            <html>
                <body>
                    <h2>Invoice #{invoice_data.get('invoice_number', 'N/A')}</h2>
                    <p>Thank you for your business!</p>
                    <p>Amount: ₹{invoice_data.get('total_amount', 0)}</p>
                    <p>Due Date: {invoice_data.get('due_date', 'N/A')}</p>
                </body>
            </html>
            """,
            subtype="html"
        )
        
        await fm.send_message(message)
        logger.info(f"Invoice email sent to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send invoice email to {email}: {str(e)}")
        return False