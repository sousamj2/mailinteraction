import json
import subprocess
from flask import current_app, request
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


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
    Send an HTML email. Supports GCP relay and LOCAL sending (with cross-instance relay).
    """
    sender = sender or _sender_from_request()
    mail_system = current_app.config.get('MAILSYSTEM', 'GCP')
    print(f"DEBUG: mail_system value is '{mail_system}'", flush=True)

    if mail_system == 'LOCAL':
        local_relay_url = current_app.config.get('LOCAL_MAIL_RELAY_URL')
        
        if local_relay_url:
            print(f"MAIL: Forwarding email to local relay: {local_relay_url}", flush=True)
            payload = {
                'sender': sender,
                'email_to': email_to,
                'subject': subject,
                'html_message': html_message,
            }
            try:
                response = requests.post(local_relay_url, json=payload, timeout=10)
                if response.status_code == 200:
                    print(f"MAIL: Email forwarded successfully to {email_to}.", flush=True)
                    return
                else:
                    print(f"MAIL ERROR: Local relay returned {response.status_code}: {response.text}", flush=True)
                    raise RuntimeError(f"Local email relay failed: {response.text}")
            except requests.exceptions.RequestException as e:
                print(f"MAIL ERROR: Connection to local relay failed: {e}", flush=True)
                raise RuntimeError(f"Failed to connect to local email relay: {e}")
        else:
            print(f"MAIL: Sending email locally — {sender} → {email_to}", flush=True)
            
            smtp_port = 465  # Hardcoded as in gcloud function
            if 'mjcrafts' in sender.lower():
                smtp_server = 'srv9.mychrome.pt'
                smtp_password = current_app.config.get('MAIL_PASSWORD')  # Loaded from MC_MAIL_PASSWORD
                smtp_user = sender
            else:
                smtp_server = 'webdomain02.dnscpanel.com'
                smtp_password = current_app.config.get('ALT_MAIL_PASSWORD')  # Loaded from EXPL_MAIL_PASSWORD
                smtp_user = sender

            if not smtp_server or not smtp_password:
                print("MAIL ERROR: Local SMTP credentials missing.", flush=True)
                raise RuntimeError("Local SMTP credentials missing.")

            try:
                msg = MIMEMultipart()
                msg['From'] = sender
                msg['To'] = email_to
                msg['Subject'] = subject
                msg.attach(MIMEText(html_message, 'html'))

                if smtp_port == 465:
                    with smtplib.SMTP_SSL(smtp_server, smtp_port) as smtp:
                        smtp.login(smtp_user, smtp_password)
                        smtp.send_message(msg)
                else:
                    with smtplib.SMTP(smtp_server, smtp_port) as smtp:
                        smtp.starttls()
                        smtp.login(smtp_user, smtp_password)
                        smtp.send_message(msg)
                print(f"MAIL: Email sent successfully to {email_to}.", flush=True)
                return
            except Exception as e:
                print(f"MAIL ERROR: Local send failed: {e}", flush=True)
                raise RuntimeError(f"Local email send failed: {e}")

    # Default to GCP relay
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
