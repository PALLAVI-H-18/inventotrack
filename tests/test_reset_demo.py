"""test_reset_demo.py - the one-command demo reset must always give the same healthy shop."""
import sys

import db as database
import reset_demo


def run_reset(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["reset_demo.py", "--yes"])
    reset_demo.main()


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]


def test_reset_builds_demo_shop_and_keeps_users(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "demo.db"))
    run_reset(monkeypatch)
    conn = database.connect()
    users_before = count(conn, "users")
    assert users_before >= 1
    assert count(conn, "products") == 21
    assert count(conn, "restricted_pesticides") == 25
    conn.execute("INSERT INTO suppliers (name) VALUES (?)", ("Junk",))
    conn.commit()
    conn.close()

    run_reset(monkeypatch)                      # run again: must be identical, not doubled
    conn = database.connect()
    assert count(conn, "products") == 21
    assert count(conn, "suppliers") == 3
    assert count(conn, "users") == users_before
    missing = conn.execute("SELECT COUNT(*) AS n FROM sales s JOIN products p ON p.product_id=s.product_id "
                           "WHERE p.is_restricted=1 AND (s.buyer_id_proof IS NULL OR s.buyer_id_proof='')").fetchone()["n"]
    assert missing == 2
