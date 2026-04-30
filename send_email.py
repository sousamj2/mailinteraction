from flask_mail import Message
from .extensions import mail
from flask import current_app


def send_email(subject: str, email_to: str, html_message: str) -> None:
    """Send an HTML email using the shared Mail extension.

    This is a simple helper (no blueprint). Call it from your application code
    or background jobs: `from mailinteraction import send_email`.
    """
    # print()
    # print(current_app.config)
    # print()
    # print(mail.state)
    # print()
    with current_app.app_context():
        msg = Message(subject=subject, recipients=[email_to])
        msg.html = html_message
        mail.send(msg)
