from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection
import secrets
from datetime import datetime, timedelta

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
        # Safety net for the rare case of two signups with the same email
        # landing at almost the same instant — the UNIQUE constraint on
        # the email column catches it even if the check above missed it.
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

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT users.id, users.name, users.email, users.role,
               users.profile_completed, users.created_at,
               profiles.phone_number, profiles.age, profiles.gender
        FROM users
        LEFT JOIN profiles ON profiles.user_id = users.id
        ORDER BY users.id
    """)
    users = cursor.fetchall()

    cursor.close()
    conn.close()
    return users


def delete_user_account(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    # Profiles row is removed automatically via ON DELETE CASCADE (set in
    # the schema), so we only need to delete from users here.
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()


def set_user_role(user_id, new_role):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET role = %s WHERE id = %s",
        (new_role, user_id)
    )

    conn.commit()
    cursor.close()
    conn.close()


def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    return user

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
    cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
    conn.commit()
    cursor.close()
    conn.close()