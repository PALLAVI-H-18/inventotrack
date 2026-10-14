"""Create the first production owner from environment variables."""
import os
import sqlite3
from getpass import getpass

from werkzeug.security import generate_password_hash

from database import DB_NAME, init_db


def create_owner():
    name = os.environ.get("OWNER_NAME") or input("Owner name: ")
    email = os.environ.get("OWNER_EMAIL") or input("Owner email: ")
    password = os.environ.get("OWNER_PASSWORD") or getpass("Owner password: ")
    name = name.strip()
    email = email.strip().lower()
    if not name or "@" not in email or len(password) < 12:
        raise ValueError(
            "Set OWNER_NAME, a valid OWNER_EMAIL, and OWNER_PASSWORD "
            "(at least 12 characters) before running this script"
        )

    init_db()
    conn = sqlite3.connect(DB_NAME)
    try:
        owner_exists = conn.execute(
            "SELECT 1 FROM users WHERE role = 'owner' LIMIT 1"
        ).fetchone()
        if owner_exists:
            raise ValueError("An owner already exists; refusing to create another")
        conn.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'owner')",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
    finally:
        conn.close()
    print(f"Created production owner: {email}")


if __name__ == "__main__":
    create_owner()
