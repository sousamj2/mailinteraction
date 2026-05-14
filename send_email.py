import json
import boto3
from flask import current_app, request


# Lazy-initialised Lambda client (reused across calls)
_lambda_client = None

def _get_lambda_client():
    """Get or create the boto3 Lambda client."""
    global _lambda_client
    if _lambda_client is None:
        region = current_app.config.get('AWS_REGION', 'eu-south-2')
        _lambda_client = boto3.client('lambda', region_name=region)
    return _lambda_client


def _sender_from_request():
    """Derive the sender address from the current request domain.

    Examples:
        mc.mjcrafts.pt       → no-reply@mjcrafts.pt
        explicacoeslisboa.pt → no-reply@explicacoeslisboa.pt
        localhost:8081       → no-reply@localhost
    """
    host = request.host.split(':')[0]  # Remove port
    parts = host.split('.')
    # Extract base domain (last 2 parts for TLDs like .pt)
    if len(parts) >= 2:
        base_domain = '.'.join(parts[-2:])
    else:
        base_domain = host
    return f"no-reply@{base_domain}"


def send_email(subject: str, email_to: str, html_message: str, sender: str = None,
               server: str = None, port: int = None, password: str = None) -> None:
    """Send an HTML email by invoking the email-sending AWS Lambda function.

    The Lambda determines the SMTP server and retrieves credentials from
    AWS SSM Parameter Store based on the sender address. This allows
    IPv6-only EC2 instances to send emails through IPv4-only SMTP servers.

    Args:
        subject:      Email subject line.
        email_to:     Recipient email address.
        html_message: HTML body of the email.
        sender:       Sender address; determines which SMTP config the Lambda uses.
                      If not provided, derived from request domain as no-reply@DOMAIN.
        server:       Unused — retained for backward compatibility.
        port:         Unused — retained for backward compatibility.
        password:     Unused — retained for backward compatibility.
    """
    sender = sender or _sender_from_request()

    payload = {
        'sender': sender,
        'recipient': email_to,
        'subject': subject,
        'html_message': html_message,
    }

    function_name = current_app.config.get('EMAIL_LAMBDA_FUNCTION', 'send-email')

    print(f"MAIL: Invoking Lambda '{function_name}' — {sender} → {email_to}", flush=True)

    response = _get_lambda_client().invoke(
        FunctionName=function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload),
    )

    # Parse the Lambda response
    response_payload = json.loads(response['Payload'].read().decode('utf-8'))
    status_code = response_payload.get('statusCode', 500)

    if status_code != 200:
        body = response_payload.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
        error_msg = body.get('error', 'Unknown Lambda error')
        print(f"MAIL ERROR: {error_msg}", flush=True)
        raise RuntimeError(f"Email sending failed: {error_msg}")

    print(f"MAIL: Email sent successfully to {email_to}.", flush=True)
