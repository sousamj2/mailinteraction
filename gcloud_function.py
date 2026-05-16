import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import functions_framework

def send_email_via_smtp(sender, recipient, subject, html_message, smtp_server, smtp_port, smtp_password):
    """Logic to send email via SMTP."""
    try:
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(html_message, 'html'))

        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port) as smtp:
                smtp.login(sender, smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, smtp_port) as smtp:
                smtp.starttls()
                smtp.login(sender, smtp_password)
                smtp.send_message(msg)
        return True, "Email sent successfully"
    except Exception as e:
        return False, f"Error sending email: {str(e)}"

@functions_framework.http
def email_handler(request):
    # Parse the incoming request from your EC2 instance
    request_json = request.get_json(silent=True)
    
    if not request_json:
        return json.dumps({"error": "Invalid JSON body"}), 400

    sender = request_json.get('sender')
    recipient = request_json.get('recipient')
    subject = request_json.get('subject')
    html_message = request_json.get('html_message')

    # Basic validation
    if not all([sender, recipient, subject, html_message]):
        return json.dumps({"error": "Missing required parameters: sender, recipient, subject, html_message"}), 400

    # 1. Load the central password configuration from Secret Manager (mapped to an env var)
    pass_config_raw = os.environ.get('PASS_CONFIG')
    if not pass_config_raw:
        return json.dumps({"error": "PASS_CONFIG environment variable is not set"}), 500
    
    try:
        pass_config = json.loads(pass_config_raw)
    except json.JSONDecodeError:
        return json.dumps({"error": "Failed to parse PASS_CONFIG as JSON"}), 500

    # 2. Select SMTP settings and retrieve the specific password from the JSON
    smtp_port = 465
    if 'mjcrafts' in sender.lower():
        smtp_server = 'srv9.mychrome.pt'
        smtp_password = pass_config.get('MC_MAIL_PASSWORD')
    else:
        smtp_server = 'webdomain02.dnscpanel.com'
        smtp_password = pass_config.get('EXPL_MAIL_PASSWORD')

    if not smtp_password:
        return json.dumps({"error": "Required SMTP password not found in PASS_CONFIG"}), 500

    # 3. Send the email
    success, message = send_email_via_smtp(
        sender, recipient, subject, html_message,
        smtp_server, smtp_port, smtp_password
    )

    result = {
        "message": message,
        "email_sent": success,
        "recipient": recipient,
        "sender": sender
    }

    return json.dumps(result), 200 if success else 500


# {
#   "sender": "no-reply@mjcrafts.pt",
#   "recipient": "tundra.trail6137@eagereverest.com",
#   "subject": "Test email subject",
#   "html_message": "Test message"
# }