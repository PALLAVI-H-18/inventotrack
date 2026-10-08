# InventoTrack API Contract

Base URL (local): `http://127.0.0.1:5000`
Live URL: `https://invento-track.onrender.com` (database not set up yet, use local for now)

All requests and responses use JSON. Errors always look like:

```json
{ "error": "message to show the user" }
```

## Status of each route

| Route | Status |
|---|---|
| GET / | Ready |
| GET /products | Ready |
| POST /products | Ready |
| POST /batches | Ready |
| GET /products/<id>/batches | Ready |
| POST /sales | Ready |
| GET /dashboard/summary | Ready |
| GET /dashboard/low-stock | Ready |
| GET /dashboard/out-of-stock | Ready |
| GET /dashboard/expiring | Ready |
| POST /auth/register, POST /auth/login | Coming soon |
| GET /reports/restricted-sales | Coming soon |
| GET /suggestions/seasonal/<product_id> | Coming soon |
| GET /reports/inventory/export | Coming soon |

---

## Products

### GET /products
Lists all products. `total_quantity` counts NON-EXPIRED stock only.

Response (200):
```json
[
  {
    "product_id": 1,
    "name": "Chlorpyrifos 20% EC",
    "brand": "AgriCorp",
    "category": "Insecticide",
    "season": "Kharif",
    "min_stock_level": 15,
    "is_restricted": 0,
    "total_quantity": 66,
    "status": "healthy"
  }
]
```

`status` values and suggested colours:

| status | Meaning | Colour |
|---|---|---|
| healthy | stock above min_stock_level | green |
| low_stock | stock between 1 and min_stock_level | amber |
| out_of_stock | stock is 0 | red |

### POST /products
Adds a product. If the name matches the restricted list, it is flagged automatically.

Request:
```json
{
  "name": "Neem Oil 1500 ppm",
  "brand": "AgriCorp",
  "category": "Bio-pesticide",
  "season": "Year-round",
  "min_stock_level": 10
}
```

Response (201):
```json
{
  "message": "Product added successfully",
  "product_id": 21,
  "is_restricted": false
}
```

Error (400) if name is missing: `{ "error": "Product name is required" }`

---

## Batches

### POST /batches
Adds a stock batch to a product. Every batch has its own expiry date.

Request:
```json
{
  "product_id": 1,
  "supplier_id": 1,
  "batch_no": "B041",
  "quantity_received": 60,
  "price_per_unit": 420,
  "purchase_date": "2026-09-25",
  "expiry_date": "2027-06-30"
}
```

Required: product_id, batch_no, quantity_received, price_per_unit, purchase_date, expiry_date.
Optional: supplier_id.

Response (201):
```json
{ "message": "Batch added successfully", "batch_id": 41 }
```

Errors:
- 400 `{ "error": "Missing required fields: expiry_date" }`
- 404 `{ "error": "Product not found" }`

### GET /products/<id>/batches
Lists all batches of one product, soonest expiry first.

Response (200):
```json
{
  "product_name": "Chlorpyrifos 20% EC",
  "batches": [
    {
      "batch_id": 41,
      "batch_no": "B041",
      "quantity_received": 60,
      "quantity_remaining": 45,
      "price_per_unit": 420.0,
      "purchase_date": "2026-09-25",
      "expiry_date": "2027-06-30",
      "supplier_id": 1
    }
  ]
}
```

Error (404) if the product does not exist.

---

## Sales

### POST /sales
Records a sale. Stock is deducted oldest-expiry-first (FIFO). Expired batches are never used.

Request:
```json
{
  "product_id": 1,
  "quantity_sold": 8
}
```

For a RESTRICTED product (`is_restricted` = 1), `buyer_id_proof` is mandatory:
```json
{
  "product_id": 22,
  "quantity_sold": 2,
  "buyer_id_proof": "Aadhaar: XXXX-XXXX-1234"
}
```

Optional: `sold_by` (user id, used after login is added).

Response (201):
```json
{
  "message": "Sale recorded successfully",
  "product_name": "Chlorpyrifos 20% EC",
  "total_quantity_sold": 8,
  "batches_used": [
    { "batch_id": 41, "quantity_taken": 8, "remaining_in_batch": 37 }
  ]
}
```

Errors (400 unless noted):
- `{ "error": "product_id and a positive quantity_sold are required" }`
- `{ "error": "This product is restricted. Buyer identification is required to complete this sale." }`
- `{ "error": "Not enough stock. Only 22 units available (non-expired)." }`
- 404 `{ "error": "Product not found" }`

Frontend note: for restricted products, show a required "Buyer ID" field in the sale form and display the error message if the API rejects the sale.

---

## Dashboard

### GET /dashboard/summary
Numbers for the dashboard cards.

Response (200):
```json
{
  "total_products": 22,
  "healthy_count": 20,
  "low_stock_count": 0,
  "out_of_stock_count": 2,
  "expiring_soon_count": 17,
  "expired_batch_count": 2,
  "total_inventory_value": 718402.44,
  "expired_stock_value": 30000.0
}
```

| Field | Meaning |
|---|---|
| total_products | number of products |
| healthy_count, low_stock_count, out_of_stock_count | products by status (these three add up to total_products) |
| expiring_soon_count | batches with stock that expire within 30 days |
| expired_batch_count | expired batches that still hold stock |
| total_inventory_value | rupee value of stock that can be sold |
| expired_stock_value | rupee value stuck in expired batches |

### GET /dashboard/low-stock
Array of products (same shape as GET /products) whose status is `low_stock`.
An empty array `[]` means nothing is low on stock.

### GET /dashboard/out-of-stock
Array of products (same shape as GET /products) whose status is `out_of_stock`.

### GET /dashboard/expiring?days=30
Batches that expire within the next N days (default 30), soonest first.

Response (200):
```json
[
  {
    "batch_id": 27,
    "batch_no": "B027",
    "product_id": 14,
    "product_name": "Metribuzin 70% WP",
    "quantity_remaining": 5,
    "expiry_date": "2026-10-15",
    "days_left": 7
  }
]
```

Error (400) if days is negative: `{ "error": "days must be zero or more" }`

---

## Coming soon

### Auth (JWT)
- `POST /auth/register` creates a user (role: owner or staff)
- `POST /auth/login` returns a token

After login, send this header on protected requests:
```
Authorization: Bearer <token>
```

### Compliance, forecast and export
- `GET /reports/restricted-sales` list of restricted sales with buyer proof
- `GET /suggestions/seasonal/<product_id>` predicted demand and restock suggestion
- `GET /reports/inventory/export` downloads an Excel file

Exact request and response shapes will be added here when each route is built.
