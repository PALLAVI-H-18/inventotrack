"""
Re-checks EVERY existing product against the restricted list and updates is_restricted.
Run once after updating app.py:   python reflag_products.py
Safe to run again at any time.
"""
from app import get_db_connection, find_restricted_match

conn = get_db_connection()
products = conn.execute("SELECT product_id, name, is_restricted FROM products").fetchall()

changed = 0
for p in products:
    match = find_restricted_match(conn, p["name"])
    new_flag = 1 if match else 0
    if new_flag != p["is_restricted"]:
        conn.execute("UPDATE products SET is_restricted = ? WHERE product_id = ?", (new_flag, p["product_id"]))
        state = "FLAGGED as restricted" if new_flag else "UNFLAGGED"
        reason = f" (matches '{match['pesticide_name']}')" if match else ""
        print(f"{state}: {p['name']}{reason}")
        changed += 1

conn.commit()
conn.close()
print(f"Done. {changed} product(s) changed, {len(products) - changed} unchanged.")