"""Owner -> staff restock alerts, plus the stock/sold numbers the QR screens show."""


def sell(client, headers, product_id, qty, **extra):
    return client.post("/sales", json={"product_id": product_id, "quantity_sold": qty, **extra}, headers=headers)


def test_sale_returns_remaining_stock_and_status(client, staff, world):
    # Neem Oil: 30 usable units (20 + 10; the expired 50 do not count), min stock 5
    r = sell(client, staff, world.neem, 10)
    assert r.status_code == 201
    assert r.get_json()["remaining_stock"] == 20 and r.get_json()["stock_status"] == "healthy"
    r = sell(client, staff, world.neem, 16)
    assert r.get_json()["remaining_stock"] == 4 and r.get_json()["stock_status"] == "low_stock"
    r = sell(client, staff, world.neem, 4)
    assert r.get_json()["remaining_stock"] == 0 and r.get_json()["stock_status"] == "out_of_stock"


def test_products_show_sold_numbers(client, staff, world):
    sell(client, staff, world.neem, 7)
    neem = next(p for p in client.get("/products", headers=staff).get_json() if p["product_id"] == world.neem)
    assert neem["total_sold"] == 7 and neem["sold_today"] == 7 and neem["total_quantity"] == 23


def test_add_batch_returns_new_total_stock(client, owner, world):
    from conftest import day
    body = {"product_id": world.neem, "batch_no": "NEW-9", "quantity_received": 15, "price_per_unit": 50,
            "purchase_date": day(0), "expiry_date": day(300)}
    r = client.post("/batches", json=body, headers=owner)
    assert r.status_code == 201 and r.get_json()["total_stock"] == 45


def test_owner_sends_alert_and_staff_sees_it(client, owner, staff, world):
    sell(client, staff, world.neem, 30)                                   # now out of stock
    r = client.post("/notifications", json={"product_id": world.neem, "message": "Order from Krishi"}, headers=owner)
    assert r.status_code == 201 and "OUT OF STOCK" in r.get_json()["text"] and "Krishi" in r.get_json()["text"]

    seen = client.get("/notifications?status=open", headers=staff).get_json()
    assert len(seen) == 1
    assert seen[0]["product_name"] == "Neem Oil" and seen[0]["current_stock"] == 0
    assert seen[0]["stock_status"] == "out_of_stock" and seen[0]["created_by_name"] == "Test Owner"


def test_low_stock_message_and_duplicate_is_409(client, owner, staff, world):
    sell(client, staff, world.neem, 27)                                   # 3 left, min 5 -> low
    r = client.post("/notifications", json={"product_id": world.neem}, headers=owner)
    assert "running low (3 left)" in r.get_json()["text"]
    assert client.post("/notifications", json={"product_id": world.neem}, headers=owner).status_code == 409


def test_staff_cannot_send_alert(client, staff, world):
    assert client.post("/notifications", json={"product_id": world.neem}, headers=staff).status_code == 403


def test_unknown_product_and_bad_body(client, owner):
    assert client.post("/notifications", json={"product_id": 9999}, headers=owner).status_code == 404
    assert client.post("/notifications", json={}, headers=owner).status_code == 400


def test_staff_marks_done_once(client, owner, staff, world):
    nid = client.post("/notifications", json={"product_id": world.mono}, headers=owner).get_json()["notification_id"]
    assert client.post(f"/notifications/{nid}/done", headers=staff).status_code == 200
    assert client.post(f"/notifications/{nid}/done", headers=staff).status_code == 409
    assert client.post("/notifications/9999/done", headers=staff).status_code == 404
    assert client.get("/notifications?status=open", headers=staff).get_json() == []
    done = client.get("/notifications?status=done", headers=staff).get_json()
    assert len(done) == 1 and done[0]["done_by_name"] == "Test Staff"
    # after it is done, the owner can alert again later
    assert client.post("/notifications", json={"product_id": world.mono}, headers=owner).status_code == 201


def test_bad_status_filter(client, staff):
    assert client.get("/notifications?status=bogus", headers=staff).status_code == 400


def test_remove_one_done_alert(client, owner, staff, world):
    nid = client.post("/notifications", json={"product_id": world.neem}, headers=owner).get_json()["notification_id"]
    assert client.delete(f"/notifications/{nid}", headers=staff).status_code == 409      # still open: cannot be removed
    client.post(f"/notifications/{nid}/done", headers=staff)
    assert client.delete(f"/notifications/{nid}", headers=owner).status_code == 200
    assert client.delete(f"/notifications/{nid}", headers=owner).status_code == 404
    assert client.get("/notifications", headers=staff).get_json() == []


def test_clear_all_done_keeps_open_ones(client, owner, staff, world):
    a = client.post("/notifications", json={"product_id": world.neem}, headers=owner).get_json()["notification_id"]
    client.post("/notifications", json={"product_id": world.mono}, headers=owner)
    client.post(f"/notifications/{a}/done", headers=staff)
    r = client.delete("/notifications/done", headers=staff)
    assert r.status_code == 200 and r.get_json()["removed"] == 1
    left = client.get("/notifications", headers=staff).get_json()
    assert len(left) == 1 and left[0]["status"] == "open"
