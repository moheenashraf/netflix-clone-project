import secrets
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection


def create_user(name, email, password, role="user"):
    """Creates a new user account. Raises ValueError if email is taken."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        raise ValueError("An account with this email already exists.")

    password_hash = generate_password_hash(password)

    try:
        cursor.execute(
            """
            INSERT INTO users (name, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            """,
            (name, email, password_hash, role)
        )
        conn.commit()
        new_id = cursor.lastrowid
    except Exception as exc:
        conn.rollback()
        cursor.close()
        conn.close()
        if "Duplicate entry" in str(exc):
            raise ValueError("An account with this email already exists.")
        raise

    cursor.close()
    conn.close()
    return new_id


def verify_login(email, password):
    """Returns the user row (as a dict) if credentials are correct, else None."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user


def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user


def mark_email_verified(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET email_verified = TRUE WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()


def create_password_reset_token(user_id):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(minutes=30)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (%s, %s, %s)",
        (user_id, token, expires_at)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return token


def validate_reset_token(token):
    """Returns the user_id if the token is real, unused, and not expired. Else None."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM password_reset_tokens WHERE token = %s AND used = FALSE",
        (token,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return None
    if row["expires_at"] < datetime.now():
        return None
    return row["user_id"]


def use_reset_token(token):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE password_reset_tokens SET used = TRUE WHERE token = %s", (token,))
    conn.commit()
    cursor.close()
    conn.close()


def update_password(user_id, new_password):
    password_hash = generate_password_hash(new_password)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (password_hash, user_id)
    )

    conn.commit()
    cursor.close()
    conn.close()
def update_password(user_id, new_password):
    password_hash = generate_password_hash(new_password)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (password_hash, user_id)
    )

    conn.commit()
    cursor.close()
    conn.close()


def get_all_users():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            id,
            name,
            email,
            role,
            email_verified,
            profile_completed
        FROM users
        ORDER BY id DESC
    """)

    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return users