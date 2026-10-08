# InventoTrack API Contract

Base URL (local): http://127.0.0.1:5000

## Auth
POST /auth/register       - create a new user
POST /auth/login          - returns JWT token

## Products

### GET /products
Lists all products. `total_quantity` counts NON-EXPIRED stock only.

Response (200):
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

status values and suggested colours:
- "healthy"       -> green  (stock above min_stock_level)
- "low_stock"     -> amber  (stock between 1 and min_stock_level)
- "out_of_stock"  -> red    (stock is 0)

## Batches
POST /batches               - add a new stock batch
GET  /products/<id>/batches - list batches for a product

## Sales
POST /sales                 - record a sale (FIFO deduction)

## Dashboard

### GET /dashboard/summary
Numbers for the dashboard cards.

Response (200):
{
    "expired_batch_count": 2,
    "expired_stock_value": 30000.0,
    "expiring_soon_count": 17,
    "healthy_count": 20,
    "low_stock_count": 0,
    "out_of_stock_count": 2,
    "total_inventory_value": 718402.44,
    "total_products": 22
}

### GET /dashboard/low-stock
Returns an array of products (same shape as GET /products) where status is "low_stock".
Empty array [] means nothing is low on stock.

### GET /dashboard/out-of-stock
Returns an array of products (same shape as GET /products) where status is "out_of_stock".

### GET /dashboard/expiring?days=30
Batches that expire within the next N days (default 30). Sorted soonest first.

Response (200):
[
  {
    "batch_id": 39,
    "batch_no": "B039",
    "quantity_remaining": 3,
    "expiry_date": "2026-10-15",
    "product_id": 20,
    "product_name": "Difenoconazole 25% EC",
    "days_left": 7
  }
]

Error (400) if days is negative:
{ "error": "days must be zero or more" }

## Compliance
GET /reports/restricted-sales - list of restricted pesticide sales

## Forecast
GET /suggestions/seasonal/<product_id> - predicted demand + restock suggestion

## Export
GET /reports/inventory/export - download Excel file

---

## Example: POST /products
Request body:
{
  "name": "Chlorpyrifos 20% EC",
  "brand": "AgriCorp",
  "category": "Insecticide",
  "season": "Kharif",
  "min_stock_level": 15
}

Response (201):
{
  "message": "Product added successfully",
  "product_id": 21
}

## Example: GET /products
Response (200):
[
  {
    "product_id": 1,
    "name": "Chlorpyrifos 20% EC",
    "brand": "AgriCorp",
    "category": "Insecticide",
    "season": "Kharif",
    "min_stock_level": 15,
    "is_restricted": 0,
    "total_quantity": 85
  }
]
