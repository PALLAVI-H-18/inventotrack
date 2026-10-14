import os
import sqlite3

DB_NAME = os.environ.get(
    "DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventotrack.db")
)


def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_NAME)), exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print("Database created successfully!")

if __name__ == "__main__":
    init_db()