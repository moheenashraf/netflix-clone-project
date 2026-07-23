import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


def create_database():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'user',
            profile_completed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles(
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL UNIQUE,
            full_name VARCHAR(255) NOT NULL,
            phone_number VARCHAR(50) NOT NULL,
            age INT NOT NULL,
            gender VARCHAR(20) NOT NULL,
            email VARCHAR(255) NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS genres(
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies(
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            poster_url VARCHAR(500),
            release_year INT,
            genre_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(genre_id) REFERENCES genres(id)
        )
        """)

        connection.commit()
        print("Database Created Successfully!")

        starter_genres = ["Action", "Comedy", "Horror", "Drama", "Sci-Fi", "Romance"]
        for genre in starter_genres:
            cursor.execute(
                "INSERT IGNORE INTO genres (name) VALUES (%s)",
                (genre,)
            )
        connection.commit()
        print("Starter genres seeded.")

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    create_database()