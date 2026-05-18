from flask import Blueprint, request, jsonify
from mailinteraction.send_email import send_email

bp_mail_relay = Blueprint("mail_relay", __name__, url_prefix="/mail_relay")

@bp_mail_relay.route("/send", methods=["POST"])
def relay_send_email():
    """
    Endpoint to receive email sending commands from other instances.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
        
    subject = data.get("subject")
    email_to = data.get("email_to")
    html_message = data.get("html_message")
    sender = data.get("sender")
    
    if not all([subject, email_to, html_message]):
        return jsonify({"error": "Missing required fields (subject, email_to, html_message)"}), 400
        
    try:
        # Call send_email.
        # Since we are on EC2-1, MAILSYSTEM should be 'LOCAL' and LOCAL_MAIL_RELAY_URL should NOT be set.
        # So it will send the email using smtplib.
        send_email(subject, email_to, html_message, sender=sender)
        return jsonify({"status": "success", "message": "Email sent"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
