"""
A robust background communication utility that manages user notifications and verification workflows using threading.
It leverages Flask-Mail to send HTML-formatted welcome messages and security codes without blocking the main application.
The service includes built-in error logging to 'email_errors.log' to track delivery failures for administrative review.
It uses dynamic template rendering to personalize emails with usernames and specific account metadata.
This module bridges the gap between the AI backend and the user experience, ensuring timely delivery of critical alerts.
"""

import threading
import os
import logging
from datetime import datetime
from flask import current_app, render_template_string
from flask_mail import Message

logger = logging.getLogger(__name__)

class EmailService:
    """Handle all email operations with background processing"""
    
    @staticmethod
    def send_verification_email(user, verification_code):
        """Send verification email in background"""
        try:
            # Get all user data we need BEFORE starting the thread
            user_data = {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'verification_code': verification_code
            }
            
            thread = threading.Thread(
                target=EmailService._send_verification_email_thread,
                args=(user_data,)
            )
            thread.daemon = True
            thread.start()
            
            current_app.logger.info(f"Started verification email thread for {user.email}")
        except Exception as e:
            current_app.logger.error(f"Failed to start email thread: {str(e)}")
    
    @staticmethod
    def _send_verification_email_thread(user_data):
        """Background thread to send verification email"""
        try:
            # Create a new app instance for this thread
            from app import create_app
            from flask_mail import Mail
            
            app = create_app()
            
            with app.app_context():
                mail = Mail(app)
                
                # Create verification URL
                verification_url = f"{app.config.get('BASE_URL', 'http://localhost:5000')}/verify-email?email={user_data['email']}"
                
                # HTML email content
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Verify Your ScorePulse AI Account</title>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            line-height: 1.6;
                            color: #333;
                            max-width: 600px;
                            margin: 0 auto;
                            padding: 20px;
                        }}
                        .container {{
                            background-color: #f9f9f9;
                            border-radius: 10px;
                            padding: 30px;
                            border: 1px solid #e0e0e0;
                        }}
                        .header {{
                            text-align: center;
                            margin-bottom: 30px;
                        }}
                        .logo {{
                            font-size: 24px;
                            font-weight: bold;
                            color: #4CAF50;
                            margin-bottom: 10px;
                        }}
                        .code-box {{
                            background-color: #fff;
                            border: 2px dashed #4CAF50;
                            border-radius: 5px;
                            padding: 15px;
                            text-align: center;
                            font-size: 28px;
                            font-weight: bold;
                            letter-spacing: 5px;
                            margin: 20px 0;
                            color: #333;
                        }}
                        .button {{
                            display: inline-block;
                            background-color: #4CAF50;
                            color: white;
                            padding: 12px 24px;
                            text-decoration: none;
                            border-radius: 5px;
                            font-weight: bold;
                            margin: 20px 0;
                        }}
                        .footer {{
                            margin-top: 30px;
                            padding-top: 20px;
                            border-top: 1px solid #e0e0e0;
                            font-size: 12px;
                            color: #666;
                            text-align: center;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <div class="logo">ScorePulse AI</div>
                            <h1>Verify Your Email Address</h1>
                        </div>
                        
                        <p>Hello <strong>{user_data['username']}</strong>,</p>
                        
                        <p>Thank you for registering with ScorePulse AI! To complete your registration and start making predictions, please verify your email address.</p>
                        
                        <p>Your verification code is:</p>
                        
                        <div class="code-box">{user_data['verification_code']}</div>
                        
                        <p>Enter this code on the verification page to activate your account.</p>
                        
                        <p style="text-align: center;">
                            <a href="{verification_url}" class="button">
                                Verify Your Email
                            </a>
                        </p>
                        
                        <p><strong>Note:</strong> This code will expire in 15 minutes for security reasons.</p>
                        
                        <p>If you didn't create an account with ScorePulse AI, please ignore this email.</p>
                        
                        <div class="footer">
                            <p>This email was sent by ScorePulse AI<br>
                            Do not reply to this email. For support, contact: <a href="mailto:support@scorepulse.ai">support@scorepulse.ai</a></p>
                            <p>© {datetime.now().year} ScorePulse AI. All rights reserved.</p>
                        </div>
                    </div>
                </body>
                </html>
                """
                
                # Plain text version
                text_content = f"""
                Verify Your ScorePulse AI Account
                
                Hello {user_data['username']},
                
                Thank you for registering with ScorePulse AI! To complete your registration and start making predictions, please verify your email address.
                
                Your verification code is: {user_data['verification_code']}
                
                Enter this code on the verification page to activate your account.
                
                Verification URL: {verification_url}
                
                Note: This code will expire in 15 minutes for security reasons.
                
                If you didn't create an account with ScorePulse AI, please ignore this email.
                
                ---
                This email was sent by ScorePulse AI
                Do not reply to this email. For support, contact: support@scorepulse.ai
                """
                
                # Create message
                msg = Message(
                    subject='🔐 Verify Your ScorePulse AI Account',
                    sender=app.config.get('MAIL_DEFAULT_SENDER', 'wemba12321@gmail.com'),
                    recipients=[user_data['email']]
                )
                
                # Add both HTML and plain text versions
                msg.html = html_content
                msg.body = text_content
                
                # Send email
                mail.send(msg)
                
                app.logger.info(f"✅ Verification email sent to {user_data['email']}")
                
        except Exception as e:
            # Log error to a file since we might not have app context
            error_msg = f"{datetime.now()}: Failed to send verification email to {user_data.get('email', 'unknown')}: {str(e)}\n"
            logger.error(error_msg)
            
            # Also write to file for debugging
            with open('email_errors.log', 'a') as f:
                f.write(error_msg)
    
    @staticmethod
    def send_welcome_email(user):
        """Send welcome email after successful verification"""
        try:
            # Get all user data we need BEFORE starting the thread
            user_data = {
                'id': user.id,
                'email': user.email,
                'username': user.username
            }
            
            thread = threading.Thread(
                target=EmailService._send_welcome_email_thread,
                args=(user_data,)
            )
            thread.daemon = True
            thread.start()
            
            current_app.logger.info(f"Started welcome email thread for {user.email}")
        except Exception as e:
            current_app.logger.error(f"Failed to start welcome email thread: {str(e)}")
    
    @staticmethod
    def _send_welcome_email_thread(user_data):
        """Background thread to send welcome email"""
        try:
            from app import create_app
            from flask_mail import Mail
            
            app = create_app()
            
            with app.app_context():
                mail = Mail(app)
                
                # Create URLs directly
                base_url = app.config.get('BASE_URL', 'http://localhost:5000')
                dashboard_url = f"{base_url}/dashboard"
                predict_url = f"{base_url}/predict"
                
                # Welcome email HTML content
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Welcome to ScorePulse AI! 🎉</title>
                </head>
                <body>
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; font-family: Arial, sans-serif;">
                        <h1 style="color: #4CAF50; text-align: center;">🎉 Welcome to ScorePulse AI!</h1>
                        <p>Hello <strong>{user_data['username']}</strong>,</p>
                        <p>Thank you for verifying your email! Your ScorePulse AI account is now fully activated and ready to use.</p>
                        
                        <h3>Get Started:</h3>
                        <ul>
                            <li><a href="{predict_url}">Make Your First Prediction</a></li>
                            <li><a href="{dashboard_url}">View Your Dashboard</a></li>
                        </ul>
                        
                        <p>Need help? Contact us at <a href="mailto:support@scorepulse.ai">support@scorepulse.ai</a></p>
                        
                        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; font-size: 12px; color: #666; text-align: center;">
                            <p>© {datetime.now().year} ScorePulse AI. All rights reserved.</p>
                        </div>
                    </div>
                </body>
                </html>
                """
                
                # Create message
                msg = Message(
                    subject='🎉 Welcome to ScorePulse AI!',
                    sender=app.config.get('MAIL_DEFAULT_SENDER', 'noreply@scorepulse.ai'),
                    recipients=[user_data['email']]
                )
                
                msg.html = html_content
                msg.body = f"Welcome {user_data['username']}! Your ScorePulse AI account is now active."
                
                # Send email
                mail.send(msg)
                
                app.logger.info(f"✅ Welcome email sent to {user_data['email']}")
                
        except Exception as e:
            error_msg = f"{datetime.now()}: Failed to send welcome email: {str(e)}\n"
            logger.error(error_msg)
            with open('email_errors.log', 'a') as f:
                f.write(error_msg)
