from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

DB_NAME = "inventotrack.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def home():
    return jsonify({"message": "InventoTrack backend is running"})
# ---------------------------------------------------------
# POST /products - add a new product (checks restricted list)
# ---------------------------------------------------------
@app.route("/products", methods=["POST"])
def add_product():
    data = request.get_json()

    if not data.get("name"):
        return jsonify({"error": "Product name is required"}), 400

    conn = get_db_connection()
    # ---------------------------------------------------------
# Helpers used by products + dashboard routes
# ---------------------------------------------------------
def today_str():
    return datetime.today().strftime("%Y-%m-%d")


def stock_status(quantity, min_level):
    if quantity <= 0:
        return "out_of_stock"
    if quantity <= min_level:
        return "low_stock"
    return "healthy"


def get_products_with_stock(conn):
    """Every product with its NON-EXPIRED stock and a status label."""
    rows = conn.execute("""
        SELECT p.product_id, p.name, p.brand, p.category, p.season,
               p.min_stock_level, p.is_restricted,
               COALESCE(SUM(b.quantity_remaining), 0) AS total_quantity
        FROM products p
        LEFT JOIN batches b
               ON p.product_id = b.product_id AND b.expiry_date >= ?
        GROUP BY p.product_id
    """, (today_str(),)).fetchall()

    products = []
    for row in rows:
        item = dict(row)
        item["status"] = stock_status(item["total_quantity"], item["min_stock_level"])
        products.append(item)
    return products

    # check against restricted_pesticides table
    match = conn.execute("""
        SELECT * FROM restricted_pesticides
        WHERE LOWER(pesticide_name) = LOWER(?)
    """, (data.get("name"),)).fetchone()

    is_restricted = 1 if match else 0

    cur = conn.execute("""
        INSERT INTO products (name, brand, category, season, min_stock_level, is_restricted)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data.get("name"),
        data.get("brand"),
        data.get("category"),
        data.get("season"),
        data.get("min_stock_level", 10),
        is_restricted
    ))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    return jsonify({
        "message": "Product added successfully",
        "product_id": new_id,
        "is_restricted": bool(is_restricted)
    }), 201

# ---------------------------------------------------------
# POST /batches - add a new stock batch for a product
# ---------------------------------------------------------
@app.route("/batches", methods=["POST"])
def add_batch():
    data = request.get_json()

    required_fields = ["product_id", "batch_no", "quantity_received",
                        "price_per_unit", "purchase_date", "expiry_date"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    conn = get_db_connection()

    # confirm the product actually exists before attaching a batch to it
    product = conn.execute(
        "SELECT * FROM products WHERE product_id = ?", (data["product_id"],)
    ).fetchone()
    if product is None:
        conn.close()
        return jsonify({"error": "Product not found"}), 404

    quantity_received = data["quantity_received"]
    if quantity_received <= 0:
        conn.close()
        return jsonify({"error": "quantity_received must be positive"}), 400

    cur = conn.execute("""
        INSERT INTO batches (product_id, supplier_id, batch_no, quantity_received,
                              quantity_remaining, price_per_unit, purchase_date, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["product_id"],
        data.get("supplier_id"),
        data["batch_no"],
        quantity_received,
        quantity_received,          # quantity_remaining starts equal to quantity_received
        data["price_per_unit"],
        data["purchase_date"],
        data["expiry_date"]
    ))
    conn.commit()
    new_batch_id = cur.lastrowid
    conn.close()

    return jsonify({
        "message": "Batch added successfully",
        "batch_id": new_batch_id
    }), 201


# ---------------------------------------------------------
# GET /products/<id>/batches - list all batches for one product
# ---------------------------------------------------------
@app.route("/products/<int:product_id>/batches", methods=["GET"])
def get_batches_for_product(product_id):
    conn = get_db_connection()

    product = conn.execute(
        "SELECT * FROM products WHERE product_id = ?", (product_id,)
    ).fetchone()
    if product is None:
        conn.close()
        return jsonify({"error": "Product not found"}), 404

    rows = conn.execute("""
        SELECT batch_id, batch_no, quantity_received, quantity_remaining,
               price_per_unit, purchase_date, expiry_date, supplier_id
        FROM batches
        WHERE product_id = ?
        ORDER BY expiry_date ASC
    """, (product_id,)).fetchall()
    conn.close()

    batches = [dict(row) for row in rows]
    return jsonify({
        "product_name": product["name"],
        "batches": batches
    })
    
# ---------------------------------------------------------
# POST /sales - record a sale with FIFO batch deduction
# ---------------------------------------------------------

# ---------------------------------------------------------
# POST /sales - record a sale, deduct stock using FIFO
# ---------------------------------------------------------
@app.route("/sales", methods=["POST"])
def record_sale():
    data = request.get_json()

    product_id = data.get("product_id")
    quantity_sold = data.get("quantity_sold")
    sold_by = data.get("sold_by")          # user_id, optional for now until auth is built
    buyer_id_proof = data.get("buyer_id_proof")  # only needed for restricted products

    if not product_id or not quantity_sold or quantity_sold <= 0:
        return jsonify({"error": "product_id and a positive quantity_sold are required"}), 400

    conn = get_db_connection()

    # Step A: confirm product exists, and check if it's restricted
    product = conn.execute(
        "SELECT * FROM products WHERE product_id = ?", (product_id,)
    ).fetchone()
    if product is None:
        conn.close()
        return jsonify({"error": "Product not found"}), 404

    # Step B: enforce compliance - restricted products need buyer ID
    if product["is_restricted"] and not buyer_id_proof:
        conn.close()
        return jsonify({
            "error": "This product is restricted. Buyer identification is required to complete this sale."
        }), 400

    # Step C: get all usable batches - not expired, has stock - oldest expiry first
    today = datetime.today().strftime("%Y-%m-%d")
    batches = conn.execute("""
        SELECT batch_id, quantity_remaining, expiry_date
        FROM batches
        WHERE product_id = ? AND quantity_remaining > 0 AND expiry_date >= ?
        ORDER BY expiry_date ASC
    """, (product_id, today)).fetchall()

    # Step D: check total available stock before touching anything
    total_available = sum(b["quantity_remaining"] for b in batches)
    if total_available < quantity_sold:
        conn.close()
        return jsonify({
            "error": f"Not enough stock. Only {total_available} units available (non-expired)."
        }), 400

    # Step E: deduct quantity across batches, oldest first (the actual FIFO logic)
    remaining_to_sell = quantity_sold
    batches_used = []   # keep track for the response, and to insert sale records

    try:
        for batch in batches:
            if remaining_to_sell <= 0:
                break

            take_from_this_batch = min(batch["quantity_remaining"], remaining_to_sell)
            new_remaining = batch["quantity_remaining"] - take_from_this_batch

            conn.execute("""
                UPDATE batches SET quantity_remaining = ? WHERE batch_id = ?
            """, (new_remaining, batch["batch_id"]))

            conn.execute("""
                INSERT INTO sales (product_id, batch_id, quantity_sold, sale_date, sold_by, buyer_id_proof)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (product_id, batch["batch_id"], take_from_this_batch, today, sold_by, buyer_id_proof))

            batches_used.append({
                "batch_id": batch["batch_id"],
                "quantity_taken": take_from_this_batch,
                "remaining_in_batch": new_remaining
            })

            remaining_to_sell -= take_from_this_batch

        conn.commit()   # only saves if everything above succeeded without error

    except Exception as e:
        conn.rollback()  # undo everything if something went wrong halfway
        conn.close()
        return jsonify({"error": f"Sale failed, nothing was changed: {str(e)}"}), 500

    conn.close()

    return jsonify({
        "message": "Sale recorded successfully",
        "product_name": product["name"],
        "total_quantity_sold": quantity_sold,
        "batches_used": batches_used
    }), 201
import os
# ---------------------------------------------------------
# GET /products - list all products (non-expired stock + status)
# ---------------------------------------------------------
@app.route("/products", methods=["GET"])
def get_products():
    conn = get_db_connection()
    products = get_products_with_stock(conn)
    conn.close()
    return jsonify(products)


# ---------------------------------------------------------
# GET /dashboard/summary - numbers for the dashboard cards
# ---------------------------------------------------------
@app.route("/dashboard/summary", methods=["GET"])
def dashboard_summary():
    conn = get_db_connection()
    today = today_str()
    soon = (datetime.today() + timedelta(days=30)).strftime("%Y-%m-%d")

    products = get_products_with_stock(conn)

    # value of stock that can actually be sold
    valid_value = conn.execute("""
        SELECT COALESCE(SUM(quantity_remaining * price_per_unit), 0) AS total
        FROM batches
        WHERE quantity_remaining > 0 AND expiry_date >= ?
    """, (today,)).fetchone()["total"]

    # value sitting in expired batches (money lost)
    expired = conn.execute("""
        SELECT COUNT(*) AS batches,
               COALESCE(SUM(quantity_remaining * price_per_unit), 0) AS value
        FROM batches
        WHERE quantity_remaining > 0 AND expiry_date < ?
    """, (today,)).fetchone()

    expiring_soon = conn.execute("""
        SELECT COUNT(*) AS c FROM batches
        WHERE quantity_remaining > 0 AND expiry_date >= ? AND expiry_date <= ?
    """, (today, soon)).fetchone()["c"]
    conn.close()

    return jsonify({
        "total_products": len(products),
        "healthy_count": sum(1 for p in products if p["status"] == "healthy"),
        "low_stock_count": sum(1 for p in products if p["status"] == "low_stock"),
        "out_of_stock_count": sum(1 for p in products if p["status"] == "out_of_stock"),
        "expiring_soon_count": expiring_soon,
        "expired_batch_count": expired["batches"],
        "total_inventory_value": round(valid_value, 2),
        "expired_stock_value": round(expired["value"], 2)
    })


# ---------------------------------------------------------
# GET /dashboard/low-stock
# ---------------------------------------------------------
@app.route("/dashboard/low-stock", methods=["GET"])
def dashboard_low_stock():
    conn = get_db_connection()
    products = get_products_with_stock(conn)
    conn.close()
    return jsonify([p for p in products if p["status"] == "low_stock"])


# ---------------------------------------------------------
# GET /dashboard/out-of-stock
# ---------------------------------------------------------
@app.route("/dashboard/out-of-stock", methods=["GET"])
def dashboard_out_of_stock():
    conn = get_db_connection()
    products = get_products_with_stock(conn)
    conn.close()
    return jsonify([p for p in products if p["status"] == "out_of_stock"])


# ---------------------------------------------------------
# GET /dashboard/expiring?days=30 - batches expiring soon
# ---------------------------------------------------------
@app.route("/dashboard/expiring", methods=["GET"])
def dashboard_expiring():
    days = request.args.get("days", 30, type=int)
    if days < 0:
        return jsonify({"error": "days must be zero or more"}), 400

    today = datetime.today().date()
    limit = today + timedelta(days=days)

    conn = get_db_connection()
    rows = conn.execute("""
        SELECT b.batch_id, b.batch_no, b.quantity_remaining, b.expiry_date,
               p.product_id, p.name AS product_name
        FROM batches b
        JOIN products p ON b.product_id = p.product_id
        WHERE b.quantity_remaining > 0
          AND b.expiry_date >= ? AND b.expiry_date <= ?
        ORDER BY b.expiry_date ASC
    """, (today.strftime("%Y-%m-%d"), limit.strftime("%Y-%m-%d"))).fetchall()
    conn.close()

    result = []
    for row in rows:
        item = dict(row)
        expiry = datetime.strptime(item["expiry_date"], "%Y-%m-%d").date()
        item["days_left"] = (expiry - today).days
        result.append(item)
    return jsonify(result)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)