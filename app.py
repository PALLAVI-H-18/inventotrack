import os
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, get_jwt, get_jwt_identity, jwt_required, verify_jwt_in_request,
)
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

import db as database
import exports
import forecast
import stock
import suggestions
from compliance import MIN_BUYER_ID_LENGTH, fetch_restricted_sales, find_restricted_match
from validators import EMAIL_PATTERN, ApiError, Fields, json_body, query_date, query_int

app = Flask(__name__)

# =========================================================
# SETTINGS  (read from environment variables - Oct 19)
# =========================================================
# On Render, DATABASE_URL exists (PostgreSQL) and RENDER=true.  On your laptop neither exists.
IS_PRODUCTION = database.using_postgres() or os.environ.get("RENDER") == "true"

JWT_SECRET = os.environ.get("JWT_SECRET_KEY", "dev-only-change-me-in-production")
if IS_PRODUCTION and (JWT_SECRET == "dev-only-change-me-in-production" or len(JWT_SECRET) < 32):
    # Stop the server loudly instead of running with a guessable secret
    raise RuntimeError("Set the JWT_SECRET_KEY environment variable to a random string of 32+ characters.")
app.config["JWT_SECRET_KEY"] = JWT_SECRET
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024          # requests above 1 MB are rejected

# CORS_ORIGINS="https://my-frontend.onrender.com,http://localhost:5173"  (default: allow all)
origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
CORS(app, origins=origins, expose_headers=["Content-Disposition"])   # lets the browser read the download filename

jwt = JWTManager(app)
app.teardown_appcontext(database.close_db)

MAX_QUANTITY = 1_000_000
SEASONS = ["Kharif", "Rabi", "Monsoon", "Year-round"]


# =========================================================
# ONE ERROR FORMAT FOR EVERYTHING (Oct 16)
#   { "error": "message" }   or   { "error": "...", "details": { "field": "problem" } }
# =========================================================
def error_json(message, status, details=None):
    body = {"error": message}
    if details:
        body["details"] = details
    return jsonify(body), status


@app.errorhandler(ApiError)
def handle_api_error(e):
    return error_json(e.message, e.status, e.details)


@app.errorhandler(HTTPException)
def handle_http_error(e):
    messages = {
        404: "Route not found",
        405: "Method not allowed for this route",
        413: "Request is too large",
    }
    return error_json(messages.get(e.code, e.description or e.name), e.code)


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    app.logger.exception("Unexpected error")            # full details go to the server log only
    return error_json("Something went wrong on the server. Please try again.", 500)


@jwt.unauthorized_loader
def missing_token(reason):
    return error_json("Login required. Please log in first.", 401)


@jwt.invalid_token_loader
def invalid_token(reason):
    return error_json("Invalid login token. Please log in again.", 401)


@jwt.expired_token_loader
def expired_token(jwt_header, jwt_data):
    return error_json("Session expired. Please log in again.", 401)


def owner_required(fn):
    """Route is allowed only for a logged-in user whose role is 'owner'."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        if get_jwt().get("role") != "owner":
            return error_json("Owner access required", 403)
        return fn(*args, **kwargs)
    return wrapper


def get_product_or_404(db, product_id):
    product = db.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
    if product is None:
        raise ApiError("Product not found", 404)
    return product


# =========================================================
# PUBLIC
# =========================================================
@app.route("/")
def home():
    return jsonify({"message": "InventoTrack backend is running"})


@app.route("/health")
def health():
    """Used to check the live server and its database are working."""
    try:
        database.get_db().execute("SELECT 1").fetchone()
    except Exception:
        app.logger.exception("Health check failed")
        raise ApiError("Database unavailable", 503)
    return jsonify({"status": "ok", "database": "postgresql" if database.using_postgres() else "sqlite"})


# =========================================================
# AUTH
# =========================================================
@app.route("/auth/login", methods=["POST"])
def login():
    f = Fields(json_body())
    email = f.text("email", required=True, max_len=120)
    password = f.text("password", required=True, max_len=128, strip=False)
    f.done()

    db = database.get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()

    # Same message for "no such user" and "wrong password" so attackers cannot tell which was wrong.
    if user is None or not check_password_hash(user["password_hash"], password):
        raise ApiError("Invalid email or password", 401)

    token = create_access_token(
        identity=str(user["user_id"]),
        additional_claims={"role": user["role"], "name": user["name"]},
        expires_delta=timedelta(hours=8),
    )
    return jsonify({
        "token": token,
        "user": {"user_id": user["user_id"], "name": user["name"], "email": user["email"], "role": user["role"]},
    })


@app.route("/auth/me", methods=["GET"])
@jwt_required()
def me():
    claims = get_jwt()
    return jsonify({"user_id": int(get_jwt_identity()), "name": claims.get("name"), "role": claims.get("role")})


@app.route("/auth/register", methods=["POST"])
@owner_required
def register():
    f = Fields(json_body())
    name = f.text("name", required=True, max_len=100)
    email = f.text("email", required=True, max_len=120)
    password = f.text("password", required=True, min_len=6, max_len=128, strip=False)
    role = f.text("role", default="staff", choices=["owner", "staff"])
    if email and not EMAIL_PATTERN.match(email):
        f.error("email", "email must be a valid address like name@example.com")
    f.done()

    db = database.get_db()
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email.lower(),)).fetchone():
        raise ApiError("A user with this email already exists", 409, {"email": "already in use"})

    new_id = db.insert(
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (name, email.lower(), generate_password_hash(password), role), "user_id",
    )
    db.commit()
    return jsonify({"message": "User created", "user_id": new_id, "role": role}), 201


# =========================================================
# PRODUCTS
# =========================================================
@app.route("/products", methods=["GET"])
@jwt_required()
def get_products():
    return jsonify(stock.get_products_with_stock(database.get_db()))


@app.route("/products", methods=["POST"])
@owner_required
def add_product():
    f = Fields(json_body())
    name = f.text("name", required=True, max_len=120)
    brand = f.text("brand", max_len=100)
    category = f.text("category", max_len=60)
    season = f.text("season", choices=SEASONS, default="Year-round")
    min_stock = f.integer("min_stock_level", minimum=0, maximum=MAX_QUANTITY, default=10)
    f.done()

    db = database.get_db()
    if db.execute("SELECT 1 FROM products WHERE LOWER(name) = LOWER(?)", (name,)).fetchone():
        raise ApiError("A product with this name already exists", 409, {"name": "already exists"})

    match = find_restricted_match(db, name)
    is_restricted = 1 if match else 0

    new_id = db.insert(
        "INSERT INTO products (name, brand, category, season, min_stock_level, is_restricted) VALUES (?, ?, ?, ?, ?, ?)",
        (name, brand or None, category or None, season, min_stock, is_restricted), "product_id",
    )
    db.commit()

    response = {"message": "Product added successfully", "product_id": new_id, "is_restricted": bool(is_restricted)}
    if match:
        response["restricted_match"] = match["pesticide_name"]
        response["restricted_reason"] = match["reason"]
        response["warning"] = "Restricted pesticide: buyer identification is required at sale."
    return jsonify(response), 201


@app.route("/restricted-pesticides", methods=["GET"])
@jwt_required()
def list_restricted():
    rows = database.get_db().execute(
        "SELECT restricted_id, pesticide_name, reason FROM restricted_pesticides ORDER BY pesticide_name"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# =========================================================
# BATCHES
# =========================================================
@app.route("/batches", methods=["POST"])
@owner_required
def add_batch():
    f = Fields(json_body())
    product_id = f.integer("product_id", required=True, minimum=1)
    batch_no = f.text("batch_no", required=True, max_len=50)
    quantity = f.integer("quantity_received", required=True, minimum=1, maximum=MAX_QUANTITY)
    price = f.number("price_per_unit", required=True, greater_than=0, maximum=1_000_000)
    purchase_date = f.date("purchase_date", required=True)
    expiry_date = f.date("expiry_date", required=True)
    supplier_id = f.integer("supplier_id", minimum=1)

    if purchase_date and purchase_date > stock.today_str():
        f.error("purchase_date", "purchase_date cannot be in the future")
    if purchase_date and expiry_date and expiry_date <= purchase_date:
        f.error("expiry_date", "expiry_date must be after purchase_date")
    f.done()

    db = database.get_db()
    get_product_or_404(db, product_id)
    if supplier_id is not None and db.execute("SELECT 1 FROM suppliers WHERE supplier_id = ?", (supplier_id,)).fetchone() is None:
        raise ApiError("Supplier not found", 400, {"supplier_id": "no supplier with this id"})
    if db.execute("SELECT 1 FROM batches WHERE product_id = ? AND batch_no = ?", (product_id, batch_no)).fetchone():
        raise ApiError("This batch number already exists for this product", 409, {"batch_no": "already used for this product"})

    new_id = db.insert("""
        INSERT INTO batches (product_id, supplier_id, batch_no, quantity_received, quantity_remaining,
                             price_per_unit, purchase_date, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (product_id, supplier_id, batch_no, quantity, quantity, price, purchase_date, expiry_date), "batch_id")
    db.commit()
    return jsonify({"message": "Batch added successfully", "batch_id": new_id}), 201


@app.route("/products/<int:product_id>/batches", methods=["GET"])
@jwt_required()
def get_batches_for_product(product_id):
    db = database.get_db()
    product = get_product_or_404(db, product_id)
    rows = db.execute("""
        SELECT batch_id, batch_no, quantity_received, quantity_remaining,
               price_per_unit, purchase_date, expiry_date, supplier_id
        FROM batches WHERE product_id = ? ORDER BY expiry_date ASC, batch_id ASC
    """, (product_id,)).fetchall()
    batches = [dict(r) for r in rows]

    if get_jwt().get("role") != "owner":           # staff must not see purchase prices
        for b in batches:
            b.pop("price_per_unit", None)
    return jsonify({"product_name": product["name"], "batches": batches})


# =========================================================
# SALES (FIFO)
# =========================================================
@app.route("/sales", methods=["POST"])
@jwt_required()
def record_sale():
    f = Fields(json_body())
    product_id = f.integer("product_id", required=True, minimum=1)
    quantity_sold = f.integer("quantity_sold", required=True, minimum=1, maximum=MAX_QUANTITY)
    buyer_id_proof = f.text("buyer_id_proof", max_len=100, default="")     # spaces-only becomes ""
    f.done()
    sold_by = int(get_jwt_identity())            # always the logged-in user, never taken from the request

    db = database.get_db()
    db.begin_write()                             # lock so two simultaneous sales cannot sell the same stock
    product = get_product_or_404(db, product_id)

    # Compliance rule: a restricted pesticide cannot be sold without a real buyer ID
    if product["is_restricted"]:
        if not buyer_id_proof:
            raise ApiError("This product is restricted. Buyer identification is required to complete this sale.",
                           400, {"buyer_id_proof": "required for restricted pesticides"})
        if len(buyer_id_proof) < MIN_BUYER_ID_LENGTH:
            raise ApiError(f"Buyer ID is too short. Enter at least {MIN_BUYER_ID_LENGTH} characters.",
                           400, {"buyer_id_proof": f"at least {MIN_BUYER_ID_LENGTH} characters"})

    today = stock.today_str()
    batches = db.execute(f"""
        SELECT batch_id, quantity_remaining, expiry_date
        FROM batches
        WHERE product_id = ? AND quantity_remaining > 0 AND expiry_date >= ?
        ORDER BY expiry_date ASC, batch_id ASC{db.lock_clause}
    """, (product_id, today)).fetchall()

    total_available = sum(b["quantity_remaining"] for b in batches)
    if total_available < quantity_sold:
        raise ApiError(f"Not enough stock. Only {total_available} units available (non-expired).", 400,
                       {"quantity_sold": f"only {total_available} available"})

    remaining_to_sell = quantity_sold
    batches_used = []
    for batch in batches:                        # oldest expiry first = FIFO
        if remaining_to_sell <= 0:
            break
        take = min(batch["quantity_remaining"], remaining_to_sell)
        new_remaining = batch["quantity_remaining"] - take

        db.execute("UPDATE batches SET quantity_remaining = ? WHERE batch_id = ?", (new_remaining, batch["batch_id"]))
        db.execute("""
            INSERT INTO sales (product_id, batch_id, quantity_sold, sale_date, sold_by, buyer_id_proof)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (product_id, batch["batch_id"], take, today, sold_by, buyer_id_proof or None))

        batches_used.append({"batch_id": batch["batch_id"], "quantity_taken": take, "remaining_in_batch": new_remaining})
        remaining_to_sell -= take

    db.commit()                                  # nothing is saved unless everything above worked
    return jsonify({
        "message": "Sale recorded successfully",
        "product_name": product["name"],
        "total_quantity_sold": quantity_sold,
        "batches_used": batches_used,
    }), 201


# =========================================================
# DASHBOARD
# =========================================================
@app.route("/dashboard/summary", methods=["GET"])
@owner_required          # contains money values, so owner only
def dashboard_summary():
    db = database.get_db()
    today = stock.today_str()
    soon = (stock.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    products = stock.get_products_with_stock(db)

    valid_value = db.execute("""
        SELECT COALESCE(SUM(quantity_remaining * price_per_unit), 0) AS total FROM batches
        WHERE quantity_remaining > 0 AND expiry_date >= ?
    """, (today,)).fetchone()["total"]
    expired = db.execute("""
        SELECT COUNT(*) AS batches, COALESCE(SUM(quantity_remaining * price_per_unit), 0) AS value FROM batches
        WHERE quantity_remaining > 0 AND expiry_date < ?
    """, (today,)).fetchone()
    expiring_soon = db.execute("""
        SELECT COUNT(*) AS c FROM batches
        WHERE quantity_remaining > 0 AND expiry_date >= ? AND expiry_date <= ?
    """, (today, soon)).fetchone()["c"]

    return jsonify({
        "total_products": len(products),
        "healthy_count": sum(1 for p in products if p["status"] == "healthy"),
        "low_stock_count": sum(1 for p in products if p["status"] == "low_stock"),
        "out_of_stock_count": sum(1 for p in products if p["status"] == "out_of_stock"),
        "expiring_soon_count": int(expiring_soon),
        "expired_batch_count": int(expired["batches"]),
        "total_inventory_value": round(float(valid_value), 2),
        "expired_stock_value": round(float(expired["value"]), 2),
    })


@app.route("/dashboard/low-stock", methods=["GET"])
@jwt_required()
def dashboard_low_stock():
    products = stock.get_products_with_stock(database.get_db())
    return jsonify([p for p in products if p["status"] == "low_stock"])


@app.route("/dashboard/out-of-stock", methods=["GET"])
@jwt_required()
def dashboard_out_of_stock():
    products = stock.get_products_with_stock(database.get_db())
    return jsonify([p for p in products if p["status"] == "out_of_stock"])


@app.route("/dashboard/expiring", methods=["GET"])
@jwt_required()
def dashboard_expiring():
    days = query_int("days", default=30, minimum=0, maximum=3650)
    today = stock.today()
    limit = today + timedelta(days=days)

    rows = database.get_db().execute("""
        SELECT b.batch_id, b.batch_no, b.quantity_remaining, b.expiry_date,
               p.product_id, p.name AS product_name
        FROM batches b JOIN products p ON b.product_id = p.product_id
        WHERE b.quantity_remaining > 0 AND b.expiry_date >= ? AND b.expiry_date <= ?
        ORDER BY b.expiry_date ASC, b.batch_id ASC
    """, (today.strftime("%Y-%m-%d"), limit.strftime("%Y-%m-%d"))).fetchall()

    result = []
    for row in rows:
        item = dict(row)
        item["days_left"] = (datetime.strptime(item["expiry_date"], "%Y-%m-%d").date() - today).days
        result.append(item)
    return jsonify(result)


# =========================================================
# COMPLIANCE LOG (Oct 11)
# =========================================================
def read_date_range():
    date_from, date_to = query_date("from"), query_date("to")
    if date_from and date_to and date_from > date_to:
        raise ApiError("'from' date must not be after 'to' date", 400, {"from": "must not be after 'to'"})
    return date_from, date_to


@app.route("/reports/restricted-sales", methods=["GET"])
@owner_required
def restricted_sales_report():
    date_from, date_to = read_date_range()
    missing_only = request.args.get("missing_only", "").lower() == "true"
    summary, records = fetch_restricted_sales(database.get_db(), date_from, date_to, missing_only)
    return jsonify({"summary": summary, "records": records})


# =========================================================
# FORECAST (Oct 12-13) - owner only
# =========================================================
@app.route("/forecast/history/<int:product_id>", methods=["GET"])
@owner_required
def forecast_history(product_id):
    db = database.get_db()
    product = get_product_or_404(db, product_id)
    series = forecast.monthly_history(db, product_id)
    return jsonify({
        "product_id": product_id,
        "product_name": product["name"],
        "season": product["season"],
        "months": [{"month": str(m), "quantity": int(q)} for m, q in series.items()],
    })


@app.route("/forecast/<int:product_id>", methods=["GET"])
@owner_required
def forecast_one(product_id):
    result = forecast.forecast_product(database.get_db(), product_id)
    if result is None:
        raise ApiError("Product not found", 404)
    return jsonify(result)


@app.route("/forecast", methods=["GET"])
@owner_required
def forecast_every_product():
    return jsonify(forecast.forecast_all(database.get_db()))


# =========================================================
# RESTOCK SUGGESTIONS (Oct 14) - owner only
# =========================================================
@app.route("/suggestions/seasonal/<int:product_id>", methods=["GET"])
@owner_required
def suggestion_one(product_id):
    result = suggestions.build_suggestion(database.get_db(), product_id)
    if result is None:
        raise ApiError("Product not found", 404)
    return jsonify(result)


@app.route("/suggestions", methods=["GET"])
@owner_required
def suggestion_all():
    only_needed = request.args.get("only_needed", "").lower() == "true"
    summary, items = suggestions.build_all_suggestions(database.get_db(), only_needed=only_needed)
    return jsonify({"summary": summary, "suggestions": items})


# =========================================================
# EXCEL EXPORTS (Oct 15) - owner only
# =========================================================
def send_excel(buffer, name):
    filename = f"{name}_{stock.today_str()}.xlsx"
    return send_file(buffer, mimetype=exports.XLSX_MIME, as_attachment=True, download_name=filename)


@app.route("/reports/inventory/export", methods=["GET"])
@owner_required
def export_inventory():
    return send_excel(exports.inventory_workbook(database.get_db()), "inventory")


@app.route("/reports/sales/export", methods=["GET"])
@owner_required
def export_sales():
    date_from, date_to = read_date_range()
    return send_excel(exports.sales_workbook(database.get_db(), date_from, date_to), "sales")


@app.route("/reports/compliance/export", methods=["GET"])
@owner_required
def export_compliance():
    date_from, date_to = read_date_range()
    missing_only = request.args.get("missing_only", "").lower() == "true"
    return send_excel(exports.compliance_workbook(database.get_db(), date_from, date_to, missing_only), "compliance_log")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=not IS_PRODUCTION)
