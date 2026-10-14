"""
Re-checks EVERY product against the restricted list and updates is_restricted.
    python reflag_products.py        (safe to run again at any time)
"""
import db as database
from compliance import find_restricted_match

conn = database.connect()
changed = 0
products = conn.execute("SELECT product_id, name, is_restricted FROM products").fetchall()
for p in products:
    match = find_restricted_match(conn, p["name"])
    new_flag = 1 if match else 0
    if new_flag != p["is_restricted"]:
        conn.execute("UPDATE products SET is_restricted = ? WHERE product_id = ?", (new_flag, p["product_id"]))
        print(("FLAGGED " if new_flag else "UNFLAGGED ") + p["name"])
        changed += 1
conn.commit()
conn.close()
print(f"Done. {changed} changed, {len(products) - changed} unchanged.")
