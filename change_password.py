import getpass
import sys

from werkzeug.security import generate_password_hash

import db as database

if len(sys.argv) != 2:
    raise SystemExit("Usage: python change_password.py user@example.com")

email = sys.argv[1].lower()
password = getpass.getpass("New password (at least 8 characters): ")
if len(password) < 8:
    raise SystemExit("Password too short.")
if password != getpass.getpass("Type it again: "):
    raise SystemExit("Passwords do not match.")

conn = database.connect()
if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone() is None:
    raise SystemExit("No user with that email.")
conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (generate_password_hash(password), email))
conn.commit()
conn.close()
print("Password changed for", email)