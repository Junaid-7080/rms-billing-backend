"""
Email service
Handles sending verification, notification, and transactional emails
"""
from typing import Optional
import logging
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr

from app.core.config import settings

logger = logging.getLogger(__name__)

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

fastmail = FastMail(conf)


async def send_verification_email(email: EmailStr, token: str) -> bool:
    """
    Send email verification link to user
    """
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #4F46E5;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9fafb;
                padding: 30px;
                border-radius: 0 0 5px 5px;
            }}
            .button {{
                display: inline-block;
                background-color: #4F46E5;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{
                text-align: center;
                margin-top: 20px;
                color: #6b7280;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Welcome to RMS Billing!</h1>
            </div>
            <div class="content">
                <p>Thank you for registering with RMS Billing Software.</p>
                <p>Please click the button below to verify your email address and activate your 14-day free trial:</p>
                <p style="text-align: center;">
                    <a href="{verification_url}" class="button">Verify Email Address</a>
                </p>
                <p>Or copy and paste this link in your browser:</p>
                <p style="word-break: break-all; color: #4F46E5;">{verification_url}</p>
                <p><strong>This link will expire in 24 hours.</strong></p>
                <p>If you didn't create an account, you can safely ignore this email.</p>
            </div>
            <div class="footer">
                <p>© 2024 RMS Billing Software. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Verify Your Email - RMS Billing",
        recipients=[email],
        body=html_content,
        subtype="html"
    )
    
    try:
        await fastmail.send_message(message)
        logger.info(f"Verification email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {str(e)}")
        return False


async def send_password_reset_email(email: EmailStr, token: str) -> bool:
    """
    Send password reset link to user
    """
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #4F46E5;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9fafb;
                padding: 30px;
                border-radius: 0 0 5px 5px;
            }}
            .button {{
                display: inline-block;
                background-color: #4F46E5;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .warning {{
                background-color: #fef3c7;
                border-left: 4px solid #f59e0b;
                padding: 10px;
                margin: 15px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Reset Your Password</h1>
            </div>
            <div class="content">
                <p>We received a request to reset your password for your RMS Billing account.</p>
                <p>Click the button below to reset your password:</p>
                <p style="text-align: center;">
                    <a href="{reset_url}" class="button">Reset Password</a>
                </p>
                <p>Or copy and paste this link in your browser:</p>
                <p style="word-break: break-all; color: #4F46E5;">{reset_url}</p>
                <div class="warning">
                    <p><strong>⚠️ Security Notice:</strong></p>
                    <ul>
                        <li>This link will expire in 1 hour</li>
                        <li>If you didn't request this, please ignore this email</li>
                        <li>Your password won't change until you create a new one</li>
                    </ul>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Reset Your Password - RMS Billing",
        recipients=[email],
        body=html_content,
        subtype="html"
    )
    
    try:
        await fastmail.send_message(message)
        logger.info(f"Password reset email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {str(e)}")
        return False


async def send_welcome_email(email: EmailStr, first_name: str) -> bool:
    """
    Send welcome email after email verification
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #10b981;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 5px 5px 0 0;
            }}
            .content {{
                background-color: #f9fafb;
                padding: 30px;
                border-radius: 0 0 5px 5px;
            }}
            .button {{
                display: inline-block;
                background-color: #4F46E5;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .features {{
                background-color: white;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Welcome to RMS Billing!</h1>
            </div>
            <div class="content">
                <p>Hi {first_name},</p>
                <p>Your email has been verified successfully! Your 14-day free trial is now active.</p>
                <div class="features">
                    <h3>What you can do:</h3>
                    <ul>
                        <li>✨ Create and manage invoices</li>
                        <li>📊 Track payments and receipts</li>
                        <li>👥 Manage customers</li>
                        <li>📈 View business analytics</li>
                        <li>🧾 Generate GST-compliant reports</li>
                    </ul>
                </div>
                <p style="text-align: center;">
                    <a href="{settings.FRONTEND_URL}/login" class="button">Start Using RMS</a>
                </p>
                <p>Need help getting started? Check out our documentation or contact support.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    message = MessageSchema(
        subject="Welcome to RMS Billing! 🎉",
        recipients=[email],
        body=html_content,
        subtype="html"
    )
    
    try:
        await fastmail.send_message(message)
        logger.info(f"Welcome email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send welcome email to {email}: {str(e)}")
        return False