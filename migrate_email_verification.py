from database import get_connection

conn = get_connection()
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE")
    print("Added email_verified column.")
except Exception as e:
    print(f"Skipped (likely already exists): {e}")

conn.commit()
cursor.close()
conn.close()
print("Migration complete.")