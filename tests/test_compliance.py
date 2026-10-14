"""Compliance: restricted pesticides need a real buyer ID, and every such sale is logged."""
from conftest import day


def sell(client, headers, product_id, qty, buyer=None):
    body = {"product_id": product_id, "quantity_sold": qty}
    if buyer is not None:
        body["buyer_id_proof"] = buyer
    return client.post("/sales", json=body, headers=headers)


def test_restricted_sale_without_buyer_id_is_blocked(client, staff, world, query):
    response = sell(client, staff, world.mono, 1)
    assert response.status_code == 400
    assert "buyer_id_proof" in response.get_json()["details"]
    assert "required" in response.get_json()["error"]
    assert query("SELECT COUNT(*) AS c FROM sales")[0]["c"] == 0       # nothing was saved


def test_spaces_only_buyer_id_counts_as_empty(client, staff, world):
    assert sell(client, staff, world.mono, 1, "     ").status_code == 400


def test_buyer_id_shorter_than_4_characters_is_blocked(client, staff, world):
    response = sell(client, staff, world.mono, 1, "AB1")
    assert response.status_code == 400
    assert "too short" in response.get_json()["error"]


def test_restricted_sale_with_valid_buyer_id_works_and_is_logged(client, staff, owner, world):
    assert sell(client, staff, world.mono, 2, "AADHAAR-1234").status_code == 201
    report = client.get("/reports/restricted-sales", headers=owner).get_json()
    assert report["summary"]["total_records"] == 1
    assert report["summary"]["with_buyer_id"] == 1
    record = report["records"][0]
    assert record["product_name"] == "Monocrotophos 36% SL"
    assert record["buyer_id_proof"] == "AADHAAR-1234"
    assert record["sold_by_name"] == "Test Staff"


def test_normal_product_needs_no_buyer_id(client, staff, world, owner):
    assert sell(client, staff, world.neem, 1).status_code == 201
    assert client.get("/reports/restricted-sales", headers=owner).get_json()["summary"]["total_records"] == 0


def test_new_product_is_flagged_restricted_automatically(client, owner):
    response = client.post("/products", json={"name": "Monocrotophos 20% EC", "season": "Kharif"}, headers=owner)
    assert response.status_code == 201
    body = response.get_json()
    assert body["is_restricted"] is True
    assert body["restricted_match"] == "Monocrotophos"
    assert "warning" in body


def test_normal_new_product_is_not_flagged(client, owner):
    body = client.post("/products", json={"name": "Neem Oil Plus"}, headers=owner).get_json()
    assert body["is_restricted"] is False


def test_missing_only_filter_finds_old_sales_without_id(client, owner, world, query):
    # simulate an old record made before the rule existed
    from db import connect
    conn = connect()
    conn.execute("INSERT INTO sales (product_id, batch_id, quantity_sold, sale_date, sold_by) VALUES (?, ?, 1, ?, ?)",
                 (world.mono, world.mono_batch, day(-3), world.staff_id))
    conn.commit()
    conn.close()
    report = client.get("/reports/restricted-sales?missing_only=true", headers=owner).get_json()
    assert report["summary"]["total_records"] == 1
    assert report["summary"]["missing_buyer_id"] == 1


def test_date_range_filter(client, staff, owner, world):
    sell(client, staff, world.mono, 1, "AADHAAR-1234")
    far_future = client.get("/reports/restricted-sales?from=2999-01-01", headers=owner).get_json()
    assert far_future["summary"]["total_records"] == 0
    backwards = client.get("/reports/restricted-sales?from=2026-10-31&to=2026-10-01", headers=owner)
    assert backwards.status_code == 400
