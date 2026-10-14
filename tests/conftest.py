"""
conftest.py - shared setup for every test file.
pytest runs this automatically. Each test gets its OWN fresh, temporary SQLite database,
so tests never disturb your real inventotrack.db and never disturb each other.
"""
import os
import sys
from datetime import timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # so "import app" works

os.environ.pop("DATABASE_URL", None)                       # tests must never touch PostgreSQL
os.environ.pop("RENDER", None)
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-that-is-long-enough-123456"

import pytest                                              # noqa: E402
from werkzeug.security import generate_password_hash       # noqa: E402

import db as database                                      # noqa: E402
import stock                                               # noqa: E402
from app import app as flask_app                           # noqa: E402


def day(offset):
    """A date string relative to today: day(0)=today, day(30)=in 30 days, day(-5)=5 days ago."""
    return (stock.today() + timedelta(days=offset)).strftime("%Y-%m-%d")


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A tiny shop:  Neem Oil (not restricted) with 3 batches, Monocrotophos (restricted) with 1."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    conn = database.connect()
    database.init_schema(conn)

    def add_user(name, email, password, role):
        return conn.insert("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                           (name, email, generate_password_hash(password), role), "user_id")

    owner_id = add_user("Test Owner", "owner@test.com", "Owner@123", "owner")
    staff_id = add_user("Test Staff", "staff@test.com", "Staff@123", "staff")

    conn.execute("INSERT INTO restricted_pesticides (pesticide_name, reason) VALUES (?, ?)", ("Monocrotophos", "Highly toxic"))
    conn.execute("INSERT INTO suppliers (name) VALUES (?)", ("Test Supplier",))

    def add_product(name, season, min_stock, restricted):
        return conn.insert("INSERT INTO products (name, brand, season, min_stock_level, is_restricted) VALUES (?, ?, ?, ?, ?)",
                           (name, "TestBrand", season, min_stock, restricted), "product_id")

    def add_batch(product_id, batch_no, qty, expiry_offset):
        return conn.insert("""INSERT INTO batches (product_id, supplier_id, batch_no, quantity_received, quantity_remaining,
                              price_per_unit, purchase_date, expiry_date) VALUES (?, 1, ?, ?, ?, 100, ?, ?)""",
                           (product_id, batch_no, qty, qty, day(-60), day(expiry_offset)), "batch_id")

    neem = add_product("Neem Oil", "Year-round", 5, 0)
    mono = add_product("Monocrotophos 36% SL", "Kharif", 5, 1)
    # The LATER-expiring batch is inserted FIRST on purpose: FIFO must follow expiry date, not insertion order.
    new_batch = add_batch(neem, "B-NEW", 20, 200)
    old_batch = add_batch(neem, "B-OLD", 10, 30)
    expired_batch = add_batch(neem, "B-EXPIRED", 50, -5)
    mono_batch = add_batch(mono, "M-1", 20, 100)
    conn.commit()
    conn.close()

    return SimpleNamespace(neem=neem, mono=mono, new_batch=new_batch, old_batch=old_batch,
                           expired_batch=expired_batch, mono_batch=mono_batch,
                           owner_id=owner_id, staff_id=staff_id)


@pytest.fixture
def client(world):
    return flask_app.test_client()


def login(client, email, password):
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.get_json()
    return {"Authorization": "Bearer " + response.get_json()["token"]}


@pytest.fixture
def owner(client):
    return login(client, "owner@test.com", "Owner@123")


@pytest.fixture
def staff(client):
    return login(client, "staff@test.com", "Staff@123")


@pytest.fixture
def query(world):
    """query("SELECT ...", (params,)) -> list of dict rows, straight from the test database."""
    def run(sql, params=()):
        conn = database.connect()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()
    return run


@pytest.fixture
def add_history(world):
    """add_history(product_id, [qty_per_month, ...]) -> sales for the last N COMPLETE months (oldest first)."""
    def run(product_id, quantities, batch_id=None):
        conn = database.connect()
        batch_id = batch_id or conn.execute("SELECT batch_id FROM batches WHERE product_id = ? LIMIT 1", (product_id,)).fetchone()["batch_id"]
        first_of_this_month = stock.today().replace(day=1)
        for k, qty in enumerate(reversed(quantities), start=1):        # k = how many months ago
            month_start = first_of_this_month
            for _ in range(k):
                month_start = (month_start - timedelta(days=1)).replace(day=1)
            conn.execute("INSERT INTO sales (product_id, batch_id, quantity_sold, sale_date) VALUES (?, ?, ?, ?)",
                         (product_id, batch_id, qty, (month_start + timedelta(days=10)).strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
    return run
