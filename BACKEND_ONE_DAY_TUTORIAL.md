# InventoTrack backend: one-day working session

This combines the October 14–20 backend tasks into one practical sequence. The
existing Flask API, SQLite schema, forecasting module, users, FIFO sales,
compliance report, and Postman collection stay in place. Work from the repository
root and take a backup before changing real inventory data.

## What you will finish

- Explainable seasonal restock suggestions.
- Three valid Excel downloads: inventory, sales, and restricted-sales compliance.
- JSON request validation and one `{"error": "..."}` response shape.
- Focused tests for FIFO, compliance, roles, insufficient stock, validation,
  suggestions, and Excel files.
- A production SQLite file selected by an environment variable.
- A deployment checklist and route-by-route live retest.

The local code and tests can be completed without cloud credentials. The final
Render deployment/live verification requires access to the Render service and a
persistent disk; this guide does not claim to have changed or verified the live
service.

## 1. Prerequisites and install (30 minutes)

You need Windows 10/11, Python 3.12 (recommended), Git, PowerShell, and a web
browser. Python 3.12 is recommended for broad package compatibility. This project
already lists Flask, pytest, and openpyxl in `requirements.txt`.

Open PowerShell and go to the project:

```powershell
cd "C:\Users\PALLAVI H\OneDrive\Desktop\Invento-track"
```

Use the project's existing environment if it is working:

```powershell
.\venv\Scripts\Activate.ps1
python --version
python -m pip --version
```

For a clean setup with Python 3.12, instead create a new environment (do not
delete the existing `venv`):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run this for the current terminal only, then
activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 2. Check the existing database before touching it (15 minutes)

The tracked `schema.sql` describes the existing SQLite tables; the actual
`inventotrack.db` is local and ignored by Git. Keep that local database. Back it
up before testing changes against it:

```powershell
Copy-Item .\inventotrack.db .\inventotrack.backup.db
```

The API and setup scripts now read the database filename from `DATABASE_PATH`.
Without it, they use `inventotrack.db` beside the code. For this PowerShell
session, point it at the existing database:

```powershell
$env:DATABASE_PATH = (Join-Path $PWD "inventotrack.db")
$env:JWT_SECRET_KEY = "local-development-secret-change-me"
```

`python database.py` applies the existing `CREATE TABLE IF NOT EXISTS` schema;
it does not delete data. Do not rerun `seed_data.py` or `create_demo_users.py`
against an already populated database: the demo rows are intended only for a
new development database.

For a completely fresh local demo database, choose a new filename first:

```powershell
$env:DATABASE_PATH = (Join-Path $PWD "inventotrack-tutorial.db")
python database.py
python seed_data.py
python create_demo_users.py
```

Demo logins created by that last command are `owner@inventotrack.com` /
`Owner@123` and `staff@inventotrack.com` / `Staff@123`. They are for local
practice only; never use them in production.

## 3. Start the API and understand the existing flow (15 minutes)

Run the local Flask server in the first PowerShell window:

```powershell
python app.py
```

In a second window, check the health route:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/
```

Expected response:

```json
{"message":"InventoTrack backend is running"}
```

Most routes require a token. Login, then keep the returned token in a variable:

```powershell
$login = Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:5000/auth/login `
  -ContentType "application/json" `
  -Body '{"email":"owner@inventotrack.com","password":"Owner@123"}'
$ownerHeaders = @{ Authorization = "Bearer $($login.token)" }
```

Check that it works:

```powershell
Invoke-RestMethod -Headers $ownerHeaders http://127.0.0.1:5000/auth/me
```

The existing request/response contract and Postman examples are in
`API_CONTRACT.md` and `postman/collections/InventoTrack`. The important flow is:
products describe items; batches add expiring stock; sales consume eligible
batches earliest-expiry-first; restricted sales also write buyer-ID compliance
records; forecasts use completed months of sales history.

## 4. Add explainable restock recommendations (45 minutes)

Try one product (replace `1` with an existing product ID):

```powershell
Invoke-RestMethod -Headers $ownerHeaders `
  http://127.0.0.1:5000/suggestions/seasonal/1
```

The response includes the suggested units and fields such as:

```json
{
  "product_id": 1,
  "product_name": "Chlorpyrifos 20% EC",
  "season": "Kharif",
  "forecast_month": "2026-11",
  "in_season": false,
  "enough_data": true,
  "best_method": "season_regression",
  "predicted_demand": 12,
  "current_stock": 7,
  "minimum_stock": 15,
  "target_stock": 15,
  "recommended_restock_quantity": 8,
  "why": "Basis: ... Season: Kharif is out of season ... Current usable stock is 7 units ..."
}
```

The actual product name, date, and numbers depend on your database. The
recommendation targets the greater of forecast demand and minimum stock, then
subtracts non-expired stock. When there are fewer than eight complete sales
months, it explains that limitation and falls back to the configured minimum
stock level. View every product with:

```powershell
Invoke-RestMethod -Headers $ownerHeaders `
  http://127.0.0.1:5000/suggestions/seasonal
```

This depends on the existing forecasting module: sales history informs demand,
the season tells whether the target month is in-season, and current stock
determines how much to order.

## 5. Download and inspect the Excel workbooks (30 minutes)

The owner-only routes return real `.xlsx` files, not CSV files or JSON:

```powershell
Invoke-WebRequest -Headers $ownerHeaders `
  -Uri http://127.0.0.1:5000/reports/inventory/export `
  -OutFile .\inventory.xlsx
Invoke-WebRequest -Headers $ownerHeaders `
  -Uri http://127.0.0.1:5000/reports/sales/export `
  -OutFile .\sales.xlsx
Invoke-WebRequest -Headers $ownerHeaders `
  -Uri http://127.0.0.1:5000/reports/compliance/export `
  -OutFile .\compliance-log.xlsx
```

Open each file in Excel or LibreOffice. Each has a named worksheet and column
headers, including when its report currently has no records. Compliance export
accepts the report's filters, for example:

```powershell
Invoke-WebRequest -Headers $ownerHeaders `
  -Uri "http://127.0.0.1:5000/reports/compliance/export?from=2026-10-01&to=2026-10-31" `
  -OutFile .\compliance-october.xlsx
```

## 6. Validate inputs and read errors consistently (30 minutes)

Requests that change data must have a JSON object. For example, a sale quantity
must be a positive integer, batch dates must be real `YYYY-MM-DD` dates, and a
product's minimum stock must be a non-negative integer. A bad request returns
HTTP 400 and a simple body:

```powershell
try {
  Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/sales `
    -Headers $ownerHeaders -ContentType "application/json" `
    -Body '{"product_id":1,"quantity_sold":"many"}'
} catch {
  $_.ErrorDetails.Message
}
```

Example error body:

```json
{"error":"product_id and a positive integer quantity_sold are required"}
```

The same single-key error shape is used for validation, missing resources,
authentication/authorization, and framework 404/405 responses. A server-side
failure is logged and returned as a generic 500 error; do not send internal
exception details to API users.

## 7. Run the feature-freeze tests (30 minutes)

Stop the development server with Ctrl+C, then run:

```powershell
python -m pytest -q
```

Expected result from this repository's tests:

```text
12 passed
```

The tests build a temporary database for each case, so they do not change your
existing `inventotrack.db`. They verify FIFO consumption, that failed sales do
not change stock, restricted-buyer-ID compliance, owner/staff authorization,
explainable restock fallback, valid XLSX downloads, and consistent validation
errors. If a test fails, fix the code before deployment; do not loosen a test
just to make it green.

Feature-freeze checklist:

- All tests pass.
- `GET /` and login work.
- Staff cannot access owner-only routes or download reports.
- A rejected sale has no partial stock deduction.
- Each downloaded workbook opens and has the expected worksheet.
- Local database backup exists and no real data was seeded over.
- `git status --short` shows only files you meant to change.

## 8. Configure a persistent Render deployment (60 minutes plus provider setup)

This app currently uses SQLite. `DATABASE_PATH` selects the database file but
does not convert SQLite into PostgreSQL. To use SQLite on Render, attach a
persistent disk to the existing web service and mount it at `/var/data`. Without
that persistent disk, a redeploy can erase the production database. A managed
PostgreSQL service requires a separate database-driver and query-layer migration;
it is not a safe one-day environment-variable change.

In the Render dashboard, select the existing `invento-track` web service and set:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app` (also in the existing `Procfile`)
- Persistent disk mount path: `/var/data`
- Environment variable `DATABASE_PATH`: `/var/data/inventotrack.db`
- Environment variable `JWT_SECRET_KEY`: a fresh random secret, never the
  development fallback and never committed to Git

Generate a strong secret locally and paste it directly into Render's secret
environment variable field:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

After Render has attached the disk and deployed the code, open its Shell and run
these commands once to create the schema and a production owner. The owner script
prompts for the name, email, and password (the password prompt does not echo
characters); the password must be at least 12 characters. You can alternatively
set `OWNER_NAME`, `OWNER_EMAIL`, and `OWNER_PASSWORD` in that Shell session:

```text
python database.py
python create_owner.py
```

Do not run `create_demo_users.py` in production. For real stock history, import
or enter verified records through a reviewed migration/API workflow; do not
overwrite the local SQLite file or assume an empty production file contains the
local data.

The checked-in Render address is
`https://invento-track.onrender.com`. Confirm in the Render dashboard that the
service is deployed from the branch containing these changes and that the
environment variables and persistent disk are attached before using it.

## 9. Retest every route against the live URL (45 minutes)

Only do write requests on a test/staging service or with approved test records:
registering accounts, adding products/batches, and recording sales changes the
database. Store the live URL and owner token in the current PowerShell session:

```powershell
$base = "https://invento-track.onrender.com"
$liveLogin = Invoke-RestMethod -Method Post -Uri "$base/auth/login" `
  -ContentType "application/json" `
  -Body '{"email":"YOUR_PRODUCTION_OWNER_EMAIL","password":"YOUR_PRODUCTION_PASSWORD"}'
$liveHeaders = @{ Authorization = "Bearer $($liveLogin.token)" }
```

Never paste a production password or token into source code, a commit, or a
public issue. In Postman, set the collection's base URL to `$base`, perform the
owner login first, and run the existing `postman/collections/InventoTrack`
requests. Test each route below, using existing read-only records first and
staging records for mutations:

| Route | Live check |
| --- | --- |
| `GET /` | No token; expect 200 JSON health message |
| `POST /auth/login` | Valid owner and staff; invalid credentials return 401 |
| `GET /auth/me` | Owner and staff tokens return their own role |
| `POST /auth/register` | Owner creates a test staff account; staff gets 403 |
| `GET /products` | Owner and staff can list; unauthenticated gets 401 |
| `POST /products` | Owner can add in staging; invalid body returns JSON error |
| `GET /restricted-pesticides` | Authenticated list |
| `POST /batches` | Owner adds a test batch in staging; invalid product returns 404 |
| `GET /products/<id>/batches` | Owner sees prices; staff does not |
| `POST /sales` | Staff can sell in staging; test FIFO, compliance, and insufficient stock |
| `GET /dashboard/summary` | Owner succeeds; staff gets 403 |
| `GET /dashboard/low-stock` | Authenticated route |
| `GET /dashboard/out-of-stock` | Authenticated route |
| `GET /dashboard/expiring?days=30` | Authenticated route; bad `days` returns JSON 400 |
| `GET /reports/restricted-sales` | Owner succeeds; test date filters and invalid date |
| `GET /forecast/history/<id>` | Owner succeeds; unknown product returns 404 |
| `GET /forecast/<id>` | Owner succeeds; check `enough_data` behavior |
| `GET /forecast` | Owner gets forecast list |
| `GET /suggestions/seasonal/<id>` | Check `why`, season, stock, and quantity |
| `GET /suggestions/seasonal` | One recommendation for each product |
| `GET /reports/inventory/export` | Owner download opens as `.xlsx`; staff gets 403 |
| `GET /reports/sales/export` | Owner download opens as `.xlsx`; staff gets 403 |
| `GET /reports/compliance/export` | Owner download opens as `.xlsx`; verify filters and staff gets 403 |

For each check, record the URL, status code, and result in the existing project
test notes/Postman run. A successful local test is not evidence that the Render
deployment or its database works. If the production owner, disk, or deployed
service is not available, stop here and finish the live checks after the service
owner provisions access; do not claim the API is live-verified.

## Common fixes

- **`ModuleNotFoundError`**: activate the intended virtual environment, then run
  `python -m pip install -r requirements.txt`.
- **`no such table`**: check `$env:DATABASE_PATH` points to the intended file and
  run `python database.py`. Do not point the app at an empty second file by
  accident.
- **Login returns 401**: use the owner credentials for the same database file
  being served. Demo users only exist if `create_demo_users.py` was run there.
- **403 on exports/suggestions**: log in with the owner account; staff tokens
  are intentionally denied.
- **404 product**: replace the example ID with one returned by `GET /products`.
- **XLSX download is JSON**: check the HTTP status and authentication error before
  trying to open the response as a workbook.
- **Render loses data after deploy**: verify a persistent disk is mounted at
  `/var/data` and `DATABASE_PATH` points inside it; do not continue writing
  production records until persistence is confirmed.
- **Render cannot write the database**: check that the disk is attached and the
  mount path is writable by the service.
