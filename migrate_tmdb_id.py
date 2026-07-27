from database import get_connection

conn = get_connection()
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE movies ADD COLUMN tmdb_id INT NULL")
    print("Added tmdb_id column.")
except Exception as e:
    print(f"Skipped (likely already exists): {e}")

conn.commit()
cursor.close()
conn.close()
print("Migration complete.")