from itsdangerous import URLSafeTimedSerializer
from flask import current_app, request
import random
import string
from datetime import datetime, timedelta

def generate_token(email):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps(email, salt=current_app.config["SECURITY_PASSWORD_SALT"])


def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = serializer.loads(
            token, salt=current_app.config["SECURITY_PASSWORD_SALT"], max_age=expiration
        )
    except Exception:
        return False
    return email

def generate_short_token(email, length=10):
    """
    Generates a short alphanumeric token, saves it to the database, and returns it.
    """
    from mysql.DBhelpers import insertNewRegistrationToken, deleteRegistrationToken
    
    # Generate 10-char alphanumeric code (all caps for display)
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    
    # Save to database
    ip_address = request.remote_addr or "0.0.0.0"
    insertNewRegistrationToken(code, ip_address, email)
    
    return code

def confirm_short_token(code, expiration_minutes=5):
    """
    Validates a short token from the database. Case-insensitive.
    """
    from mysql.DBhelpers import getRegistrationTokenByToken, deleteRegistrationToken
    
    if not code:
        return False
        
    try:
        # Search for token
        token_data = getRegistrationTokenByToken(code.upper())
        
        if not token_data:
            return False
            
        # Check expiration
        created_at = token_data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            
        if datetime.utcnow() - created_at > timedelta(minutes=expiration_minutes):
            deleteRegistrationToken(code.upper())
            return False
            
        # Valid token! Delete it so it can't be reused
        email = token_data.get('email')
        deleteRegistrationToken(code.upper())
        
        return email
    except Exception as e:
        print(f"DEBUG RESUME: Error in confirm_short_token: {str(e)}")
        return False
