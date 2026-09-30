# InventoTrack API Contract

Base URL (local): http://127.0.0.1:5000

## Auth
POST /auth/register       - create a new user
POST /auth/login          - returns JWT token

## Products
GET  /products             - list all products with stock totals
POST /products              - add a new product
GET  /products/<id>         - get one product's details

## Batches
POST /batches               - add a new stock batch
GET  /products/<id>/batches - list batches for a product

## Sales
POST /sales                 - record a sale (FIFO deduction)

## Dashboard
GET /dashboard/summary      - total value, low stock, out of stock counts
GET /dashboard/low-stock    - list of low stock products
GET /dashboard/expiring     - batches expiring within 30 days

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