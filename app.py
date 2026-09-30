from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3

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
# GET /products - list all products with total remaining stock
# ---------------------------------------------------------
@app.route("/products", methods=["GET"])
def get_products():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT p.product_id, p.name, p.brand, p.category, p.season,
               p.min_stock_level, p.is_restricted,
               COALESCE(SUM(b.quantity_remaining), 0) AS total_quantity
        FROM products p
        LEFT JOIN batches b ON p.product_id = b.product_id
        GROUP BY p.product_id
    """).fetchall()
    conn.close()

    products = [dict(row) for row in rows]
    return jsonify(products)


# ---------------------------------------------------------
# POST /products - add a new product (checks restricted list)
# ---------------------------------------------------------
@app.route("/products", methods=["POST"])
def add_product():
    data = request.get_json()

    if not data.get("name"):
        return jsonify({"error": "Product name is required"}), 400

    conn = get_db_connection()

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


if __name__ == "__main__":
    app.run(debug=True)