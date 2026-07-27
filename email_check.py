from email_validator import validate_email, EmailNotValidError


def is_real_email(email):
    """Checks the email is correctly formatted AND that its domain has
    valid mail servers configured. Cannot verify a specific mailbox truly
    exists (no public service can do that reliably), but this correctly
    rejects malformed addresses and fake/non-existent domains."""
    try:
        validate_email(email, check_deliverability=True)
        return True
    except EmailNotValidError:
        return False