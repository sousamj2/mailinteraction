from flask_mail import Message
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .extensions import mail
from flask import current_app


def _needs_ipv4_allocation():
    """Check if temporary IPv4 allocation is needed for SMTP connectivity.
    
    Controlled by the MAIL_ALLOCATE_IPV4 config flag (default: False).
    When True, an Elastic IP is temporarily allocated before sending
    and released afterwards — needed for IPv6-only EC2 instances
    connecting to IPv4-only SMTP servers.
    """
    return current_app.config.get("MAIL_ALLOCATE_IPV4", False)


def send_email(subject: str, email_to: str, html_message: str, sender: str = None, 
               server: str = None, port: int = None, password: str = None) -> None:
    """Send an HTML email using the shared Mail extension or a direct SMTP connection.
    
    If MAIL_ALLOCATE_IPV4 is enabled in the app config, a temporary Elastic IP
    is allocated before sending and released afterwards. This is required for
    IPv6-only EC2 instances connecting to IPv4-only SMTP servers.
    
    If 'server' is provided, it uses smtplib for a direct connection (useful for alternative domains).
    Otherwise, it uses the default Flask-Mail extension.
    """
    allocated = False

    if _needs_ipv4_allocation():
        from .allocate_ipv4 import allocate_and_associate_eip
        print("MAIL: Allocating temporary IPv4 for SMTP...", flush=True)
        result = allocate_and_associate_eip()
        if "error" in result:
            raise ConnectionError(f"Failed to allocate IPv4 for email: {result['error']}")
        allocated = True
        print(f"MAIL: IPv4 {result['public_ip']} allocated successfully.", flush=True)

    try:
        _do_send(subject, email_to, html_message, sender, server, port, password)
    finally:
        if allocated:
            from .release_ipv4 import release_eip
            print("MAIL: Releasing temporary IPv4...", flush=True)
            release_result = release_eip()
            if "error" in release_result:
                print(f"MAIL WARNING: Failed to release IPv4: {release_result['error']}", flush=True)
            else:
                print("MAIL: IPv4 released successfully.", flush=True)


def _do_send(subject, email_to, html_message, sender, server, port, password):
    """Internal: perform the actual email send."""
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
