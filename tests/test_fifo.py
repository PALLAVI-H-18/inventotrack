"""FIFO: the batch that expires first is sold first. Expired batches are never sold."""


def sell(client, headers, product_id, qty, buyer=None):
    body = {"product_id": product_id, "quantity_sold": qty}
    if buyer:
        body["buyer_id_proof"] = buyer
    return client.post("/sales", json=body, headers=headers)


def remaining(query, batch_id):
    return query("SELECT quantity_remaining AS q FROM batches WHERE batch_id = ?", (batch_id,))[0]["q"]


def test_sale_takes_from_batch_that_expires_first(client, staff, world, query):
    response = sell(client, staff, world.neem, 4)
    assert response.status_code == 201
    used = response.get_json()["batches_used"]
    assert [b["batch_id"] for b in used] == [world.old_batch]          # B-OLD, not B-NEW
    assert remaining(query, world.old_batch) == 6
    assert remaining(query, world.new_batch) == 20                     # untouched


def test_sale_spanning_two_batches(client, staff, world, query):
    response = sell(client, staff, world.neem, 15)                     # B-OLD has 10, so 5 come from B-NEW
    assert response.status_code == 201
    used = response.get_json()["batches_used"]
    assert [(b["batch_id"], b["quantity_taken"]) for b in used] == [(world.old_batch, 10), (world.new_batch, 5)]
    assert remaining(query, world.old_batch) == 0
    assert remaining(query, world.new_batch) == 15
    rows = query("SELECT batch_id, quantity_sold FROM sales WHERE product_id = ? ORDER BY sale_id", (world.neem,))
    assert [(r["batch_id"], r["quantity_sold"]) for r in rows] == [(world.old_batch, 10), (world.new_batch, 5)]


def test_expired_batch_is_never_sold(client, staff, world, query):
    assert sell(client, staff, world.neem, 30).status_code == 201      # exactly the 30 usable units
    assert remaining(query, world.expired_batch) == 50                 # expired stock untouched


def test_sold_by_is_the_logged_in_user(client, staff, world, query):
    sell(client, staff, world.neem, 1)
    assert query("SELECT sold_by FROM sales")[0]["sold_by"] == world.staff_id


def test_insufficient_stock_is_rejected(client, staff, world):
    response = sell(client, staff, world.neem, 31)                     # only 30 usable (the 50 expired do not count)
    assert response.status_code == 400
    body = response.get_json()
    assert "Not enough stock" in body["error"]
    assert "30" in body["error"]
    assert body["details"]["quantity_sold"] == "only 30 available"


def test_insufficient_stock_changes_nothing(client, staff, world, query):
    sell(client, staff, world.neem, 31)
    assert remaining(query, world.old_batch) == 10
    assert remaining(query, world.new_batch) == 20
    assert query("SELECT COUNT(*) AS c FROM sales")[0]["c"] == 0


def test_cannot_sell_zero_or_negative(client, staff, world):
    assert sell(client, staff, world.neem, 0).status_code == 400
    assert sell(client, staff, world.neem, -3).status_code == 400


def test_unknown_product_is_404(client, staff):
    response = sell(client, staff, 9999, 1)
    assert response.status_code == 404
    assert response.get_json() == {"error": "Product not found"}
