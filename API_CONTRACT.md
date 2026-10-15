# InventoTrack API Contract

Base URL (local): `http://127.0.0.1:5000`
Live URL: `https://invento-track.onrender.com` (database not set up yet, use local for now)

All requests and responses use JSON. Errors always look like:

```json
{ "error": "message to show the user" }
```

## Login rules

Every route except `GET /` and `POST /auth/login` needs a token:

```
Authorization: Bearer <token>
```

| Status | Meaning | What the frontend should do |
|---|---|---|
| 401 | Not logged in, or token expired | Send the user to the login page |
| 403 | Logged in, but not allowed (staff on an owner route) | Hide or disable that page |

Roles: **owner** can use everything. **staff** can log in, view products, view batches (without prices), see
low-stock / out-of-stock / expiring lists, and record sales.

## Status of each route

| Route | Who | Status |
|---|---|---|
| POST /auth/login | anyone | Ready |
| GET /auth/me | logged in | Ready |
| POST /auth/register | owner | Ready |
| GET /products | logged in | Ready |
| POST /products | owner | Ready |
| POST /batches | owner | Ready |
| GET /products/<id>/batches | logged in | Ready |
| POST /sales | logged in | Ready |
| GET /restricted-pesticides | logged in | Ready |
| GET /dashboard/summary | owner | Ready |
| GET /dashboard/low-stock, /out-of-stock, /expiring | logged in | Ready |
| GET /reports/restricted-sales | owner | Ready (Oct 11) |
| GET /forecast/history/<id> | owner | Ready (Oct 12) |
| GET /forecast/<id>, GET /forecast | owner | Ready (Oct 13) |
| GET /suggestions/seasonal/<id> | owner | Coming (Oct 14) |
| GET /reports/inventory/export | owner | Coming (Oct 15) |

---

## Auth

### POST /auth/login
Request: `{ "email": "owner@inventotrack.com", "password": "Owner@123" }`

Response (200):
```json
{
  "token": "eyJhbGciOi...",
  "user": { "user_id": 1, "name": "Shop Owner", "email": "owner@inventotrack.com", "role": "owner" }
}
```
Errors: 400 missing fields, 401 `Invalid email or password`.

### GET /auth/me
Response (200): `{ "user_id": 1, "name": "Shop Owner", "role": "owner" }`

### POST /auth/register (owner only)
Request: `{ "name": "New Staff", "email": "new@shop.com", "password": "secret1", "role": "staff" }`
Response (201): `{ "message": "User created", "user_id": 3, "role": "staff" }`
Errors: 400 invalid input, 403 not owner, 409 email already used.

---

## Products

### GET /products
`total_quantity` counts NON-EXPIRED stock only.

```json
[
  {
    "product_id": 1, "name": "Chlorpyrifos 20% EC", "brand": "AgriCorp", "category": "Insecticide",
    "season": "Kharif", "min_stock_level": 15, "is_restricted": 0,
    "total_quantity": 66, "status": "healthy"
  }
]
```

| status | Meaning | Colour |
|---|---|---|
| healthy | stock above min_stock_level | green |
| low_stock | stock between 1 and min_stock_level | amber |
| out_of_stock | stock is 0 | red |

### POST /products (owner only)
Request: `{ "name": "Monocrotophos 36% SL", "brand": "X", "category": "Insecticide", "season": "Kharif", "min_stock_level": 10 }`

Response (201), restricted product:
```json
{
  "message": "Product added successfully", "product_id": 23, "is_restricted": true,
  "restricted_match": "Monocrotophos", "restricted_reason": "Banned for use on vegetables - CIBRC",
  "warning": "Restricted pesticide: buyer identification is required at sale."
}
```
For a normal product only `message`, `product_id` and `is_restricted: false` are returned.

### GET /restricted-pesticides
`[ { "restricted_id": 1, "pesticide_name": "Monocrotophos", "reason": "Banned ..." } ]`

---

## Batches

### POST /batches (owner only)
Request:
```json
{ "product_id": 1, "supplier_id": 1, "batch_no": "B041", "quantity_received": 60,
  "price_per_unit": 420, "purchase_date": "2026-09-25", "expiry_date": "2027-06-30" }
```
Response (201): `{ "message": "Batch added successfully", "batch_id": 41 }`
Errors: 400 missing fields, 404 product not found.

### GET /products/<id>/batches
Soonest expiry first. **Staff do not receive `price_per_unit`.**
```json
{ "product_name": "Chlorpyrifos 20% EC",
  "batches": [ { "batch_id": 41, "batch_no": "B041", "quantity_received": 60, "quantity_remaining": 45,
                 "price_per_unit": 420.0, "purchase_date": "2026-09-25", "expiry_date": "2027-06-30", "supplier_id": 1 } ] }
```

---

## Sales

### POST /sales
Stock is taken oldest-expiry-first (FIFO). Expired batches are never used. `sold_by` is taken from the login token.

Request: `{ "product_id": 1, "quantity_sold": 8 }`

For a RESTRICTED product, `buyer_id_proof` is mandatory (at least 4 characters, spaces are ignored):
`{ "product_id": 7, "quantity_sold": 2, "buyer_id_proof": "Aadhaar: XXXX-XXXX-1234" }`

Response (201):
```json
{ "message": "Sale recorded successfully", "product_name": "Chlorpyrifos 20% EC", "total_quantity_sold": 8,
  "batches_used": [ { "batch_id": 41, "quantity_taken": 8, "remaining_in_batch": 37 } ] }
```
Errors (400): missing/invalid fields, `Not enough stock. Only N units available (non-expired).`,
`This product is restricted. Buyer identification is required to complete this sale.`,
`Buyer ID is too short. Enter at least 4 characters.` Also 404 product not found.

---

## Dashboard

### GET /dashboard/summary (owner only)
```json
{ "total_products": 22, "healthy_count": 20, "low_stock_count": 0, "out_of_stock_count": 2,
  "expiring_soon_count": 17, "expired_batch_count": 2,
  "total_inventory_value": 718402.44, "expired_stock_value": 30000.0 }
```

### GET /dashboard/low-stock and GET /dashboard/out-of-stock
Arrays of products (same shape as GET /products). `[]` means none.

### GET /dashboard/expiring?days=30
```json
[ { "batch_id": 27, "batch_no": "B027", "product_id": 14, "product_name": "Metribuzin 70% WP",
    "quantity_remaining": 5, "expiry_date": "2026-10-15", "days_left": 7 } ]
```
Error (400) if days is negative.

---

## Compliance log (Oct 11) - owner only

### GET /reports/restricted-sales
Every sale of a restricted pesticide, newest first. One row per batch used, so a sale that took stock from
two batches appears as two rows with the same buyer ID.

Optional filters: `?from=2026-10-01&to=2026-10-31` and `?missing_only=true` (only rows with NO buyer ID).

Response (200):
```json
{
  "summary": { "total_records": 13, "total_units": 402, "with_buyer_id": 1, "missing_buyer_id": 12 },
  "records": [
    { "sale_id": 245, "sale_date": "2026-10-12", "product_id": 7, "product_name": "Paraquat 24% SL",
      "batch_no": "B013", "quantity_sold": 2, "buyer_id_proof": "Aadhaar 1234",
      "has_buyer_id": true, "sold_by_name": "Shop Staff" }
  ]
}
```
`with_buyer_id + missing_buyer_id = total_records`. Show rows with `has_buyer_id: false` in red.
Errors: 400 bad date (`'from' must be a date like 2026-10-31`), 403 staff.

---

## Forecast (Oct 12-13) - owner only

### GET /forecast/history/<product_id>
Units sold per month. The unfinished current month is left out and empty months are filled with 0.
```json
{ "product_id": 1, "product_name": "Chlorpyrifos 20% EC", "season": "Kharif",
  "months": [ { "month": "2025-11", "quantity": 14 }, { "month": "2025-12", "quantity": 11 } ] }
```

### GET /forecast/<product_id>
Predicts NEXT month's demand with three methods and tests each on the last 4 months.
```json
{
  "product_id": 1, "product_name": "Chlorpyrifos 20% EC", "season": "Kharif",
  "months_available": 11, "enough_data": true, "backtest_months": 4,
  "history": [ { "month": "2025-11", "quantity": 14 } ],
  "methods": [
    { "method": "season_regression", "label": "Season-aware regression", "mae": 7.22, "prediction": 12 },
    { "method": "linear_trend", "label": "Linear trend (regression)", "mae": 13.79, "prediction": 43 },
    { "method": "moving_average", "label": "3-month moving average", "mae": 16.33, "prediction": 38 }
  ],
  "lowest_error_method": "season_regression",
  "best_method": "season_regression", "best_method_label": "Season-aware regression",
  "forecast_month": "2026-11", "in_season_next_month": false,
  "predicted_demand": 12,
  "explanation": "Kharif is a seasonal product, so the season-aware model is used ..."
}
```
`mae` = average mistake in units over the test months (smaller is better).
When there is not enough history (fewer than 8 complete months):
```json
{ "product_id": 21, "product_name": "Neem Oil 1500 ppm", "season": "Year-round", "months_available": 0,
  "history": [], "enough_data": false,
  "message": "Not enough sales history yet: 0 complete month(s) found, at least 8 are needed." }
```
Errors: 404 product not found, 403 staff.

### GET /forecast
One short row per product: `product_id, product_name, season, enough_data` and, when `enough_data` is true,
`forecast_month, predicted_demand, best_method, best_method_label`; otherwise `message`.

---

## Restock suggestions (owner only)  - Oct 14

Rule: `target_stock = predicted_demand + min_stock_level`, `recommended_order = max(0, target_stock - current_stock)`.
`current_stock` counts only batches that have not expired. With fewer than 8 complete months of sales there is no
forecast, so the simple rule `target_stock = 2 x min_stock_level` is used (`basis` = `minimum_stock_rule`).

### GET /suggestions/seasonal/<product_id>
```json
{
  "product_id": 2, "product_name": "Carbendazim 50% WP", "season": "Rabi", "is_restricted": false,
  "current_stock": 37, "expiring_within_30_days": 0, "min_stock_level": 12,
  "basis": "forecast", "method": "Season-aware regression",
  "forecast_month": "2026-11", "in_season_next_month": true, "predicted_demand": 29,
  "target_stock": 41, "recommended_order": 4, "priority": "order_soon",
  "why": "Based on 14 months of sales, about 29 units are expected to sell in 2026-11 (Season-aware regression). Rabi season is active next month, so demand is expected to be higher. Adding the safety stock of 12 gives a target of 41. Current usable stock is 37, so order 4 more."
}
```
`priority`: `order_now` (stock is at/below the minimum or below expected demand), `order_soon` (an order is needed but stock is still above both), `ok` (no order needed).
When `basis` is `minimum_stock_rule`: `method`, `forecast_month`, `in_season_next_month` and `predicted_demand` are `null`.
Errors: 404 product not found, 401 no token, 403 staff.

### GET /suggestions
Optional `?only_needed=true` (only products with `recommended_order > 0`). Most urgent first.
```json
{ "summary": { "total_products": 20, "order_now": 0, "order_soon": 5, "ok": 15, "total_units_to_order": 24 },
  "suggestions": [ { "...": "same fields as above" } ] }
```

---

## Excel exports (owner only)  - Oct 15

All three return a real `.xlsx` file (`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`,
`Content-Disposition: attachment; filename=inventory_2026-10-14.xlsx`). The frontend must send the token, so download with
`fetch` + `blob`, not a plain link.

| Route | Sheets | Optional query |
|---|---|---|
| `GET /reports/inventory/export` | Summary, Products, Batches (expired = red, expiring in 30 days = amber) | - |
| `GET /reports/sales/export` | Summary, Sales | `from`, `to` (YYYY-MM-DD) |
| `GET /reports/compliance/export` | Summary, Restricted sales (missing buyer ID = red) | `from`, `to`, `missing_only=true` |

Errors are JSON (see below), for example 400 for a bad date and 403 for staff.

---

## Restock alerts (Oct 15) - owner sends, staff receive

| Route | Who | What it does |
|---|---|---|
| `POST /notifications` `{product_id, message?}` | owner | Sends an alert to staff. The text is built automatically ("X is OUT OF STOCK..." or "X is running low (3 left)...") plus the optional note. 409 if an alert for that product is already open. |
| `GET /notifications?status=open\|done\|all` | any login | Alerts with the product's CURRENT stock (`current_stock`, `stock_status`). Open ones come first. |
| `POST /notifications/<id>/done` | any login | Marks the alert done ("brought to the shop"). 409 if already done. |

Also new: `GET /products` rows have `total_sold` and `sold_today`; `POST /sales` returns `remaining_stock` and `stock_status`; `POST /batches` returns `total_stock`.
New table `notifications` (created by `python setup_database.py`).

---

## One error format everywhere  - Oct 16

Every error, from every route, has this shape:
```json
{ "error": "Validation failed", "details": { "quantity_received": "quantity_received must be a whole number" } }
```
`error` is always a readable string. `details` appears only when specific fields are wrong (field name -> problem).

| Status | Meaning |
|---|---|
| 400 | Bad input (wrong type, missing field, bad date, rule broken, not enough stock, missing buyer ID) |
| 401 | Not logged in, bad token, or token expired |
| 403 | Logged in, but owner access is required |
| 404 | Product / route not found |
| 405 | Wrong HTTP method for the route |
| 409 | Duplicate (product name, batch number for a product, user email) |
| 413 | Request body larger than 1 MB |
| 500 | Unexpected server problem (details are only in the server log, never in the response) |

## Health check
`GET /health` (no login) -> `{ "status": "ok", "database": "postgresql" }`. Returns 503 if the database cannot be reached.
