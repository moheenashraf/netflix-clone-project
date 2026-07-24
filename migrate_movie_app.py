from database import get_connection

conn = get_connection()
cursor = conn.cursor()

# ---------------- LOGS TABLE ----------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS logs(
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    action TEXT NOT NULL,
    module VARCHAR(100) DEFAULT '',
    time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(50) DEFAULT ''
)
""")
print("logs table ready.")

# ---------------- WATCH HISTORY TABLE ----------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS watch_history(
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    movie_id INT NOT NULL,
    watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE
)
""")
print("watch_history table ready.")

conn.commit()
cursor.close()
conn.close()
print("Migration complete.")