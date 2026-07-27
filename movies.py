from database import get_connection
import os
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

DEFAULT_POSTER = "https://placehold.co/300x450/1a1a1a/ffffff?text=No+Poster"


def sanitize_movie_dict(movie):
    """Ensures movie dictionary fields (especially poster_url) are safe and non-null."""
    if not movie:
        return movie

    poster = movie.get("poster_url")
    if not poster or str(poster).strip() == "":
        title_param = str(movie.get("title", "No Image")).replace(" ", "+")
        movie["poster_url"] = f"https://placehold.co/300x450/1a1a1a/ffffff?text={title_param}"

    return movie


def get_all_genres():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM genres ORDER BY name")
    genres = cursor.fetchall()

    cursor.close()
    conn.close()
    return genres


def get_movies_grouped_by_genre():
    """Returns a list of {genre_name, movies: [...]}, showing the newest updated
    version of every movie and skipping duplicates across categories."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Order by movies.id DESC so the most recently edited/added movies are processed first
    cursor.execute("""
        SELECT
            movies.id, movies.title, movies.description,
            movies.poster_url, movies.release_year,
            genres.id AS genre_id, genres.name AS genre_name
        FROM movies
        INNER JOIN genres ON genres.id = movies.genre_id
        ORDER BY movies.id DESC
    """)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    seen_titles = set()
    grouped = {}

    for row in rows:
        row = sanitize_movie_dict(row)
        title_key = str(row["title"]).strip().lower()

        # Skip duplicate titles so only the latest edited version appears
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        genre_name = row["genre_name"]
        if genre_name not in grouped:
            grouped[genre_name] = []
        grouped[genre_name].append(row)

    # Sort genres alphabetically for display
    sorted_categories = sorted(grouped.items(), key=lambda x: x[0])
    return [{"genre_name": name, "movies": movies} for name, movies in sorted_categories]


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
    return [sanitize_movie_dict(m) for m in movies]


def get_movie_by_id(movie_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
    movie = cursor.fetchone()

    cursor.close()
    conn.close()
    return sanitize_movie_dict(movie)


def add_movie(title, description, poster_url, release_year, genre_id):
    conn = get_connection()
    cursor = conn.cursor()

    if not poster_url or str(poster_url).strip() == "":
        poster_url = DEFAULT_POSTER

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

    if not poster_url or str(poster_url).strip() == "":
        poster_url = DEFAULT_POSTER

    # 1. Update the specific movie record
    cursor.execute(
        """
        UPDATE movies
        SET title = %s, description = %s, poster_url = %s,
            release_year = %s, genre_id = %s
        WHERE id = %s
        """,
        (title, description, poster_url, release_year, genre_id, movie_id)
    )

    # 2. Synchronize poster_url across ANY duplicate title records in the database
    cursor.execute(
        """
        UPDATE movies
        SET poster_url = %s
        WHERE LOWER(TRIM(title)) = LOWER(TRIM(%s))
        """,
        (poster_url, title)
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


def get_trailer_for_movie(tmdb_id):
    """Returns a YouTube video key for the movie's official trailer, or None
    if no trailer is available."""
    if not tmdb_id or not TMDB_API_KEY:
        return None

    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos?api_key={TMDB_API_KEY}"

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
    except Exception:
        return None

    videos = data.get("results", [])

    for video in videos:
        if video.get("site") == "YouTube" and video.get("type") == "Trailer":
            return video.get("key")

    for video in videos:
        if video.get("site") == "YouTube":
            return video.get("key")

    return None