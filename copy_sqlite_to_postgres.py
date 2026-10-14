"""
copy_sqlite_to_postgres.py - copies YOUR local data (inventotrack.db) into the Render PostgreSQL database.  (Oct 19)

    # PowerShell:   $env:DATABASE_URL = "<External Database URL from Render>"
    python copy_sqlite_to_postgres.py

Run it once. It refuses to run if the PostgreSQL tables already contain data.
"""
import os
import sqlite3

import db as database

TABLES = [  # parent tables first, then the tables that point to them
    ("users", "user_id"), ("suppliers", "supplier_id"), ("products", "product_id"),
    ("batches", "batch_id"), ("sales", "sale_id"), ("restricted_pesticides", "restricted_id"),
]

if not database.using_postgres():
    raise SystemExit("Set DATABASE_URL first (the External Database URL from Render).")
source_path = database.sqlite_path()
if not os.path.exists(source_path):
    raise SystemExit(f"Local database not found: {source_path}")

source = sqlite3.connect(source_path)
source.row_factory = sqlite3.Row
target = database.connect()
database.init_schema(target)

for table, _ in TABLES:
    if target.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"] > 0:
        raise SystemExit(f"Table '{table}' in PostgreSQL already has data - stopping so nothing is duplicated.")

for table, id_column in TABLES:
    rows = source.execute(f"SELECT * FROM {table}").fetchall()
    if rows:
        columns = list(rows[0].keys())
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})"
        for row in rows:
            target.execute(sql, tuple(row[c] for c in columns))
        # make the auto-number continue after the highest copied id
        target.execute(f"SELECT setval(pg_get_serial_sequence('{table}', '{id_column}'), "
                       f"(SELECT MAX({id_column}) FROM {table}))")
    print(f"{table}: {len(rows)} rows copied")
target.commit()
target.close()
source.close()
print("Done.")
