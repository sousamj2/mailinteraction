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
    insertNewBlacklistedEmail,
    insertNewBlacklistedIP,
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
            flash("Por favor insira um endereço de email válido.")
            return redirect(url_for("register.request_confirmation"))

        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            flash("Formato de email inválido. Por favor, insira um endereço de email válido.")
            return redirect(url_for("register.request_confirmation"))

        ip_addr = request.headers.get("X-Real-IP") or request.remote_addr or "127.0.0.1"

        if ip_addr and isIpBlacklisted(ip_addr):
            flash("Este IP não pode fazer mais pedidos.")
            return redirect(url_for("register.request_confirmation"))

        if isEmailBlacklisted(email):
            if ip_addr:
                insertNewBlacklistedIP(ip_addr)
            flash("Este endereço de email não poderá receber mais pedidos.")
            return redirect(url_for("register.request_confirmation"))

        if getRegistrationTokenByEmailOrIP(email, ip_addr):
            flash("Este ip/email já fez pedido de uma conta nova.")
            return redirect(url_for("register.request_confirmation"))

        token = generate_token(email)
        success = insertNewRegistrationToken(token, ip_addr, email)
        if success != "Insert successful":
             flash("Erro ao processar o pedido. Por favor tente mais tarde.")
             print(f"Error inserting registration token: {success}")
             return redirect(url_for("register.request_confirmation"))

        confirm_url = url_for("register.confirm_email", token=token, _external=True)
        unsubscribe_url = url_for("register.unsubscribe", token=token, _external=True)

        subject = "Confirmar o endereço de email"
        html_message = f"""
        <p>Para confirmar o endereço de email e criar uma conta, utiliza este link:</p>
        <p><a href="{confirm_url}">{confirm_url}</a></p>
        <p>O link de confirmação é válido por 1 hora.</p>
        <p>Se não fez nenhum pedido, pode ignorar este email ou <a href="{unsubscribe_url}">pedir a remoção da base de dados.</a></p>
        """

        send_email(subject, email, html_message)
        flash("Foi enviado um email para confirmar o endereço de email.")
        flash("Veja também na página de lixo electrónico ou spam.")
        return redirect(url_for("register.request_confirmation"))

    main_content_html = render_template("content/request_new_user.html")
    return render_template(
        "index.html",
        admin_email=current_app.config["ADMIN_EMAIL"],
        user=session.get("userinfo"),
        page_title="Explicações em Lisboa",
        title="Explicações em Lisboa",
        main_content=Markup(main_content_html),
    )


@bp_register.route("/confirm/<token>")
def confirm_email(token):
    """
    Confirms a user's email address using a secure token.
    """
    token_data = getRegistrationToken(token)
    if not token_data:
        flash("Link de confirmação inválido ou expirado.")
        return redirect(url_for("register.request_confirmation"))

    email = confirm_token(token)
    if not email or email != token_data["email"]:
        flash("Link de confirmação inválido ou expirado.")
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
        flash("Link de remoção inválido ou expirado.")
        flash("Peça um novo link de remoção (requer fazer novo pedido com o email em que recebeu a mensagem).")
        return redirect(url_for("signin.signin"))

    email = token_data["email"]
    ip = token_data["ip_address"]

    if email:
        insertNewBlacklistedEmail(email)
    if ip:
        insertNewBlacklistedIP(ip)

    deleteRegistrationToken(token)

    flash("Este email foi removido da base de dados e não voltará a receber pedidos.")
    flash("O endereço de IP também foi bloqueado da base de dados e não voltará a fazer pedidos. Obrigado por ajudar a combater o envio de spam.")
    return redirect(url_for("signin.signin"))
