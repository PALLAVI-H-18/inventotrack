"""Roles: no token -> 401 (who are you?), staff on an owner route -> 403 (you may not)."""

OWNER_ONLY = [
    ("GET", "/dashboard/summary"), ("GET", "/reports/restricted-sales"), ("GET", "/forecast"),
    ("GET", "/forecast/1"), ("GET", "/forecast/history/1"), ("GET", "/suggestions"),
    ("GET", "/suggestions/seasonal/1"), ("GET", "/reports/inventory/export"),
    ("GET", "/reports/sales/export"), ("GET", "/reports/compliance/export"),
    ("POST", "/products"), ("POST", "/batches"), ("POST", "/auth/register"),
]
ANY_LOGIN = [
    ("GET", "/products"), ("GET", "/restricted-pesticides"), ("GET", "/dashboard/low-stock"),
    ("GET", "/dashboard/out-of-stock"), ("GET", "/dashboard/expiring"), ("GET", "/products/1/batches"),
    ("GET", "/auth/me"),
]


def call(client, method, path, headers=None):
    return client.open(path, method=method, headers=headers or {}, json={} if method == "POST" else None)


def test_every_protected_route_rejects_missing_token(client):
    for method, path in OWNER_ONLY + ANY_LOGIN + [("POST", "/sales")]:
        response = call(client, method, path)
        assert response.status_code == 401, (method, path, response.status_code)
        assert response.get_json() == {"error": "Login required. Please log in first."}


def test_garbage_token_is_rejected(client):
    response = client.get("/products", headers={"Authorization": "Bearer not.a.real.token"})
    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid login token. Please log in again."}


def test_staff_is_blocked_from_every_owner_route(client, staff):
    for method, path in OWNER_ONLY:
        response = call(client, method, path, staff)
        assert response.status_code == 403, (method, path, response.status_code)
        assert response.get_json() == {"error": "Owner access required"}


def test_owner_can_use_owner_routes(client, owner):
    for path in ["/dashboard/summary", "/reports/restricted-sales", "/forecast", "/suggestions"]:
        assert client.get(path, headers=owner).status_code == 200, path


def test_staff_can_use_shared_routes(client, staff):
    for method, path in ANY_LOGIN:
        assert call(client, method, path, staff).status_code == 200, (method, path)


def test_staff_does_not_see_purchase_price(client, staff, owner, world):
    staff_view = client.get(f"/products/{world.neem}/batches", headers=staff).get_json()
    owner_view = client.get(f"/products/{world.neem}/batches", headers=owner).get_json()
    assert all("price_per_unit" not in b for b in staff_view["batches"])
    assert all("price_per_unit" in b for b in owner_view["batches"])


def test_login_gives_role_and_wrong_password_is_401(client):
    ok = client.post("/auth/login", json={"email": "OWNER@test.com", "password": "Owner@123"})
    assert ok.status_code == 200 and ok.get_json()["user"]["role"] == "owner"       # email is case-insensitive
    wrong = client.post("/auth/login", json={"email": "owner@test.com", "password": "nope"})
    unknown = client.post("/auth/login", json={"email": "nobody@test.com", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json() == unknown.get_json()          # same message: attackers cannot tell which part was wrong


def test_owner_can_register_staff_and_duplicate_is_409(client, owner):
    body = {"name": "New Staff", "email": "new@test.com", "password": "secret1", "role": "staff"}
    assert client.post("/auth/register", json=body, headers=owner).status_code == 201
    assert client.post("/auth/register", json=body, headers=owner).status_code == 409
