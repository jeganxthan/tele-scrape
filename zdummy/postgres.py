import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def init_db():
    """Initializes the database schema."""
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        
        # Create series_data table with JSONB column
        cur.execute("""
            CREATE TABLE IF NOT EXISTS series_data (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) UNIQUE NOT NULL,
                data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database initialized successfully (JSONB storage).")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        if conn:
            conn.rollback()
            conn.close()

def save_show_data(data):
    """Saves the entire scraped show data as a JSON object."""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        
        show_title = data.get("show_title")
        if not show_title:
            print("❌ Cannot save data: 'show_title' is missing from data dictionary.")
            print(f"Data keys: {list(data.keys())}")
            return False

        print(f"Attempting to save data for show: '{show_title}'")

        # Insert or Update the JSON blob
        cur.execute("""
            INSERT INTO series_data (title, data)
            VALUES (%s, %s)
            ON CONFLICT (title) DO UPDATE SET
                data = EXCLUDED.data,
                created_at = CURRENT_TIMESTAMP;
        """, (show_title, Json(data)))

        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Full JSON data for '{show_title}' saved to database.")
        return True

    except Exception as e:
        print(f"❌ Failed to save data: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

def get_all_shows():
    """Retrieves a list of all stored shows."""
    conn = get_db_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, title, created_at FROM series_data ORDER BY title;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"❌ Failed to fetch shows: {e}")
        return []

def get_show_data(title):
    """Retrieves the full JSON data for a specific show."""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT data FROM series_data WHERE title = %s;", (title,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return row['data']
        return None
    except Exception as e:
        print(f"❌ Failed to fetch show data: {e}")
        return None

