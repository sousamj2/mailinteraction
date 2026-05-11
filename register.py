from flask import (
    Blueprint,
    request,
    session,
    redirect,
    url_for,
    flash,
    current_app,
    render_template,
    render_template_string,
)
from mailinteraction.registration_token import generate_token, confirm_token
from mailinteraction.send_email import send_email
from markupsafe import Markup
from mysql.DBhelpers import (
    insertNewBlacklistEmail,
    insertNewBlacklistIP,
    isEmailBlacklisted,
    insertNewRegistrationToken,
    getRegistrationToken,
    getRegistrationTokenByEmailOrIP,
    deleteRegistrationToken,
    deleteExpiredRegistrationTokens,
    isIpBlacklisted,
)
import re


bp_register = Blueprint("register", __name__, url_prefix="/register")


@bp_register.route("/", methods=["GET", "POST"])
def request_confirmation():
    """
    Handles the initial step of user registration by requesting email confirmation.
    """
    if request.method == "POST":
        deleteExpiredRegistrationTokens()
        email = request.form.get("email")

        if email:
            email = email.strip().lower()

        if not email:
            flash("Please enter a valid email address.")
            return redirect(url_for("register.request_confirmation"))

        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            flash("Invalid email format. Please enter a valid email address.")
            return redirect(url_for("register.request_confirmation"))

        ip_addr = request.headers.get("X-Real-IP") or request.remote_addr or "127.0.0.1"

        if ip_addr and isIpBlacklisted(ip_addr):
            flash("This IP address is blacklisted from making more requests.")
            return redirect(url_for("register.request_confirmation"))

        if isEmailBlacklisted(email):
            if ip_addr:
                insertNewBlacklistIP(ip_addr)
            flash("This email address is blacklisted from receiving more requests.")
            return redirect(url_for("register.request_confirmation"))

        if getRegistrationTokenByEmailOrIP(email, ip_addr):
            flash("A request for a new account has already been made for this IP/Email.")
            return redirect(url_for("register.request_confirmation"))

        token = generate_token(email)
        success = insertNewRegistrationToken(token, ip_addr, email)
        if success != "Insert successful":
             flash("An error occurred while processing your request. Please try again later.")
             print(f"Error inserting registration token: {success}")
             return redirect(url_for("register.request_confirmation"))

        confirm_url = url_for("register.confirm_email", token=token, _external=True)
        unsubscribe_url = url_for("register.unsubscribe", token=token, _external=True)

        subject = "Confirm Your Email Address"
        html_message = f"""
        <p>To confirm your email address and create an account, please use the following link:</p>
        <p><a href="{confirm_url}">{confirm_url}</a></p>
        <p>This confirmation link is valid for 1 hour.</p>
        <p>If you did not make this request, you can ignore this email or <a href="{unsubscribe_url}">request removal from our database.</a></p>
        """

        send_email(subject, email, html_message)
        flash(f"A confirmation email has been sent to your address (from {current_app.config['MAIL_DEFAULT_SENDER']}).")
        flash("Please check your inbox and spam/junk folder.")
        return redirect(url_for("register.request_confirmation"))

    return render_template(
        "index.html",
        admin_email=current_app.config["ADMIN_EMAIL"],
        user=session.get("userinfo"),
        page_title="Mostly Jovial Crafters", 
        title="Mostly Jovial Crafters",
        content_template="content/request_new_user.html",
    )


@bp_register.route("/confirm/<token>")
def confirm_email(token):
    """
    Confirms a user's email address using a secure token.
    """
    token_data = getRegistrationToken(token)
    if not token_data:
        flash("Invalid or expired confirmation link.")
        return redirect(url_for("register.request_confirmation"))

    email = confirm_token(token)
    if not email or email != token_data["email"]:
        flash("Invalid or expired confirmation link.")
        deleteRegistrationToken(token)
        return redirect(url_for("register.request_confirmation"))

    deleteRegistrationToken(token)

    return render_template_string(
        """
        <form id="postform" method="post" action="{{ url_for('signup.signup') }}">
            <input type="hidden" name="email" value="{{ email }}">
        </form>
        <script type="text/javascript">
            document.getElementById('postform').submit();
        </script>
    """,
        email=email,
    )


@bp_register.route("/unsubscribe/<token>")
def unsubscribe(token):
    """
    Handles user unsubscribe requests.
    """
    token_data = getRegistrationToken(token)
    if not token_data:
        flash("Invalid or expired removal link.")
        flash("Please request a new one (requires a new registration request with the same email).")
        return redirect(url_for("signin.signin"))

    email = token_data["email"]
    ip = token_data["ip_address"]

    if email:
        insertNewBlacklistEmail(email)
    if ip:
        insertNewBlacklistIP(ip)

    deleteRegistrationToken(token)

    flash("This email has been removed from our database and will not receive any more requests.")
    flash("The IP address has also been blocked from making more requests. Thank you for helping us combat spam.")
    return redirect(url_for("signin.signin"))
