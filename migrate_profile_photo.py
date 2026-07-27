from database import get_connection

conn = get_connection()
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE profiles ADD COLUMN profile_photo_url VARCHAR(500) NULL")
    print("Added profile_photo_url column.")
except Exception as e:
    print(f"Skipped (likely already exists): {e}")

conn.commit()
cursor.close()
conn.close()
print("Migration complete.")