-- Signal23 Parser Database Schema
-- База данных: db_signal23

-- 1. Outlets (торговые точки)
CREATE TABLE IF NOT EXISTS outlets (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) NOT NULL UNIQUE,
    city VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. Staging (сырые данные)
CREATE TABLE IF NOT EXISTS staging (
    id SERIAL PRIMARY KEY,
    outlet_code VARCHAR(50) NOT NULL,
    name TEXT NOT NULL,
    article VARCHAR(100),
    barcode VARCHAR(50),
    brand_raw TEXT,
    model_raw TEXT,
    part_type_raw TEXT,
    category_raw TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    url TEXT,
    loaded_at TIMESTAMP DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_staging_outlet ON staging(outlet_code);
CREATE INDEX IF NOT EXISTS idx_staging_article ON staging(article);

-- 3. Nomenclature (уникальные товары)
CREATE TABLE IF NOT EXISTS nomenclature (
    id SERIAL PRIMARY KEY,
    article VARCHAR(100) NOT NULL UNIQUE,
    barcode VARCHAR(50),
    name TEXT NOT NULL,
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    first_seen_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_nom_brand ON nomenclature(brand);
CREATE INDEX IF NOT EXISTS idx_nom_model ON nomenclature(model);
CREATE INDEX IF NOT EXISTS idx_nom_article ON nomenclature(article);

-- 4. Unique nomenclature (для нормализации)
CREATE TABLE IF NOT EXISTS unique_nomenclature (
    id SERIAL PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    canonical_article VARCHAR(100),
    nomenclature_id INTEGER REFERENCES nomenclature(id),
    zip_nomenclature_id UUID,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    is_processed BOOLEAN DEFAULT FALSE,
    confidence NUMERIC(3,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 5. Current prices (текущие цены)
CREATE TABLE IF NOT EXISTS current_prices (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER NOT NULL REFERENCES nomenclature(id) ON DELETE CASCADE,
    outlet_id INTEGER NOT NULL REFERENCES outlets(id) ON DELETE CASCADE,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(nomenclature_id, outlet_id)
);
CREATE INDEX IF NOT EXISTS idx_prices_nom ON current_prices(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_prices_outlet ON current_prices(outlet_id);

-- 6. Price history (история цен)
CREATE TABLE IF NOT EXISTS price_history (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER NOT NULL REFERENCES nomenclature(id) ON DELETE CASCADE,
    outlet_id INTEGER NOT NULL REFERENCES outlets(id) ON DELETE CASCADE,
    price NUMERIC(12,2),
    recorded_date DATE DEFAULT CURRENT_DATE,
    recorded_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(nomenclature_id, outlet_id, recorded_date)
);
CREATE INDEX IF NOT EXISTS idx_history_date ON price_history(recorded_date);
