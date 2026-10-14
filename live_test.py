"""
live_test.py - checks EVERY route of a running InventoTrack server.   (Oct 20)

    python live_test.py http://127.0.0.1:5000
    python live_test.py https://invento-track.onrender.com

Needs only Python (no extra libraries). Uses the demo owner/staff logins unless you set
OWNER_EMAIL / OWNER_PASSWORD / STAFF_EMAIL / STAFF_PASSWORD.
It creates ONE test product (name starts with "LIVETEST") with its own batch, so your real stock is untouched.
Exit code 0 = everything passed.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000").rstrip("/")
OWNER = (os.environ.get("OWNER_EMAIL", "owner@inventotrack.com"), os.environ.get("OWNER_PASSWORD", "Owner@123"))
STAFF = (os.environ.get("STAFF_EMAIL", "staff@inventotrack.com"), os.environ.get("STAFF_PASSWORD", "Staff@123"))
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

results = []


def call(method, path, token=None, body=None, raw_body=None):
    """Returns (status, parsed_json_or_None, headers, raw_bytes)."""
    data = raw_body if raw_body is not None else (json.dumps(body).encode() if body is not None else None)
    request = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            status, headers, payload = response.status, response.headers, response.read()
    except urllib.error.HTTPError as e:
        status, headers, payload = e.code, e.headers, e.read()
    try:
        parsed = json.loads(payload)
    except ValueError:
        parsed = None
    return status, parsed, headers, payload


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   <- {detail}" if not ok else ""))


def expect(name, method, path, status, token=None, body=None, raw_body=None, test=None):
    code, js, headers, payload = call(method, path, token, body, raw_body)
    ok = code == status
    detail = f"expected {status}, got {code}: {str(js or payload[:100])[:150]}"
    if ok and test is not None:
        try:
            ok = bool(test(js, headers, payload))
            detail = f"unexpected body: {str(js or payload[:100])[:200]}"
        except Exception as e:                       # a missing key counts as a failed check
            ok, detail = False, f"check crashed: {e!r} on {str(js)[:150]}"
    check(f"{method:6} {path}  ->  {status}  {name}", ok, detail)
    return js


def is_error(js):
    return isinstance(js, dict) and isinstance(js.get("error"), str) and set(js) <= {"error", "details"}


def main():
    print(f"\nTesting {BASE}\n(first request can take ~50 s if the free server was asleep)\n")
    started = time.time()
    code, js, _, _ = call("GET", "/health")
    while code != 200 and time.time() - started < 120:       # wait for Render to wake up
        time.sleep(5)
        code, js, _, _ = call("GET", "/health")

    print("PUBLIC")
    expect("home", "GET", "/", 200, test=lambda j, h, p: "running" in j["message"])
    expect("health + database", "GET", "/health", 200, test=lambda j, h, p: j["status"] == "ok")
    print(f"        database in use: {js.get('database') if js else '?'}")

    print("\nAUTH")
    owner_login = expect("owner login", "POST", "/auth/login", 200, body={"email": OWNER[0], "password": OWNER[1]},
                         test=lambda j, h, p: j["user"]["role"] == "owner")
    staff_login = expect("staff login", "POST", "/auth/login", 200, body={"email": STAFF[0], "password": STAFF[1]},
                         test=lambda j, h, p: j["user"]["role"] == "staff")
    if not owner_login or not staff_login:
        print("\nCannot continue without both logins.")
        return 1
    owner, staff = owner_login["token"], staff_login["token"]
    expect("wrong password", "POST", "/auth/login", 401, body={"email": OWNER[0], "password": "wrong"}, test=lambda j, h, p: is_error(j))
    expect("empty login body", "POST", "/auth/login", 400, body={}, test=lambda j, h, p: is_error(j) and "email" in j["details"])
    expect("who am I (owner)", "GET", "/auth/me", 200, owner, test=lambda j, h, p: j["role"] == "owner")
    expect("no token", "GET", "/auth/me", 401, test=lambda j, h, p: is_error(j))
    expect("bad token", "GET", "/auth/me", 401, "garbage", test=lambda j, h, p: is_error(j))
    expect("staff cannot register users", "POST", "/auth/register", 403, staff, body={}, test=lambda j, h, p: is_error(j))
    expect("register validation", "POST", "/auth/register", 400, owner, body={"name": "x"}, test=lambda j, h, p: is_error(j))

    print("\nPRODUCTS, BATCHES, RESTRICTED LIST")
    expect("list products (owner)", "GET", "/products", 200, owner, test=lambda j, h, p: isinstance(j, list) and len(j) > 0 and "status" in j[0])
    expect("list products (staff)", "GET", "/products", 200, staff)
    expect("restricted list", "GET", "/restricted-pesticides", 200, owner, test=lambda j, h, p: len(j) > 0)
    stamp = str(int(time.time()))
    created = expect("add normal product", "POST", "/products", 201, owner,
                     body={"name": f"LIVETEST Neem {stamp}", "season": "Year-round", "min_stock_level": 5},
                     test=lambda j, h, p: j["is_restricted"] is False)
    expect("duplicate product", "POST", "/products", 409, owner, body={"name": f"livetest neem {stamp}"}, test=lambda j, h, p: is_error(j))
    expect("staff cannot add product", "POST", "/products", 403, staff, body={"name": "x"}, test=lambda j, h, p: is_error(j))
    expect("bad season", "POST", "/products", 400, owner, body={"name": "x", "season": "Winter"}, test=lambda j, h, p: is_error(j))
    restricted = expect("add restricted product", "POST", "/products", 201, owner,
                        body={"name": f"Monocrotophos LIVETEST {stamp}", "season": "Kharif", "min_stock_level": 5},
                        test=lambda j, h, p: j["is_restricted"] is True and "warning" in j)
    if not created or not restricted:
        return 1
    pid, rid = created["product_id"], restricted["product_id"]

    today = date.today()
    batch = {"product_id": pid, "batch_no": f"LT-{stamp}", "quantity_received": 10, "price_per_unit": 100,
             "purchase_date": (today - timedelta(days=1)).isoformat(), "expiry_date": (today + timedelta(days=200)).isoformat()}
    expect("add batch", "POST", "/batches", 201, owner, body=batch, test=lambda j, h, p: "batch_id" in j)
    expect("duplicate batch no", "POST", "/batches", 409, owner, body=batch, test=lambda j, h, p: is_error(j))
    expect("expiry before purchase", "POST", "/batches", 400, owner, body={**batch, "batch_no": "X1", "expiry_date": (today - timedelta(days=9)).isoformat()}, test=lambda j, h, p: is_error(j))
    expect("staff cannot add batch", "POST", "/batches", 403, staff, body=batch, test=lambda j, h, p: is_error(j))
    expect("batches (owner sees price)", "GET", f"/products/{pid}/batches", 200, owner, test=lambda j, h, p: "price_per_unit" in j["batches"][0])
    expect("batches (staff has no price)", "GET", f"/products/{pid}/batches", 200, staff, test=lambda j, h, p: "price_per_unit" not in j["batches"][0])
    expect("batches of unknown product", "GET", "/products/999999/batches", 404, owner, test=lambda j, h, p: is_error(j))
    expect("add batch for restricted product", "POST", "/batches", 201, owner, body={**batch, "product_id": rid, "batch_no": f"LT-R-{stamp}"})

    print("\nSALES (FIFO + compliance)")
    expect("sale ok", "POST", "/sales", 201, staff, body={"product_id": pid, "quantity_sold": 4},
           test=lambda j, h, p: j["total_quantity_sold"] == 4 and j["batches_used"][0]["remaining_in_batch"] == 6)
    expect("not enough stock", "POST", "/sales", 400, staff, body={"product_id": pid, "quantity_sold": 500}, test=lambda j, h, p: is_error(j) and "Not enough stock" in j["error"])
    expect("zero quantity", "POST", "/sales", 400, staff, body={"product_id": pid, "quantity_sold": 0}, test=lambda j, h, p: is_error(j))
    expect("text quantity", "POST", "/sales", 400, staff, body={"product_id": pid, "quantity_sold": "two"}, test=lambda j, h, p: is_error(j))
    expect("unknown product", "POST", "/sales", 404, staff, body={"product_id": 999999, "quantity_sold": 1}, test=lambda j, h, p: is_error(j))
    expect("not JSON", "POST", "/sales", 400, staff, raw_body=b"hello", test=lambda j, h, p: is_error(j))
    expect("restricted, no buyer ID", "POST", "/sales", 400, staff, body={"product_id": rid, "quantity_sold": 1}, test=lambda j, h, p: is_error(j))
    expect("restricted, spaces as ID", "POST", "/sales", 400, staff, body={"product_id": rid, "quantity_sold": 1, "buyer_id_proof": "    "}, test=lambda j, h, p: is_error(j))
    expect("restricted, short ID", "POST", "/sales", 400, staff, body={"product_id": rid, "quantity_sold": 1, "buyer_id_proof": "AB"}, test=lambda j, h, p: is_error(j))
    expect("restricted with valid ID", "POST", "/sales", 201, staff, body={"product_id": rid, "quantity_sold": 2, "buyer_id_proof": "AADHAAR-LIVE-1"})
    expect("sale without token", "POST", "/sales", 401, body={"product_id": pid, "quantity_sold": 1}, test=lambda j, h, p: is_error(j))

    print("\nDASHBOARD")
    expect("summary (owner)", "GET", "/dashboard/summary", 200, owner, test=lambda j, h, p: j["total_products"] > 0 and "total_inventory_value" in j)
    expect("summary (staff blocked)", "GET", "/dashboard/summary", 403, staff, test=lambda j, h, p: is_error(j))
    expect("low stock", "GET", "/dashboard/low-stock", 200, staff, test=lambda j, h, p: isinstance(j, list))
    expect("out of stock", "GET", "/dashboard/out-of-stock", 200, staff, test=lambda j, h, p: isinstance(j, list))
    expect("expiring (default)", "GET", "/dashboard/expiring", 200, staff, test=lambda j, h, p: isinstance(j, list))
    expect("expiring ?days=90", "GET", "/dashboard/expiring?days=90", 200, staff)
    expect("expiring ?days=abc", "GET", "/dashboard/expiring?days=abc", 400, staff, test=lambda j, h, p: is_error(j))

    print("\nCOMPLIANCE LOG")
    expect("log (owner)", "GET", "/reports/restricted-sales", 200, owner, test=lambda j, h, p: j["summary"]["total_records"] >= 1)
    expect("log missing_only", "GET", "/reports/restricted-sales?missing_only=true", 200, owner, test=lambda j, h, p: "records" in j)
    expect("log date range", "GET", "/reports/restricted-sales?from=2020-01-01&to=2099-12-31", 200, owner)
    expect("log backwards range", "GET", "/reports/restricted-sales?from=2026-10-31&to=2026-10-01", 400, owner, test=lambda j, h, p: is_error(j))
    expect("log (staff blocked)", "GET", "/reports/restricted-sales", 403, staff, test=lambda j, h, p: is_error(j))

    print("\nFORECAST")
    expect("forecast history", "GET", "/forecast/history/1", 200, owner, test=lambda j, h, p: "months" in j)
    expect("forecast one", "GET", "/forecast/1", 200, owner, test=lambda j, h, p: "enough_data" in j)
    expect("forecast one (new product, little data)", "GET", f"/forecast/{pid}", 200, owner, test=lambda j, h, p: j["enough_data"] is False)
    expect("forecast unknown product", "GET", "/forecast/999999", 404, owner, test=lambda j, h, p: is_error(j))
    expect("forecast all", "GET", "/forecast", 200, owner, test=lambda j, h, p: isinstance(j, list) and len(j) > 0)
    expect("forecast (staff blocked)", "GET", "/forecast", 403, staff, test=lambda j, h, p: is_error(j))

    print("\nRESTOCK SUGGESTIONS")
    expect("suggestion for product 1", "GET", "/suggestions/seasonal/1", 200, owner,
           test=lambda j, h, p: j["basis"] in ("forecast", "minimum_stock_rule") and len(j["why"]) > 20 and j["recommended_order"] >= 0)
    expect("suggestion, new product uses simple rule", "GET", f"/suggestions/seasonal/{pid}", 200, owner,
           test=lambda j, h, p: j["basis"] == "minimum_stock_rule" and j["target_stock"] == 10)
    expect("all suggestions", "GET", "/suggestions", 200, owner, test=lambda j, h, p: "summary" in j and isinstance(j["suggestions"], list))
    expect("only_needed", "GET", "/suggestions?only_needed=true", 200, owner, test=lambda j, h, p: all(s["recommended_order"] > 0 for s in j["suggestions"]))
    expect("suggestion unknown product", "GET", "/suggestions/seasonal/999999", 404, owner, test=lambda j, h, p: is_error(j))
    expect("suggestions (staff blocked)", "GET", "/suggestions", 403, staff, test=lambda j, h, p: is_error(j))

    print("\nEXCEL EXPORTS")
    for path in ["/reports/inventory/export", "/reports/sales/export", "/reports/compliance/export"]:
        expect("download", "GET", path, 200, owner,
               test=lambda j, h, p: h.get_content_type() == XLSX and p[:2] == b"PK" and "attachment" in h.get("Content-Disposition", ""))
        expect("staff blocked", "GET", path, 403, staff, test=lambda j, h, p: is_error(j))
    expect("export with bad date", "GET", "/reports/sales/export?from=nonsense", 400, owner, test=lambda j, h, p: is_error(j))

    print("\nERROR FORMAT")
    expect("unknown route", "GET", "/no-such-route", 404, owner, test=lambda j, h, p: is_error(j))
    expect("wrong method", "DELETE", "/products", 405, owner, test=lambda j, h, p: is_error(j))

    passed = sum(results)
    print(f"\n{'=' * 50}\n{passed} of {len(results)} checks passed" + ("   -> ALL GOOD" if passed == len(results) else "   -> FIX THE FAILURES ABOVE"))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
