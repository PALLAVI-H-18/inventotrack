-- USERS: owner and staff accounts
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'staff'))
);

-- SUPPLIERS: who batches are purchased from
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    address TEXT
);

-- PRODUCTS: the pesticide itself, not tied to any single batch
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT,
    category TEXT,
    season TEXT,                        -- Kharif / Rabi / Monsoon / Year-round
    min_stock_level INTEGER DEFAULT 10,
    is_restricted INTEGER DEFAULT 0,    -- 0 = no, 1 = yes (auto-set later)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- BATCHES: each individual stock delivery, own expiry date
CREATE TABLE IF NOT EXISTS batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    supplier_id INTEGER,
    batch_no TEXT NOT NULL,
    quantity_received INTEGER NOT NULL,
    quantity_remaining INTEGER NOT NULL,
    price_per_unit REAL NOT NULL,
    purchase_date TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products (product_id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers (supplier_id)
);

-- SALES: every transaction, deducted from a specific batch (FIFO)
CREATE TABLE IF NOT EXISTS sales (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    batch_id INTEGER NOT NULL,
    quantity_sold INTEGER NOT NULL,
    sale_date TEXT DEFAULT CURRENT_TIMESTAMP,
    sold_by INTEGER,                    -- links to users.user_id
    buyer_id_proof TEXT,                -- filled only if product is restricted
    FOREIGN KEY (product_id) REFERENCES products (product_id),
    FOREIGN KEY (batch_id) REFERENCES batches (batch_id),
    FOREIGN KEY (sold_by) REFERENCES users (user_id)
);

-- RESTRICTED_PESTICIDES: reference list checked against every product
CREATE TABLE IF NOT EXISTS restricted_pesticides (
    restricted_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pesticide_name TEXT NOT NULL,
    reason TEXT
);