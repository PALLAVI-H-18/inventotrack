"""stock.py - small helpers about "today" and current stock."""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))     # Render servers run in UTC; the shop runs in India


def today():
    return datetime.now(IST).date()


def today_str():
    return today().strftime("%Y-%m-%d")


def stock_status(quantity, min_level):
    if quantity <= 0:
        return "out_of_stock"
    if quantity <= min_level:
        return "low_stock"
    return "healthy"


def get_products_with_stock(db):
    """Every product with its NON-EXPIRED stock and a status label."""
    rows = db.execute("""
        SELECT p.product_id, p.name, p.brand, p.category, p.season,
               p.min_stock_level, p.is_restricted,
               COALESCE(SUM(b.quantity_remaining), 0) AS total_quantity,
               (SELECT COALESCE(SUM(s.quantity_sold), 0) FROM sales s WHERE s.product_id = p.product_id) AS total_sold,
               (SELECT COALESCE(SUM(s.quantity_sold), 0) FROM sales s
                 WHERE s.product_id = p.product_id AND s.sale_date LIKE ?) AS sold_today
        FROM products p
        LEFT JOIN batches b ON p.product_id = b.product_id AND b.expiry_date >= ?
        GROUP BY p.product_id
        ORDER BY p.product_id
    """, (today_str() + "%", today_str())).fetchall()

    products = []
    for row in rows:
        item = dict(row)
        item["total_quantity"] = int(item["total_quantity"])
        item["total_sold"] = int(item["total_sold"])
        item["sold_today"] = int(item["sold_today"])
        item["status"] = stock_status(item["total_quantity"], item["min_stock_level"])
        products.append(item)
    return products
