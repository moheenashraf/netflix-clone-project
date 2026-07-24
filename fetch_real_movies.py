import os
import json
import urllib.request
from dotenv import load_dotenv
from database import get_connection

load_dotenv()

API_KEY = os.getenv("TMDB_API_KEY")
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# TMDB's official genre ID numbers, mapped to the genre names already
# sitting in our own `genres` table.
TMDB_GENRE_MAP = {
    "Action": 28,
    "Comedy": 35,
    "Horror": 27,
    "Drama": 18,
    "Sci-Fi": 878,
    "Romance": 10749,
}

MOVIES_PER_GENRE = 4


def fetch_movies_for_genre(tmdb_genre_id):
    url = (
        f"https://api.themoviedb.org/3/discover/movie"
        f"?api_key={API_KEY}&with_genres={tmdb_genre_id}"
        f"&sort_by=popularity.desc&page=1"
    )
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
    return data.get("results", [])[:MOVIES_PER_GENRE]


def fetch_and_store():
    if not API_KEY:
        print("ERROR: TMDB_API_KEY not found in .env — add it before running this.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Clear out old sample movies so we don't end up with a mix of
    # fictional and real titles.
    cursor.execute("DELETE FROM watch_history")
    cursor.execute("DELETE FROM movies")
    conn.commit()
    print("Cleared old sample movies.")

    cursor.execute("SELECT id, name FROM genres")
    local_genres = {name: gid for gid, name in cursor.fetchall()}

    total_added = 0

    for genre_name, tmdb_id in TMDB_GENRE_MAP.items():
        local_genre_id = local_genres.get(genre_name)
        if not local_genre_id:
            print(f"Skipping '{genre_name}' — not found in local genres table.")
            continue

        results = fetch_movies_for_genre(tmdb_id)

        for movie in results:
            title = movie.get("title", "Untitled")
            overview = movie.get("overview", "").strip() or "No description available."
            poster_path = movie.get("poster_path")
            release_date = movie.get("release_date", "")
            release_year = int(release_date[:4]) if release_date[:4].isdigit() else None

            if not poster_path:
                print(f"Skipping '{title}' — no poster available.")
                continue

            poster_url = f"{IMAGE_BASE}{poster_path}"

            cursor.execute(
                """
                INSERT INTO movies (title, description, poster_url, release_year, genre_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (title, overview, poster_url, release_year, local_genre_id)
            )
            print(f"Added: {title} ({genre_name})")
            total_added += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"\nDone. {total_added} real movies added with real posters.")


if __name__ == "__main__":
    fetch_and_store()