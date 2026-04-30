# Mail Interaction Module

This module handles all outbound communication, primarily through SMTP email.

## Responsibilities

- **Email Dispatch:** Utilizes `Flask-Mail` to send secure (SSL/TLS) emails to users. Configuration is dynamically loaded from the environment.
- **Registration Flow:** Implements a highly secure, token-based registration system.
  - Generates time-sensitive (1-hour expiration) URL-safe tokens using `itsdangerous`.
  - Sends confirmation emails with unique links to verify user identities.
  - Automatically cleans up expired tokens from the database.
- **Anti-Spam/Abuse:** Checks requested IP addresses and emails against a blacklist before dispatching emails. Includes functionality for users to seamlessly unsubscribe or request removal from the database.

## Architecture Notes
- The tokens generated (`registration_token.py`) encode the user's email securely but do not embed IP addresses to prevent conflicts across proxy layers.
- Uses strict database validation to guarantee that an email is successfully queued or dispatched only if the token was successfully logged in the database.