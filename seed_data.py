import sqlite3
import random
from datetime import datetime, timedelta

conn = sqlite3.connect("inventotrack.db")
cur = conn.cursor()

# ---------------------------------------------------------
# 1. PRODUCTS (20) — each tagged with a season
# ---------------------------------------------------------
products = [
    ("Chlorpyrifos 20% EC", "AgriCorp", "Insecticide", "Kharif", 15),
    ("Cypermethrin 10% EC", "CropSafe", "Insecticide", "Kharif", 15),
    ("Imidacloprid 17.8% SL", "GreenGuard", "Insecticide", "Kharif", 10),
    ("Mancozeb 75% WP", "AgriCorp", "Fungicide", "Monsoon", 20),
    ("Carbendazim 50% WP", "CropSafe", "Fungicide", "Monsoon", 15),
    ("Glyphosate 41% SL", "WeedOut", "Herbicide", "Year-round", 25),
    ("Paraquat 24% SL", "WeedOut", "Herbicide", "Year-round", 10),
    ("2,4-D Amine Salt 58% SL", "AgriCorp", "Herbicide", "Rabi", 15),
    ("Thiamethoxam 25% WG", "GreenGuard", "Insecticide", "Kharif", 10),
    ("Propiconazole 25% EC", "CropSafe", "Fungicide", "Rabi", 12),
    ("Malathion 50% EC", "AgriCorp", "Insecticide", "Year-round", 15),
    ("Hexaconazole 5% SC", "GreenGuard", "Fungicide", "Rabi", 10),
    ("Acephate 75% SP", "CropSafe", "Insecticide", "Kharif", 12),
    ("Metribuzin 70% WP", "WeedOut", "Herbicide", "Rabi", 10),
    ("Copper Oxychloride 50% WP", "AgriCorp", "Fungicide", "Monsoon", 15),
    ("Fipronil 5% SC", "GreenGuard", "Insecticide", "Kharif", 10),
    ("Pendimethalin 30% EC", "WeedOut", "Herbicide", "Kharif", 12),
    ("Sulphur 80% WDG", "CropSafe", "Fungicide", "Rabi", 15),
    ("Emamectin Benzoate 5% SG", "GreenGuard", "Insecticide", "Kharif", 8),
    ("Difenoconazole 25% EC", "AgriCorp", "Fungicide", "Monsoon", 10),
]

cur.executemany("""
    INSERT INTO products (name, brand, category, season, min_stock_level)
    VALUES (?, ?, ?, ?, ?)
""", products)
conn.commit()
print(f"Inserted {len(products)} products")

# ---------------------------------------------------------
# 2. RESTRICTED PESTICIDES (25) — reference list
# Based on India's actual banned/restricted insecticide list
# ---------------------------------------------------------
restricted = [
    ("Monocrotophos", "Banned for use on vegetables - CIBRC"),
    ("Phorate", "Restricted - highly toxic"),
    ("Methyl Parathion", "Banned - extremely hazardous"),
    ("Endosulfan", "Banned by Supreme Court order"),
    ("Dichlorvos", "Restricted - under phase-out review"),
    ("Aldrin", "Banned - persistent organic pollutant"),
    ("Dieldrin", "Banned - persistent organic pollutant"),
    ("Chlordane", "Banned - persistent organic pollutant"),
    ("Heptachlor", "Banned - persistent organic pollutant"),
    ("DDT", "Banned for agricultural use"),
    ("Lindane", "Banned - CIBRC"),
    ("Captafol", "Banned - carcinogenic risk"),
    ("Methomyl", "Restricted - highly toxic"),
    ("Phosphamidon", "Banned - CIBRC"),
    ("Paraquat Dichloride", "Restricted - requires licensed sale"),
    ("Carbofuran", "Restricted - highly toxic to birds"),
    ("Triazophos", "Restricted - under review"),
    ("Fenthion", "Restricted - toxic to birds"),
    ("Methamidophos", "Banned - CIBRC"),
    ("Nicotine Sulfate", "Banned - agricultural use"),
    ("Sodium Cyanide", "Banned - extremely hazardous"),
    ("Calcium Cyanide", "Banned - extremely hazardous"),
    ("Ethyl Mercury Chloride", "Banned - mercury compound"),
    ("Toxaphene", "Banned - persistent organic pollutant"),
    ("Chlorobenzilate", "Banned - CIBRC"),
]

cur.executemany("""
    INSERT INTO restricted_pesticides (pesticide_name, reason)
    VALUES (?, ?)
""", restricted)
conn.commit()
print(f"Inserted {len(restricted)} restricted pesticides")

# ---------------------------------------------------------
# 3. SUPPLIERS (needed before batches, since batches reference them)
# ---------------------------------------------------------
suppliers = [
    ("AgroDistributors Pvt Ltd", "9880011223", "Bengaluru"),
    ("Krishi Suppliers", "9845566778", "Mysuru"),
    ("Farm Input Traders", "9900112233", "Hassan"),
]
cur.executemany("""
    INSERT INTO suppliers (name, phone, address)
    VALUES (?, ?, ?)
""", suppliers)
conn.commit()
print(f"Inserted {len(suppliers)} suppliers")

# ---------------------------------------------------------
# 4. BATCHES (40) — 2 batches per product, realistic expiry spread
# ---------------------------------------------------------
cur.execute("SELECT product_id, min_stock_level FROM products")
all_products = cur.fetchall()

today = datetime.today()
batches = []
batch_counter = 1

for product_id, min_stock in all_products:
    for i in range(2):  # 2 batches per product = 40 total
        qty_received = random.randint(40, 120)

        # Make some batches realistically low/near-empty, some expiring soon
        if i == 0:
            qty_remaining = random.randint(1, min_stock)       # low stock batch
            expiry = today + timedelta(days=random.randint(15, 25))  # expiring soon
        else:
            qty_remaining = random.randint(min_stock, qty_received)  # healthy batch
            expiry = today + timedelta(days=random.randint(200, 500))  # safe expiry

        purchase_date = today - timedelta(days=random.randint(30, 200))
        price = round(random.uniform(150, 900), 2)
        supplier_id = random.randint(1, 3)

        batches.append((
            product_id, supplier_id, f"B{batch_counter:03d}",
            qty_received, qty_remaining, price,
            purchase_date.strftime("%Y-%m-%d"),
            expiry.strftime("%Y-%m-%d")
        ))
        batch_counter += 1

cur.executemany("""
    INSERT INTO batches (product_id, supplier_id, batch_no, quantity_received,
                          quantity_remaining, price_per_unit, purchase_date, expiry_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", batches)
conn.commit()
print(f"Inserted {len(batches)} batches")

# ---------------------------------------------------------
# 5. SALES — 12 months of seasonal sales history per product
# This is what your forecasting model will train on later
# ---------------------------------------------------------
cur.execute("SELECT product_id, season FROM products")
product_seasons = cur.fetchall()

cur.execute("SELECT batch_id, product_id FROM batches")
product_batches = {}
for batch_id, product_id in cur.fetchall():
    product_batches.setdefault(product_id, []).append(batch_id)

season_months = {
    "Kharif": [6, 7, 8, 9, 10],
    "Rabi": [11, 12, 1, 2, 3],
    "Monsoon": [6, 7, 8, 9],
    "Year-round": list(range(1, 13)),
}

sales = []
for product_id, season in product_seasons:
    active_months = season_months.get(season, list(range(1, 13)))
    batch_ids = product_batches.get(product_id, [])
    if not batch_ids:
        continue

    for month_offset in range(12):  # last 12 months
        sale_date = today - timedelta(days=30 * month_offset)
        month = sale_date.month

        if month in active_months:
            qty = random.randint(25, 45)   # high season sales
        else:
            qty = random.randint(5, 15)    # off season sales

        batch_id = random.choice(batch_ids)
        sales.append((
            product_id, batch_id, qty,
            sale_date.strftime("%Y-%m-%d"), 1, None
        ))

cur.executemany("""
    INSERT INTO sales (product_id, batch_id, quantity_sold, sale_date, sold_by, buyer_id_proof)
    VALUES (?, ?, ?, ?, ?, ?)
""", sales)
conn.commit()
print(f"Inserted {len(sales)} sales records")

conn.close()
print("\nSeed data loaded successfully!")