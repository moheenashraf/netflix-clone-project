from database import get_connection


def record_watch(user_id, movie_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO watch_history (user_id, movie_id) VALUES (%s, %s)",
        (user_id, movie_id)
    )
    conn.commit()
    cursor.close()
    conn.close()


def get_recently_watched(user_id, limit=5):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT movies.id, movies.title, movies.poster_url, movies.release_year,
               genres.name AS genre_name, watch_history.watched_at
        FROM watch_history
        INNER JOIN movies ON movies.id = watch_history.movie_id
        INNER JOIN genres ON genres.id = movies.genre_id
        WHERE watch_history.user_id = %s
        ORDER BY watch_history.watched_at DESC
        LIMIT %s
    """, (user_id, limit))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_suggested_movies(user_id, limit=6):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Suggest movies from genres the user has already watched, excluding
    # anything they've already seen.
    cursor.execute("""
        SELECT DISTINCT movies.id, movies.title, movies.poster_url,
               movies.release_year, genres.name AS genre_name
        FROM movies
        INNER JOIN genres ON genres.id = movies.genre_id
        WHERE movies.genre_id IN (
            SELECT DISTINCT m.genre_id
            FROM watch_history wh
            INNER JOIN movies m ON m.id = wh.movie_id
            WHERE wh.user_id = %s
        )
        AND movies.id NOT IN (
            SELECT movie_id FROM watch_history WHERE user_id = %s
        )
        ORDER BY RAND()
        LIMIT %s
    """, (user_id, user_id, limit))
    suggestions = cursor.fetchall()

    # New users (or ones who've watched everything in their genres) get a
    # random sample instead, so the section is never left empty.
    if not suggestions:
        cursor.execute("""
            SELECT movies.id, movies.title, movies.poster_url,
                   movies.release_year, genres.name AS genre_name
            FROM movies
            INNER JOIN genres ON genres.id = movies.genre_id
            WHERE movies.id NOT IN (
                SELECT movie_id FROM watch_history WHERE user_id = %s
            )
            ORDER BY RAND()
            LIMIT %s
        """, (user_id, limit))
        suggestions = cursor.fetchall()

    cursor.close()
    conn.close()
    return suggestions
def get_all_watch_history():
    """Admin-only: every watch event across every user, most recent first."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT users.name AS user_name, movies.title AS movie_title,
               genres.name AS genre_name, watch_history.watched_at
        FROM watch_history
        INNER JOIN users ON users.id = watch_history.user_id
        INNER JOIN movies ON movies.id = watch_history.movie_id
        INNER JOIN genres ON genres.id = movies.genre_id
        ORDER BY watch_history.watched_at DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows