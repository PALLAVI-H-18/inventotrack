"""
seed_demo.py - a sample shop: 25 restricted pesticides, 3 suppliers, 20 products, batches and
about 13 months of sales (so the forecast has something to learn from).
Used by:  python setup_database.py --demo-data     (does nothing if products already exist)
"""
import random
from datetime import timedelta

import compliance
import stock

RESTRICTED = [
    ("Monocrotophos", "Highly toxic organophosphate"), ("Paraquat Dichloride", "Fatal if swallowed"),
    ("Endosulfan", "Banned in India"), ("Phorate", "Extremely hazardous"), ("Carbofuran", "Highly toxic"),
    ("Methyl Parathion", "Banned for vegetables"), ("Chlorpyrifos", "Restricted use"),
    ("Acephate", "Restricted use"), ("Dichlorvos", "Restricted use"), ("Triazophos", "Restricted use"),
    ("Fipronil", "Restricted use"), ("Atrazine", "Restricted use"), ("Carbendazim", "Restricted use"),
    ("Captan", "Restricted use"), ("Mancozeb", "Restricted use"), ("Zineb", "Restricted use"),
    ("Diuron", "Restricted use"), ("Dimethoate", "Restricted use"), ("Fenitrothion", "Restricted use"),
    ("Phosphamidon", "Banned"), ("Methomyl", "Restricted use"), ("Thiodicarb", "Restricted use"),
    ("Aluminium Phosphide", "Fumigant, highly toxic"), ("Quinalphos", "Restricted use"),
    ("Cypermethrin 25% EC", "Restricted use"),
]
SUPPLIERS = [("Kisan Agro Traders", "9880011111", "Chikkaballapur"), ("Green Fields Distributors", "9880022222", "Bangalore"),
             ("Bharat Crop Care", "9880033333", "Kolar")]
# name, brand, category, season, min_stock, monthly base demand
PRODUCTS = [
    ("Neem Oil 1500 PPM", "AgriNeem", "Bio-pesticide", "Year-round", 15, 20),
    ("Monocrotophos 36% SL", "CropGuard", "Insecticide", "Kharif", 10, 12),
    ("Paraquat 24% SL", "GreenKill", "Herbicide", "Kharif", 10, 10),
    ("Chlorpyrifos 20% EC", "AgriCorp", "Insecticide", "Kharif", 12, 15),
    ("Imidacloprid 17.8% SL", "BayerCrop", "Insecticide", "Kharif", 12, 18),
    ("Glyphosate 41% SL", "WeedAway", "Herbicide", "Monsoon", 15, 25),
    ("Mancozeb 75% WP", "FungiStop", "Fungicide", "Rabi", 12, 14),
    ("Carbendazim 50% WP", "FungiStop", "Fungicide", "Rabi", 12, 12),
    ("Copper Oxychloride 50% WP", "CopperPro", "Fungicide", "Year-round", 10, 16),
    ("Sulphur 80% WDG", "SulfoMax", "Fungicide", "Rabi", 10, 10),
    ("Lambda Cyhalothrin 5% EC", "CropGuard", "Insecticide", "Kharif", 10, 11),
    ("Emamectin Benzoate 5% SG", "AgriCorp", "Insecticide", "Kharif", 8, 9),
    ("Thiamethoxam 25% WG", "BayerCrop", "Insecticide", "Kharif", 10, 13),
    ("Hexaconazole 5% EC", "FungiStop", "Fungicide", "Rabi", 8, 8),
    ("Pendimethalin 30% EC", "WeedAway", "Herbicide", "Monsoon", 10, 14),
    ("Atrazine 50% WP", "WeedAway", "Herbicide", "Monsoon", 8, 9),
    ("2,4-D Sodium Salt", "WeedAway", "Herbicide", "Year-round", 8, 7),
    ("Bio Fertilizer Mix", "GreenGrow", "Fertilizer", "Year-round", 20, 22),
    ("Zinc Sulphate", "GreenGrow", "Fertilizer", "Rabi", 15, 12),
    ("Trichoderma Viride", "BioShield", "Bio-pesticide", "Year-round", 10, 9),
]


def seed(db):
    if db.execute("SELECT 1 FROM products LIMIT 1").fetchone():
        print("Products already exist - demo data skipped.")
        return
    rng = random.Random(42)                       # same numbers every time
    today = stock.today()

    for name, reason in RESTRICTED:
        db.execute("INSERT INTO restricted_pesticides (pesticide_name, reason) VALUES (?, ?)", (name, reason))
    for s in SUPPLIERS:
        db.execute("INSERT INTO suppliers (name, phone, address) VALUES (?, ?, ?)", s)

    owner = db.execute("SELECT user_id FROM users WHERE role = 'owner' LIMIT 1").fetchone()
    staff = db.execute("SELECT user_id FROM users WHERE role = 'staff' LIMIT 1").fetchone()
    sellers = [r["user_id"] for r in (owner, staff) if r]

    for index, (name, brand, category, season, min_stock, base) in enumerate(PRODUCTS):
        restricted = 1 if compliance.find_restricted_match(db, name) else 0
        pid = db.insert(
            "INSERT INTO products (name, brand, category, season, min_stock_level, is_restricted) VALUES (?, ?, ?, ?, ?, ?)",
            (name, brand, category, season, min_stock, restricted), "product_id")

        # two batches: older one expires sooner (FIFO uses it first)
        batch_ids = []
        for n, (qty, expiry_days) in enumerate([(rng.randint(0, 12), 120 + index * 7), (rng.randint(5, 60), 400)], start=1):
            batch_ids.append(db.insert("""
                INSERT INTO batches (product_id, supplier_id, batch_no, quantity_received, quantity_remaining,
                                     price_per_unit, purchase_date, expiry_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (pid, 1 + index % 3, f"B{pid:02d}-{n}", qty + 20, qty, float(rng.randint(150, 900)),
                 (today - timedelta(days=60 * n)).strftime("%Y-%m-%d"),
                 (today + timedelta(days=expiry_days)).strftime("%Y-%m-%d")), "batch_id"))

        # 13 months of sales: higher in the product's own season
        months = [(today.replace(day=1) - timedelta(days=31 * k)).replace(day=1) for k in range(13, 0, -1)]
        in_season = {"Kharif": [6, 7, 8, 9, 10], "Rabi": [11, 12, 1, 2, 3], "Monsoon": [6, 7, 8, 9]}.get(season, list(range(1, 13)))
        for m in months:
            qty = max(1, int(base * (2.5 if m.month in in_season and season != "Year-round" else 1) + rng.randint(-2, 2)))
            while qty > 0:
                take = min(qty, rng.randint(1, 5))
                day = m + timedelta(days=rng.randint(0, 26))
                db.execute("INSERT INTO sales (product_id, batch_id, quantity_sold, sale_date, sold_by, buyer_id_proof) VALUES (?, ?, ?, ?, ?, ?)",
                           (pid, batch_ids[0], take, day.strftime("%Y-%m-%d"), rng.choice(sellers) if sellers else None,
                            f"AADHAAR-{rng.randint(1000, 9999)}" if restricted and rng.random() > 0.15 else None))
                qty -= take
    db.commit()
    print(f"Demo data added: {len(PRODUCTS)} products, {len(RESTRICTED)} restricted names, {len(SUPPLIERS)} suppliers.")
