"""Validation: bad input gives a clean 4xx and ALWAYS the same JSON shape. Nothing ever leaks a stack trace."""
from conftest import day


def assert_clean_error(response, status):
    assert response.status_code == status, response.get_json()
    body = response.get_json()
    assert set(body) <= {"error", "details"}
    assert isinstance(body["error"], str) and body["error"]
    if "details" in body:
        assert isinstance(body["details"], dict)
    return body


def good_batch(world, **changes):
    body = {"product_id": world.neem, "batch_no": "B-TEST", "quantity_received": 10, "price_per_unit": 50,
            "purchase_date": day(-1), "expiry_date": day(300), "supplier_id": 1}
    body.update(changes)
    return body


def test_valid_batch_is_created(client, owner, world):
    response = client.post("/batches", json=good_batch(world), headers=owner)
    assert response.status_code == 201 and "batch_id" in response.get_json()


def test_missing_fields_are_all_reported_together(client, owner):
    body = assert_clean_error(client.post("/batches", json={}, headers=owner), 400)
    assert {"product_id", "batch_no", "quantity_received", "price_per_unit", "purchase_date", "expiry_date"} <= set(body["details"])


def test_wrong_types_are_rejected(client, owner, world):
    for field, value in [("quantity_received", "ten"), ("quantity_received", True), ("quantity_received", 2.5),
                         ("price_per_unit", "free"), ("price_per_unit", 0), ("batch_no", 123)]:
        assert_clean_error(client.post("/batches", json=good_batch(world, **{field: value}), headers=owner), 400)


def test_date_rules(client, owner, world):
    assert_clean_error(client.post("/batches", json=good_batch(world, expiry_date="31-12-2027"), headers=owner), 400)
    assert_clean_error(client.post("/batches", json=good_batch(world, expiry_date="2027-02-30"), headers=owner), 400)
    body = assert_clean_error(client.post("/batches", json=good_batch(world, expiry_date=day(-10)), headers=owner), 400)
    assert "expiry_date" in body["details"]                                       # before purchase date
    body = assert_clean_error(client.post("/batches", json=good_batch(world, purchase_date=day(5)), headers=owner), 400)
    assert "purchase_date" in body["details"]                                     # in the future


def test_unknown_product_and_supplier(client, owner, world):
    assert_clean_error(client.post("/batches", json=good_batch(world, product_id=9999), headers=owner), 404)
    assert_clean_error(client.post("/batches", json=good_batch(world, supplier_id=9999), headers=owner), 400)


def test_duplicates_are_409(client, owner, world):
    client.post("/batches", json=good_batch(world), headers=owner)
    assert_clean_error(client.post("/batches", json=good_batch(world), headers=owner), 409)
    assert_clean_error(client.post("/products", json={"name": "neem oil"}, headers=owner), 409)   # name check ignores case


def test_product_validation(client, owner):
    assert_clean_error(client.post("/products", json={"name": "   "}, headers=owner), 400)
    assert_clean_error(client.post("/products", json={"name": "X", "season": "Winter"}, headers=owner), 400)
    assert_clean_error(client.post("/products", json={"name": "X", "min_stock_level": -1}, headers=owner), 400)


def test_body_must_be_json(client, owner):
    assert_clean_error(client.post("/sales", data="this is not json", headers=owner), 400)
    assert_clean_error(client.post("/sales", json=[1, 2, 3], headers=owner), 400)


def test_login_validation(client):
    body = assert_clean_error(client.post("/auth/login", json={}), 400)
    assert set(body["details"]) == {"email", "password"}


def test_bad_query_parameters(client, owner):
    assert_clean_error(client.get("/dashboard/expiring?days=abc", headers=owner), 400)
    assert_clean_error(client.get("/dashboard/expiring?days=-1", headers=owner), 400)
    assert_clean_error(client.get("/reports/restricted-sales?from=yesterday", headers=owner), 400)


def test_unknown_route_and_wrong_method(client):
    assert assert_clean_error(client.get("/does-not-exist"), 404)["error"] == "Route not found"
    assert_clean_error(client.delete("/products"), 405)


def test_oversized_request_is_413(client, owner):
    assert_clean_error(client.post("/sales", data="x" * (2 * 1024 * 1024), headers=owner,
                                   content_type="application/json"), 413)


def test_server_errors_never_leak_details(client, owner, monkeypatch):
    import stock

    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(stock, "get_products_with_stock", boom)
    from app import app
    app.config["PROPAGATE_EXCEPTIONS"] = False
    body = assert_clean_error(client.get("/products", headers=owner), 500)
    assert "secret" not in body["error"]
