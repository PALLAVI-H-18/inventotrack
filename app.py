import os
import sqlite3
import math
from io import BytesIO
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required,
    get_jwt, get_jwt_identity, verify_jwt_in_request,
)
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook

from database import DB_NAME
from forecast import SEASON_MONTHS, monthly_history, forecast_product, forecast_all

app = Flask(__name__)
CORS(app)

app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "dev-only-change-me-in-production"
)
if (
    os.environ.get("FLASK_ENV") == "production" or os.environ.get("RENDER") == "true"
) and app.config["JWT_SECRET_KEY"] == "dev-only-change-me-in-production":
    raise RuntimeError("JWT_SECRET_KEY must be set to a secure value in production")
jwt = JWTManager(app)

# A restricted-pesticide sale needs a buyer ID of at least this many characters (Oct 11)
MIN_BUYER_ID_LENGTH = 4


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@app.errorhandler(HTTPException)
def http_error(error):
    return jsonify({"error": error.description}), error.code


@app.errorhandler(Exception)
def unexpected_error(error):
    app.logger.exception("Unhandled API error: %s", error)
    return jsonify({"error": "An unexpected server error occurred"}), 500


def read_json_object():
    """Return a JSON object or a consistent validation response."""
    if not request.is_json:
        return None, (jsonify({"error": "Content-Type must be application/json"}), 400)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "Request body must be a JSON object"}), 400)
    return data, None


def is_integer(value, minimum=None):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and (minimum is None or value >= minimum)
    )


def is_iso_date(value):
    if not isinstance(value, str):
        return False
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") == value
    except ValueError:
        return False


def excel_response(filename, sheet_name, headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(headers)
    for row in rows:
        values = []
        for header in headers:
            value = row.get(header)
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                value = "'" + value
            values.append(value)
        sheet.append(values)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


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
    data, error = read_json_object()
    if error:
        return error
    email = data.get("email")
    password = data.get("password")

    if not isinstance(email, str) or not isinstance(password, str) or not email.strip() or not password:
        return jsonify({"error": "Email and password are required"}), 400
    email = email.strip().lower()
    if "@" not in email:
        return jsonify({"error": "Enter a valid email address"}), 400

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
    data, error = read_json_object()
    if error:
        return error
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "staff")

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name is required"}), 400
    if not isinstance(email, str) or not isinstance(password, str) or not password:
        return jsonify({"error": "name, email and password are required"}), 400
    name = name.strip()
    email = email.strip().lower()
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
    data, error = read_json_object()
    if error:
        return error

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "Product name is required"}), 400
    min_stock_level = data.get("min_stock_level", 10)
    if not is_integer(min_stock_level, 0):
        return jsonify({"error": "min_stock_level must be a non-negative integer"}), 400
    for field in ("brand", "category", "season"):
        if data.get(field) is not None and not isinstance(data[field], str):
            return jsonify({"error": f"{field} must be a string"}), 400

    conn = get_db_connection()

    match = find_restricted_match(conn, name.strip())
    is_restricted = 1 if match else 0

    cur = conn.execute("""
        INSERT INTO products (name, brand, category, season, min_stock_level, is_restricted)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        name.strip(),
        data.get("brand"),
        data.get("category"),
        data.get("season"),
        min_stock_level,
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


@app.route("/reports/inventory/export", methods=["GET"])
@owner_required
def export_inventory():
    conn = get_db_connection()
    products = get_products_with_stock(conn)
    conn.close()
    headers = [
        "product_id", "name", "brand", "category", "season",
        "min_stock_level", "is_restricted", "total_quantity", "status",
    ]
    return excel_response(
        "inventory.xlsx", "Inventory", headers, products
    )


# =========================================================
# BATCHES
# =========================================================
@app.route("/batches", methods=["POST"])
@owner_required
def add_batch():
    data, error = read_json_object()
    if error:
        return error

    required_fields = ["product_id", "batch_no", "quantity_received",
                       "price_per_unit", "purchase_date", "expiry_date"]
    missing = [f for f in required_fields if f not in data or data[f] is None or data[f] == ""]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    if not is_integer(data["product_id"], 1):
        return jsonify({"error": "product_id must be a positive integer"}), 400
    if not isinstance(data["batch_no"], str) or not data["batch_no"].strip():
        return jsonify({"error": "batch_no must be a non-empty string"}), 400
    if not is_integer(data["quantity_received"], 1):
        return jsonify({"error": "quantity_received must be a positive integer"}), 400
    price = data["price_per_unit"]
    if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price < 0:
        return jsonify({"error": "price_per_unit must be a non-negative number"}), 400
    if not is_iso_date(data["purchase_date"]) or not is_iso_date(data["expiry_date"]):
        return jsonify({"error": "purchase_date and expiry_date must use YYYY-MM-DD"}), 400
    if data["expiry_date"] < data["purchase_date"]:
        return jsonify({"error": "expiry_date must not be before purchase_date"}), 400
    if data.get("supplier_id") is not None and not is_integer(data["supplier_id"], 1):
        return jsonify({"error": "supplier_id must be a positive integer"}), 400

    conn = get_db_connection()

    product = conn.execute(
        "SELECT * FROM products WHERE product_id = ?", (data["product_id"],)
    ).fetchone()
    if product is None:
        conn.close()
        return jsonify({"error": "Product not found"}), 404

    quantity_received = data["quantity_received"]

    cur = conn.execute("""
        INSERT INTO batches (product_id, supplier_id, batch_no, quantity_received,
                             quantity_remaining, price_per_unit, purchase_date, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["product_id"],
        data.get("supplier_id"),
        data["batch_no"].strip(),
        quantity_received,
        quantity_received,
        price,
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
    data, error = read_json_object()
    if error:
        return error

    product_id = data.get("product_id")
    quantity_sold = data.get("quantity_sold")
    buyer_id_proof = data.get("buyer_id_proof", "")
    if not is_integer(product_id, 1) or not is_integer(quantity_sold, 1):
        return jsonify({"error": "product_id and a positive integer quantity_sold are required"}), 400
    if not isinstance(buyer_id_proof, str):
        return jsonify({"error": "buyer_id_proof must be a string"}), 400
    buyer_id_proof = buyer_id_proof.strip()
    sold_by = int(get_jwt_identity())   # always the logged-in user, never from the request body

    conn = get_db_connection()

    product = conn.execute(
        "SELECT * FROM products WHERE product_id = ?", (product_id,)
    ).fetchone()
    if product is None:
        conn.close()
        return jsonify({"error": "Product not found"}), 404

    # Compliance rule (Oct 11): a restricted pesticide cannot be sold without a real buyer ID
    if product["is_restricted"]:
        if not buyer_id_proof:
            conn.close()
            return jsonify({
                "error": "This product is restricted. Buyer identification is required to complete this sale."
            }), 400
        if len(buyer_id_proof) < MIN_BUYER_ID_LENGTH:
            conn.close()
            return jsonify({
                "error": f"Buyer ID is too short. Enter at least {MIN_BUYER_ID_LENGTH} characters."
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
            """, (product_id, batch["batch_id"], take, today, sold_by, buyer_id_proof or None))

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
    days_arg = request.args.get("days", "30")
    try:
        days = int(days_arg)
    except ValueError:
        return jsonify({"error": "days must be a non-negative integer"}), 400
    if days < 0 or str(days) != days_arg.strip():
        return jsonify({"error": "days must be a non-negative integer"}), 400

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


# =========================================================
# COMPLIANCE LOG (Oct 11)
# =========================================================
def read_date_arg(name):
    """Reads ?from=2026-10-01 style dates. Returns (value, error_message)."""
    value = request.args.get(name)
    if not value:
        return None, None
    if not is_iso_date(value):
        return None, f"'{name}' must be a date like 2026-10-31"
    return value, None


def get_restricted_sales_records(conn, date_from=None, date_to=None, missing_only=False):
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
    rows = conn.execute(query, params).fetchall()
    records = []
    for row in rows:
        item = dict(row)
        item["has_buyer_id"] = bool(item["buyer_id_proof"] and item["buyer_id_proof"].strip())
        records.append(item)
    with_id = sum(1 for record in records if record["has_buyer_id"])
    return {
        "summary": {
            "total_records": len(records),
            "total_units": sum(record["quantity_sold"] for record in records),
            "with_buyer_id": with_id,
            "missing_buyer_id": len(records) - with_id,
        },
        "records": records,
    }


def read_compliance_filters():
    date_from, error = read_date_arg("from")
    if error:
        return None, error
    date_to, error = read_date_arg("to")
    if error:
        return None, error
    if date_from and date_to and date_from > date_to:
        return None, "'from' date must not be after 'to' date"
    missing_arg = request.args.get("missing_only", "").lower()
    if missing_arg not in ("", "true", "false"):
        return None, "missing_only must be true or false"
    return (date_from, date_to, missing_arg == "true"), None


@app.route("/reports/restricted-sales", methods=["GET"])
@owner_required
def restricted_sales_report():
    """
    The compliance log: every sale of a restricted pesticide, with the buyer ID.
      ?from=2026-10-01&to=2026-10-31   only this date range
      ?missing_only=true               only sales that have NO buyer ID
    """
    filters, error = read_compliance_filters()
    if error:
        return jsonify({"error": error}), 400
    date_from, date_to, missing_only = filters

    conn = get_db_connection()
    result = get_restricted_sales_records(conn, date_from, date_to, missing_only)
    conn.close()
    return jsonify(result)


@app.route("/reports/sales/export", methods=["GET"])
@owner_required
def export_sales():
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT s.sale_id, s.sale_date, p.product_id, p.name AS product_name,
               b.batch_no, s.quantity_sold, s.buyer_id_proof,
               u.name AS sold_by_name
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        JOIN batches b ON s.batch_id = b.batch_id
        LEFT JOIN users u ON s.sold_by = u.user_id
        ORDER BY s.sale_date DESC, s.sale_id DESC
    """).fetchall()
    conn.close()
    headers = [
        "sale_id", "sale_date", "product_id", "product_name", "batch_no",
        "quantity_sold", "buyer_id_proof", "sold_by_name",
    ]
    return excel_response("sales.xlsx", "Sales", headers, [dict(row) for row in rows])


@app.route("/reports/compliance/export", methods=["GET"])
@owner_required
def export_compliance():
    filters, error = read_compliance_filters()
    if error:
        return jsonify({"error": error}), 400
    date_from, date_to, missing_only = filters
    conn = get_db_connection()
    result = get_restricted_sales_records(conn, date_from, date_to, missing_only)
    conn.close()
    headers = [
        "sale_id", "sale_date", "product_id", "product_name", "batch_no",
        "quantity_sold", "buyer_id_proof", "has_buyer_id", "sold_by_name",
    ]
    return excel_response(
        "compliance-log.xlsx", "Compliance Log", headers, result["records"]
    )


# =========================================================
# FORECAST (Oct 12 + Oct 13) - owner only
# =========================================================
@app.route("/forecast/history/<int:product_id>", methods=["GET"])
@owner_required
def forecast_history(product_id):
    """Oct 12: units sold per month (the clean table the model learns from)."""
    conn = get_db_connection()
    product = conn.execute(
        "SELECT name, season FROM products WHERE product_id = ?", (product_id,)
    ).fetchone()
    conn.close()
    if product is None:
        return jsonify({"error": "Product not found"}), 404

    series = monthly_history(DB_NAME, product_id)
    return jsonify({
        "product_id": product_id,
        "product_name": product["name"],
        "season": product["season"],
        "months": [{"month": str(m), "quantity": int(q)} for m, q in series.items()],
    })


@app.route("/forecast/<int:product_id>", methods=["GET"])
@owner_required
def forecast_one(product_id):
    """Oct 13: next month's demand for one product, with all three methods compared."""
    result = forecast_product(DB_NAME, product_id)
    if result is None:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(result)


@app.route("/forecast", methods=["GET"])
@owner_required
def forecast_every_product():
    """Oct 13: one prediction per product."""
    return jsonify(forecast_all(DB_NAME))


def make_restock_suggestion(product, forecast):
    target_date = datetime.today().date().replace(day=28) + timedelta(days=4)
    target_date = target_date.replace(day=1)
    season = product["season"] or "Unspecified"
    in_season = target_date.month in SEASON_MONTHS.get(season, range(1, 13))
    current_stock = product["total_quantity"]
    minimum_stock = product["min_stock_level"]

    if forecast["enough_data"]:
        demand = forecast["predicted_demand"]
        target_stock = max(minimum_stock, demand)
        basis = (
            f"{forecast['best_method_label']} predicts {demand} units for "
            f"{forecast['forecast_month']} (backtest MAE "
            f"{next(method['mae'] for method in forecast['methods'] if method['method'] == forecast['best_method'])} "
            f"units)."
        )
        forecast_month = forecast["forecast_month"]
    else:
        demand = None
        target_stock = minimum_stock
        forecast_month = None
        basis = (
            f"Sales history is not yet long enough for a reliable forecast; "
            f"the minimum stock level of {minimum_stock} units is used."
        )

    recommended_quantity = max(0, target_stock - current_stock)
    season_description = "in season" if in_season else "out of season"
    why = (
        f"Basis: {basis} Season: {season} is {season_description} for the forecast month. "
        f"Current usable stock is {current_stock} units; target stock is {target_stock} "
        f"units. Restock {recommended_quantity} units."
    )
    return {
        "product_id": product["product_id"],
        "product_name": product["name"],
        "season": season,
        "forecast_month": forecast_month,
        "in_season": in_season,
        "enough_data": forecast["enough_data"],
        "best_method": forecast.get("best_method"),
        "predicted_demand": demand,
        "current_stock": current_stock,
        "minimum_stock": minimum_stock,
        "target_stock": target_stock,
        "recommended_restock_quantity": recommended_quantity,
        "why": why,
    }


@app.route("/suggestions/seasonal/<int:product_id>", methods=["GET"])
@owner_required
def seasonal_suggestion(product_id):
    conn = get_db_connection()
    product = next(
        (item for item in get_products_with_stock(conn) if item["product_id"] == product_id),
        None,
    )
    conn.close()
    if product is None:
        return jsonify({"error": "Product not found"}), 404
    forecast = forecast_product(DB_NAME, product_id)
    return jsonify(make_restock_suggestion(product, forecast))


@app.route("/suggestions/seasonal", methods=["GET"])
@owner_required
def all_seasonal_suggestions():
    conn = get_db_connection()
    products = get_products_with_stock(conn)
    conn.close()
    return jsonify([
        make_restock_suggestion(product, forecast_product(DB_NAME, product["product_id"]))
        for product in products
    ])



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")