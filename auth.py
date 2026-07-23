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

    cursor.execute(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (%s, %s, %s, %s)
        """,
        (name, email, password_hash, role)
    )
    conn.commit()
    new_id = cursor.lastrowid

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