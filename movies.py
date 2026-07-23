from database import get_connection


def get_all_genres():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM genres ORDER BY name")
    genres = cursor.fetchall()

    cursor.close()
    conn.close()
    return genres


def get_movies_grouped_by_genre():
    """Returns a list of {genre_name, movies: [...]}, skipping genres with
    no movies yet so the browse page doesn't show empty rows."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            movies.id, movies.title, movies.description,
            movies.poster_url, movies.release_year,
            genres.id AS genre_id, genres.name AS genre_name
        FROM movies
        INNER JOIN genres ON genres.id = movies.genre_id
        ORDER BY genres.name, movies.release_year DESC
    """)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    grouped = {}
    for row in rows:
        genre_name = row["genre_name"]
        if genre_name not in grouped:
            grouped[genre_name] = []
        grouped[genre_name].append(row)

    return [{"genre_name": name, "movies": movies} for name, movies in grouped.items()]


def get_all_movies():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT movies.*, genres.name AS genre_name
        FROM movies
        INNER JOIN genres ON genres.id = movies.genre_id
        ORDER BY movies.id DESC
    """)
    movies = cursor.fetchall()

    cursor.close()
    conn.close()
    return movies


def get_movie_by_id(movie_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()

    cursor.close()
    conn.close()
    return movie


def add_movie(title, description, poster_url, release_year, genre_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO movies (title, description, poster_url, release_year, genre_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (title, description, poster_url, release_year, genre_id)
    )

    conn.commit()
    new_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return new_id


def update_movie(movie_id, title, description, poster_url, release_year, genre_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE movies
        SET title = %s, description = %s, poster_url = %s,
            release_year = %s, genre_id = %s
        WHERE id = %s
        """,
        (title, description, poster_url, release_year, genre_id, movie_id)
    )

    conn.commit()
    cursor.close()
    conn.close()


def delete_movie(movie_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM movies WHERE id = %s", (movie_id,))

    conn.commit()
    cursor.close()
    conn.close()