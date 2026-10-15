"""
reset_demo.py - ONE command that restores clean demo data.      (Oct 21)

    python reset_demo.py          asks "Type RESET to continue", then rebuilds the demo shop
    python reset_demo.py --yes    no question (for scripts)

It DELETES products, batches, sales, suppliers and the restricted list, then re-creates the demo shop:
20 products + 1 new product, ~13 months of sales, and one example of every situation
(out of stock, low stock, expiring soon, expired, restricted sales with and without buyer ID).
It KEEPS your users, so your logins and passwords stay as they are.
Works on your laptop (SQLite) and on Render (PostgreSQL, when DATABASE_URL is set).
"""
import sys
from urllib.parse import urlparse

import db as database
import seed_demo
import setup_database

TABLES = ["sales", "batches", "products", "suppliers", "restricted_pesticides"]    # children first


def describe_target():
    if database.using_postgres():
        return f"PostgreSQL database on host {urlparse(database.database_url()).hostname}  (THE LIVE ONE)"
    return f"local SQLite file {database.sqlite_path()}"


def wipe(conn):
    if conn.postgres:
        conn.execute("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE")
    else:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM sqlite_sequence WHERE name IN (" + ", ".join("?" for _ in TABLES) + ")", TABLES)
    conn.commit()


def main():
    print("This will reset the demo data in:", describe_target())
    print("Products, batches, sales and suppliers will be DELETED and re-created. Users are kept.")
    if "--yes" not in sys.argv and input("Type RESET to continue: ").strip() != "RESET":
        raise SystemExit("Cancelled. Nothing was changed.")

    conn = database.connect()
    database.init_schema(conn)
    wipe(conn)
    if conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"] == 0:
        setup_database.create_demo_users(conn)
    seed_demo.seed(conn)

    print("\nDone. The database now holds:")
    for table in TABLES + ["users"]:
        print(f"  {table:24} {conn.execute(f'SELECT COUNT(*) AS c FROM {table}').fetchone()['c']}")
    conn.close()


if __name__ == "__main__":
    main()
