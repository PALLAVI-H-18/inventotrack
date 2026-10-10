import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required,
    get_jwt, get_jwt_identity, verify_jwt_in_request,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)

# Secret used to sign login tokens. On Render this comes from an environment variable.
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "dev-only-change-me-in-production")
jwt = JWTManager(app)

DB_NAME = "inventotrack.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# AUTH HELPERS (Oct 8-9)
# =========================================================
# Keep every auth error in the same {"error": "..."} shape the frontend expects.
@jwt.unauthorized_loader
def missing_token(reason):
    return jsonify({"error": "Login required. Please log in first."}), 401


@jwt.invalid_token_loader
def invalid_token(reason):
    return jsonify({"error": "Invalid login token. Please log in again."}), 401


@jwt.expired_token_loader
def expired_token(jwt_header, jwt_data):
    return jsonify({"error": "Session expired. Please log in again."}), 401


def owner_required(fn):
    """Route is allowed only for a logged-in user whose role is 'owner'."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        if get_jwt().get("role") != "owner":
            return jsonify({"error": "Owner access required"}), 403
        return fn(*args, **kwargs)
    return wrapper


# =========================================================
# STOCK HELPERS
# =========================================================
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


# =========================================================
# COMPLIANCE HELPER (Oct 10)
# =========================================================
def find_restricted_match(conn, product_name):
    """
    Returns the restricted_pesticides row that matches this product name, or None.

    A product matches when:
      1. the restricted name appears inside the product name
         ("Monocrotophos 36% SL" matches "Monocrotophos"), or
      2. the first word (the active ingredient) is the same
         ("Paraquat 24% SL" matches "Paraquat Dichloride").
    Case is ignored.
    """
    name = (product_name or "").strip().lower()
    if not name:
        return None
    first_word = name.split()[0]

    rows = conn.execute(
        "SELECT pesticide_name, reason FROM restricted_pesticides"
    ).fetchall()
    for row in rows:
        restricted = row["pesticide_name"].strip().lower()
        if restricted in name:
            return row
        if len(first_word) >= 5 and first_word == restricted.split()[0]:
            return row
    return None


# =========================================================
# PUBLIC
# =========================================================
@app.route("/")
def home():
    return jsonify({"message": "InventoTrack backend is running"})


# =========================================================
# AUTH ROUTES
# =========================================================
@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    # Same message for "no such user" and "wrong password" so attackers can't tell which.
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_access_token(
        identity=str(user["user_id"]),            # identity must be a string
        additional_claims={"role": user["role"], "name": user["name"]},
        expires_delta=timedelta(hours=8),
    )
    return jsonify({
        "token": token,
        "user": {
            "user_id": user["user_id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        },
    })


@app.route("/auth/me", methods=["GET"])
@jwt_required()
def me():
    claims = get_jwt()
    return jsonify({
        "user_id": int(get_jwt_identity()),
        "name": claims.get("name"),
        "role": claims.get("role"),
    })


@app.route("/auth/register", methods=["POST"])
@owner_required
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role", "staff")

    if not name or not email or not password:
        return jsonify({"error": "name, email and password are required"}), 400
    if "@" not in email:
        return jsonify({"error": "Enter a valid email address"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if role not in ("owner", "staff"):
        return jsonify({"error": "role must be 'owner' or 'staff'"}), 400

    conn = get_db_connection()
    exists = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
    if exists:
        conn.close()
        return jsonify({"error": "A user with this email already exists"}), 409

    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (name, email, generate_password_hash(password), role),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    return jsonify({"message": "User created", "user_id": new_id, "role": role}), 201


# =========================================================
# PRODUCTS
# =========================================================
@app.route("/products", methods=["GET"])
@jwt_required()
def get_products():
    conn = get_db_connection()
    products = get_products_with_stock(conn)
    conn.close()
    return jsonify(products)


@app.route("/products", methods=["POST"])
@owner_required
def add_product():
    data = request.get_json(silent=True) or {}

    if not data.get("name"):
        return jsonify({"error": "Product name is required"}), 400

    conn = get_db_connection()

    match = find_restricted_match(conn, data.get("name"))
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

    response = {
        "message": "Product added successfully",
        "product_id": new_id,
        "is_restricted": bool(is_restricted),
    }
    if match:
        response["restricted_match"] = match["pesticide_name"]
        response["restricted_reason"] = match["reason"]
        response["warning"] = "Restricted pesticide: buyer identification is required at sale."
    return jsonify(response), 201


@app.route("/restricted-pesticides", methods=["GET"])
@jwt_required()
def list_restricted():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT restricted_id, pesticide_name, reason FROM restricted_pesticides ORDER BY pesticide_name"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# =========================================================
# BATCHES
# =========================================================
@app.route("/batches", methods=["POST"])
@owner_required
def add_batch():
    data = request.get_json(silent=True) or {}

    required_fields = ["product_id", "batch_no", "quantity_received",
                       "price_per_unit", "purchase_date", "expiry_date"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    conn = get_db_connection()

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
        quantity_received,
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


@app.route("/products/<int:product_id>/batches", methods=["GET"])
@jwt_required()
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

    # Staff must not see purchase prices.
    if get_jwt().get("role") != "owner":
        for b in batches:
            b.pop("price_per_unit", None)

    return jsonify({"product_name": product["name"], "batches": batches})


# =========================================================
# SALES (FIFO)
# =========================================================
@app.route("/sales", methods=["POST"])
@jwt_required()
def record_sale():
    data = request.get_json(silent=True) or {}

    product_id = data.get("product_id")
    quantity_sold = data.get("quantity_sold")
    buyer_id_proof = data.get("buyer_id_proof")
    sold_by = int(get_jwt_identity())   # always the logged-in user, never from the request body

    if not product_id or not quantity_sold or quantity_sold <= 0:
        return jsonify({"error": "product_id and a positive quantity_sold are required"}), 400

    conn = get_db_connection()

    product = conn.execute(
        "SELECT * FROM products WHERE product_id = ?", (product_id,)
    ).fetchone()
    if product is None:
        conn.close()
        return jsonify({"error": "Product not found"}), 404

    if product["is_restricted"] and not buyer_id_proof:
        conn.close()
        return jsonify({
            "error": "This product is restricted. Buyer identification is required to complete this sale."
        }), 400

    today = today_str()
    batches = conn.execute("""
        SELECT batch_id, quantity_remaining, expiry_date
        FROM batches
        WHERE product_id = ? AND quantity_remaining > 0 AND expiry_date >= ?
        ORDER BY expiry_date ASC
    """, (product_id, today)).fetchall()

    total_available = sum(b["quantity_remaining"] for b in batches)
    if total_available < quantity_sold:
        conn.close()
        return jsonify({
            "error": f"Not enough stock. Only {total_available} units available (non-expired)."
        }), 400

    remaining_to_sell = quantity_sold
    batches_used = []

    try:
        for batch in batches:
            if remaining_to_sell <= 0:
                break

            take = min(batch["quantity_remaining"], remaining_to_sell)
            new_remaining = batch["quantity_remaining"] - take

            conn.execute(
                "UPDATE batches SET quantity_remaining = ? WHERE batch_id = ?",
                (new_remaining, batch["batch_id"])
            )
            conn.execute("""
                INSERT INTO sales (product_id, batch_id, quantity_sold, sale_date, sold_by, buyer_id_proof)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (product_id, batch["batch_id"], take, today, sold_by, buyer_id_proof))

            batches_used.append({
                "batch_id": batch["batch_id"],
                "quantity_taken": take,
                "remaining_in_batch": new_remaining
            })
            remaining_to_sell -= take

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": f"Sale failed, nothing was changed: {str(e)}"}), 500

    conn.close()
    return jsonify({
        "message": "Sale recorded successfully",
        "product_name": product["name"],
        "total_quantity_sold": quantity_sold,
        "batches_used": batches_used
    }), 201


# =========================================================
# DASHBOARD
# =========================================================
@app.route("/dashboard/summary", methods=["GET"])
@owner_required          # contains money values, so owner only
def dashboard_summary():
    conn = get_db_connection()
    today = today_str()
    soon = (datetime.today() + timedelta(days=30)).strftime("%Y-%m-%d")

    products = get_products_with_stock(conn)

    valid_value = conn.execute("""
        SELECT COALESCE(SUM(quantity_remaining * price_per_unit), 0) AS total
        FROM batches
        WHERE quantity_remaining > 0 AND expiry_date >= ?
    """, (today,)).fetchone()["total"]

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


@app.route("/dashboard/low-stock", methods=["GET"])
@jwt_required()
def dashboard_low_stock():
    conn = get_db_connection()
    products = get_products_with_stock(conn)
    conn.close()
    return jsonify([p for p in products if p["status"] == "low_stock"])


@app.route("/dashboard/out-of-stock", methods=["GET"])
@jwt_required()
def dashboard_out_of_stock():
    conn = get_db_connection()
    products = get_products_with_stock(conn)
    conn.close()
    return jsonify([p for p in products if p["status"] == "out_of_stock"])


@app.route("/dashboard/expiring", methods=["GET"])
@jwt_required()
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