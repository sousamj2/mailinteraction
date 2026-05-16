import json
import subprocess
from flask import current_app, request
import requests


def _get_identity_token(url):
    """
    Get a Google ID token to authenticate the request to Cloud Run/Functions.
    Tries to use gcloud CLI as a fallback since this is running on an EC2 instance
    where gcloud might be already authenticated.
    """
    try:
        # Try using gcloud command line if available (user confirmed this works in terminal)
        result = subprocess.run(
            ['gcloud', 'auth', 'print-identity-token'],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"MAIL WARNING: Failed to get identity token via gcloud: {e}", flush=True)
        
        # Alternative: Try metadata server if running on GCP (not our case, but good to have)
        # Or try google-auth library if installed
        try:
            import google.auth
            import google.auth.transport.requests
            import google.oauth2.id_token
            
            auth_req = google.auth.transport.requests.Request()
            return google.oauth2.id_token.fetch_id_token(auth_req, url)
        except ImportError:
            print("MAIL ERROR: google-auth library not installed and gcloud failed.", flush=True)
            return None
        except Exception as e2:
            print(f"MAIL ERROR: Failed to get identity token via google-auth: {e2}", flush=True)
            return None


def _sender_from_request():
    """Derive the sender address from the current request domain."""
    try:
        host = request.host.split(':')[0]  # Remove port
        parts = host.split('.')
        # Extract base domain (last 2 parts for TLDs like .pt)
        if len(parts) >= 2:
            base_domain = '.'.join(parts[-2:])
        else:
            base_domain = host
        return f"no-reply@{base_domain}"
    except Exception:
        return current_app.config.get('MAIL_DEFAULT_SENDER', 'no-reply@mjcrafts.pt')


def send_email(subject: str, email_to: str, html_message: str, sender: str = None,
               server: str = None, port: int = None, password: str = None) -> None:
    """
    Send an HTML email by invoking a Google Cloud Function relay.
    
    This is used to bypass IPv6 connectivity issues on AWS EC2 by offloading 
    the SMTP connection to a GCP function that has IPv4 egress.
    """
    sender = sender or _sender_from_request()
    relay_url = current_app.config.get('GOOGLE_MAIL_RELAY_URL')
    
    if not relay_url:
        print("MAIL ERROR: GOOGLE_MAIL_RELAY_URL not configured.", flush=True)
        raise RuntimeError("Email relay URL not configured.")

    print(f"MAIL: Relaying email via GCF — {sender} → {email_to}", flush=True)

    token = _get_identity_token(relay_url)
    if not token:
        print("MAIL ERROR: Could not obtain identity token for GCP.", flush=True)
        raise RuntimeError("Failed to authenticate with Google Cloud.")

    payload = {
        'sender': sender,
        'recipient': email_to,
        'subject': subject,
        'html_message': html_message,
    }

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    try:
        # Increase timeout as SMTP over relay can be slow
        response = requests.post(relay_url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            print(f"MAIL: Email sent successfully to {email_to}.", flush=True)
        else:
            error_data = response.json() if response.content else {}
            error_msg = error_data.get('error', response.text)
            print(f"MAIL ERROR: Relay returned {response.status_code}: {error_msg}", flush=True)
            raise RuntimeError(f"Email relay failed: {error_msg}")
            
    except requests.exceptions.RequestException as e:
        print(f"MAIL ERROR: Connection to relay failed: {e}", flush=True)
        raise RuntimeError(f"Failed to connect to email relay: {e}")
