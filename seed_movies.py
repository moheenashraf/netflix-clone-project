from database import get_connection

# Using placehold.co for posters — free, no signup, reliable, and lets us
# generate a placeholder image just by changing the URL. Swap these for
# real poster URLs later once you're adding movies through the admin panel.

sample_movies = [
    ("Action", "Blaze Protocol", "A rogue agent races against time to stop a global threat.", 2023),
    ("Action", "Iron Horizon", "Elite soldiers defend the last free city on Earth.", 2022),
    ("Comedy", "Office Chaos", "A disastrous first week at a chaotic startup.", 2021),
    ("Comedy", "Roommates from Hell", "Three strangers, one apartment, zero boundaries.", 2020),
    ("Horror", "The Silent House", "A family moves into a house that remembers everything.", 2023),
    ("Horror", "Midnight Static", "Something answers back on the old radio frequency.", 2022),
    ("Drama", "Quiet Waters", "A father and daughter rebuild their bond one summer.", 2021),
    ("Drama", "The Long Return", "A soldier's homecoming reveals a town full of secrets.", 2019),
    ("Sci-Fi", "Orbit Zero", "The last crew of Earth's final space station.", 2024),
    ("Sci-Fi", "Neon Divide", "In a divided future city, one hacker holds the truth.", 2023),
    ("Romance", "Letters to Someday", "Two strangers fall in love through anonymous letters.", 2022),
    ("Romance", "Second Chances Cafe", "An old flame reignites over morning coffee.", 2021),
]


def seed():
    conn = get_connection()
    cursor = conn.cursor()

    for genre_name, title, description, year in sample_movies:
        cursor.execute("SELECT id FROM genres WHERE name = %s", (genre_name,))
        genre_row = cursor.fetchone()
        if not genre_row:
            print(f"Skipping '{title}' — genre '{genre_name}' not found.")
            continue
        genre_id = genre_row[0]

        # Avoid inserting the same movie twice if this script runs more than once
        cursor.execute("SELECT id FROM movies WHERE title = %s", (title,))
        if cursor.fetchone():
            print(f"Skipping '{title}' — already exists.")
            continue

        poster_url = f"https://placehold.co/300x450/1a1a1a/ffffff?text={title.replace(' ', '+')}"

        cursor.execute(
            """
            INSERT INTO movies (title, description, poster_url, release_year, genre_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (title, description, poster_url, year, genre_id)
        )
        print(f"Added: {title}")

    conn.commit()
    cursor.close()
    conn.close()
    print("Seeding complete.")


if __name__ == "__main__":
    seed()