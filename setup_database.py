"""
setup_database.py - creates the tables and the two demo logins.   (Oct 19)

    python setup_database.py                 -> tables + demo users
    python setup_database.py --demo-data     -> also fills a sample shop (only if there are no products yet)

Works on your laptop (SQLite) and on Render (PostgreSQL, when DATABASE_URL is set).
Safe to run again: nothing that already exists is duplicated.
Demo passwords are for DEMO only - change them (or delete the accounts) for real use.
"""
import sys

from werkzeug.security import generate_password_hash

import db as database

DEMO_USERS = [
    ("Shop Owner", "owner@inventotrack.com", "Owner@123", "owner"),
    ("Shop Staff", "staff@inventotrack.com", "Staff@123", "staff"),
]


def create_demo_users(conn):
    for name, email, password, role in DEMO_USERS:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            print(f"  skipped (exists): {email}")
            continue
        conn.insert(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (name, email, generate_password_hash(password), role), "user_id",
        )
        print(f"  created {role}: {email}")
    conn.commit()


if __name__ == "__main__":
    conn = database.connect()
    print("Database:", "PostgreSQL" if conn.postgres else f"SQLite ({database.sqlite_path()})")
    database.init_schema(conn)
    print("Tables ready.")
    create_demo_users(conn)
    if "--demo-data" in sys.argv:
        import seed_demo
        seed_demo.seed(conn)
    conn.close()
