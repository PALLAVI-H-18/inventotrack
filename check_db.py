import db as database

conn = database.connect()
for table in ["users", "suppliers", "products", "batches", "sales", "restricted_pesticides"]:
    count = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
    print(f"{table}: {count}")
conn.close()