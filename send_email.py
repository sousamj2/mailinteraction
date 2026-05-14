from flask_mail import Message
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .extensions import mail
from flask import current_app


def send_email(subject: str, email_to: str, html_message: str, sender: str = None, 
               server: str = None, port: int = None, password: str = None) -> None:
    """Send an HTML email using the shared Mail extension or a direct SMTP connection.
    
    If 'server' is provided, it uses smtplib for a direct connection (useful for alternative domains).
    Otherwise, it uses the default Flask-Mail extension.
    """
    if server:
        # Use direct SMTP for alternative server
        try:
            msg = MIMEMultipart()
            msg['From'] = sender or current_app.config['MAIL_DEFAULT_SENDER']
            msg['To'] = email_to
            msg['Subject'] = subject
            msg.attach(MIMEText(html_message, 'html'))

            # Assuming SSL for port 465, else STARTTLS for others
            if port == 465:
                with smtplib.SMTP_SSL(server, port) as smtp:
                    smtp.login(msg['From'], password or current_app.config['MAIL_PASSWORD'])
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(server, port or 587) as smtp:
                    smtp.starttls()
                    smtp.login(msg['From'], password or current_app.config['MAIL_PASSWORD'])
                    smtp.send_message(msg)
        except Exception as e:
            print(f"Error sending alternative email: {e}")
            raise
    else:
        # Use default Flask-Mail extension
        with current_app.app_context():
            msg = Message(subject=subject, recipients=[email_to], sender=sender)
            msg.html = html_message
            mail.send(msg)
