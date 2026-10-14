"""compliance.py - restricted-pesticide rules and the compliance log query."""

MIN_BUYER_ID_LENGTH = 4


def find_restricted_match(db, product_name):
    """
    Returns the restricted_pesticides row matching this product name, or None.
    Match when the restricted name appears inside the product name, or the first word
    (the active ingredient, at least 5 letters) is the same. Case is ignored.
    """
    name = (product_name or "").strip().lower()
    if not name:
        return None
    first_word = name.split()[0]

    for row in db.execute("SELECT pesticide_name, reason FROM restricted_pesticides").fetchall():
        restricted = row["pesticide_name"].strip().lower()
        if restricted in name:
            return row
        if len(first_word) >= 5 and first_word == restricted.split()[0]:
            return row
    return None


def fetch_restricted_sales(db, date_from=None, date_to=None, missing_only=False):
    """Returns (summary, records) for every sale of a restricted pesticide."""
    query = """
        SELECT s.sale_id, s.sale_date, s.quantity_sold, s.buyer_id_proof,
               p.product_id, p.name AS product_name, b.batch_no,
               u.name AS sold_by_name
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        JOIN batches b ON s.batch_id = b.batch_id
        LEFT JOIN users u ON s.sold_by = u.user_id
        WHERE p.is_restricted = 1
    """
    params = []
    if date_from:
        query += " AND s.sale_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND s.sale_date <= ?"
        params.append(date_to)
    if missing_only:
        query += " AND (s.buyer_id_proof IS NULL OR TRIM(s.buyer_id_proof) = '')"
    query += " ORDER BY s.sale_date DESC, s.sale_id DESC"

    records = []
    for row in db.execute(query, params).fetchall():
        item = dict(row)
        item["has_buyer_id"] = bool(item["buyer_id_proof"] and item["buyer_id_proof"].strip())
        records.append(item)

    with_id = sum(1 for r in records if r["has_buyer_id"])
    summary = {
        "total_records": len(records),
        "total_units": sum(r["quantity_sold"] for r in records),
        "with_buyer_id": with_id,
        "missing_buyer_id": len(records) - with_id,
    }
    return summary, records
