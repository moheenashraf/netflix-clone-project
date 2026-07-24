from database import get_connection


def create_profile(user_id, full_name, phone_number, age, gender, email, favorite_genre_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO profiles (user_id, full_name, phone_number, age, gender, email, favorite_genre_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, full_name, phone_number, age, gender, email, favorite_genre_id)
    )

    cursor.execute(
        "UPDATE users SET profile_completed = TRUE WHERE id = %s",
        (user_id,)
    )

    conn.commit()
    cursor.close()
    conn.close()


def get_profile(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT profiles.*, genres.name AS favorite_genre_name
        FROM profiles
        LEFT JOIN genres ON genres.id = profiles.favorite_genre_id
        WHERE profiles.user_id = %s
    """, (user_id,))
    profile = cursor.fetchone()

    cursor.close()
    conn.close()
    return profile


def update_profile(user_id, full_name, phone_number, age, gender, favorite_genre_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE profiles
        SET full_name = %s, phone_number = %s, age = %s, gender = %s, favorite_genre_id = %s
        WHERE user_id = %s
        """,
        (full_name, phone_number, age, gender, favorite_genre_id, user_id)
    )

    conn.commit()
    cursor.close()
    conn.close()