"""
Creates the two demo accounts (one owner, one staff).
Run once after database.py:   python create_demo_users.py
Safe to run again: existing users are skipped.
These are DEMO passwords only. Change them for any real use.
"""
import sqlite3
from werkzeug.security import generate_password_hash

DEMO_USERS = [
    ("Shop Owner", "owner@inventotrack.com", "Owner@123", "owner"),
    ("Shop Staff", "staff@inventotrack.com", "Staff@123", "staff"),
]

conn = sqlite3.connect("inventotrack.db")
for name, email, password, role in DEMO_USERS:
    exists = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
    if exists:
        print(f"Skipped (already exists): {email}")
        continue
    conn.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (name, email, generate_password_hash(password), role),
    )
    print(f"Created {role}: {email}")
conn.commit()
conn.close()