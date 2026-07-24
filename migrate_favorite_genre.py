from database import get_connection

conn = get_connection()
cursor = conn.cursor()

try:
    cursor.execute("""
        ALTER TABLE profiles
        ADD COLUMN favorite_genre_id INT NULL,
        ADD FOREIGN KEY (favorite_genre_id) REFERENCES genres(id)
    """)
    print("Added favorite_genre_id column.")
except Exception as e:
    print(f"Skipped (likely already exists): {e}")

conn.commit()
cursor.close()
conn.close()
print("Migration complete.")