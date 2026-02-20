-- =============================================================================
-- init_local_db.sql — Схема локальной БД для парсеров (Homelab Supabase)
-- v10: {shop}_prices → {shop}_product_urls, price переехал в nomenclature
-- Создаёт таблицы для 10 магазинов + zip_outlets
-- Запуск: psql "postgresql://postgres:<password>@localhost:5432/postgres" < init_local_db.sql
-- =============================================================================

-- ========================= zip_outlets (копия из облака) =========================

CREATE TABLE IF NOT EXISTS zip_outlets (
    id UUID PRIMARY KEY,
    shop_id INTEGER,
    code VARCHAR(50) UNIQUE,
    name VARCHAR(200),
    city VARCHAR(100),
    address TEXT,
    phone VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========================= _05gsm =========================

CREATE TABLE IF NOT EXISTS _05gsm_staging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outlet_code VARCHAR(50),
    article VARCHAR(255),
    name TEXT,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    product_url TEXT,
    loaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx__05gsm_staging_article ON _05gsm_staging(article);

CREATE TABLE IF NOT EXISTS _05gsm_nomenclature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article VARCHAR(100) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    device_type VARCHAR(50),
    product_id VARCHAR(255),
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    normalized_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx__05gsm_nom_article ON _05gsm_nomenclature(article);
CREATE INDEX IF NOT EXISTS idx__05gsm_nom_updated ON _05gsm_nomenclature(updated_at);

CREATE TABLE IF NOT EXISTS _05gsm_product_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nomenclature_id UUID NOT NULL REFERENCES _05gsm_nomenclature(id) ON DELETE CASCADE,
    outlet_id UUID,
    url TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT _05gsm_product_urls_url_unique UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx__05gsm_product_urls_nom ON _05gsm_product_urls(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx__05gsm_product_urls_updated ON _05gsm_product_urls(updated_at);

-- ========================= memstech =========================

CREATE TABLE IF NOT EXISTS memstech_staging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outlet_code VARCHAR(50),
    article VARCHAR(255),
    name TEXT,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    product_url TEXT,
    loaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_memstech_staging_article ON memstech_staging(article);

CREATE TABLE IF NOT EXISTS memstech_nomenclature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article VARCHAR(100) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    device_type VARCHAR(50),
    product_id VARCHAR(255),
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    normalized_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_memstech_nom_article ON memstech_nomenclature(article);
CREATE INDEX IF NOT EXISTS idx_memstech_nom_updated ON memstech_nomenclature(updated_at);

CREATE TABLE IF NOT EXISTS memstech_product_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nomenclature_id UUID NOT NULL REFERENCES memstech_nomenclature(id) ON DELETE CASCADE,
    outlet_id UUID,
    url TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT memstech_product_urls_url_unique UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx_memstech_product_urls_nom ON memstech_product_urls(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_memstech_product_urls_updated ON memstech_product_urls(updated_at);

-- ========================= signal23 =========================

CREATE TABLE IF NOT EXISTS signal23_staging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outlet_code VARCHAR(50),
    article VARCHAR(255),
    name TEXT,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    product_url TEXT,
    loaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_signal23_staging_article ON signal23_staging(article);

CREATE TABLE IF NOT EXISTS signal23_nomenclature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article VARCHAR(100) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    device_type VARCHAR(50),
    product_id VARCHAR(255),
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    normalized_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_signal23_nom_article ON signal23_nomenclature(article);
CREATE INDEX IF NOT EXISTS idx_signal23_nom_updated ON signal23_nomenclature(updated_at);

CREATE TABLE IF NOT EXISTS signal23_product_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nomenclature_id UUID NOT NULL REFERENCES signal23_nomenclature(id) ON DELETE CASCADE,
    outlet_id UUID,
    url TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT signal23_product_urls_url_unique UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx_signal23_product_urls_nom ON signal23_product_urls(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_signal23_product_urls_updated ON signal23_product_urls(updated_at);

-- ========================= taggsm =========================

CREATE TABLE IF NOT EXISTS taggsm_staging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outlet_code VARCHAR(50),
    article VARCHAR(255),
    name TEXT,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    product_url TEXT,
    loaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_taggsm_staging_article ON taggsm_staging(article);

CREATE TABLE IF NOT EXISTS taggsm_nomenclature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article VARCHAR(100) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    device_type VARCHAR(50),
    product_id VARCHAR(255),
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    normalized_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_taggsm_nom_article ON taggsm_nomenclature(article);
CREATE INDEX IF NOT EXISTS idx_taggsm_nom_updated ON taggsm_nomenclature(updated_at);

CREATE TABLE IF NOT EXISTS taggsm_product_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nomenclature_id UUID NOT NULL REFERENCES taggsm_nomenclature(id) ON DELETE CASCADE,
    outlet_id UUID,
    url TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT taggsm_product_urls_url_unique UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx_taggsm_product_urls_nom ON taggsm_product_urls(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_taggsm_product_urls_updated ON taggsm_product_urls(updated_at);

-- ========================= liberti =========================

CREATE TABLE IF NOT EXISTS liberti_staging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outlet_code VARCHAR(50),
    article VARCHAR(255),
    name TEXT,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    product_url TEXT,
    loaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_liberti_staging_article ON liberti_staging(article);

CREATE TABLE IF NOT EXISTS liberti_nomenclature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article VARCHAR(100) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    device_type VARCHAR(50),
    product_id VARCHAR(255),
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    normalized_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_liberti_nom_article ON liberti_nomenclature(article);
CREATE INDEX IF NOT EXISTS idx_liberti_nom_updated ON liberti_nomenclature(updated_at);

CREATE TABLE IF NOT EXISTS liberti_product_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nomenclature_id UUID NOT NULL REFERENCES liberti_nomenclature(id) ON DELETE CASCADE,
    outlet_id UUID,
    url TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT liberti_product_urls_url_unique UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx_liberti_product_urls_nom ON liberti_product_urls(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_liberti_product_urls_updated ON liberti_product_urls(updated_at);

-- ========================= profi =========================

CREATE TABLE IF NOT EXISTS profi_staging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outlet_code VARCHAR(50),
    article VARCHAR(255),
    name TEXT,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    product_url TEXT,
    loaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_profi_staging_article ON profi_staging(article);

CREATE TABLE IF NOT EXISTS profi_nomenclature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article VARCHAR(100) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    device_type VARCHAR(50),
    product_id VARCHAR(255),
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    normalized_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_profi_nom_article ON profi_nomenclature(article);
CREATE INDEX IF NOT EXISTS idx_profi_nom_updated ON profi_nomenclature(updated_at);

CREATE TABLE IF NOT EXISTS profi_product_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nomenclature_id UUID NOT NULL REFERENCES profi_nomenclature(id) ON DELETE CASCADE,
    outlet_id UUID,
    url TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT profi_product_urls_url_unique UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx_profi_product_urls_nom ON profi_product_urls(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_profi_product_urls_updated ON profi_product_urls(updated_at);

-- ========================= lcdstock =========================

CREATE TABLE IF NOT EXISTS lcdstock_staging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outlet_code VARCHAR(50),
    article VARCHAR(255),
    name TEXT,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    product_url TEXT,
    loaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_lcdstock_staging_article ON lcdstock_staging(article);

CREATE TABLE IF NOT EXISTS lcdstock_nomenclature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article VARCHAR(100) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    device_type VARCHAR(50),
    product_id VARCHAR(255),
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    normalized_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_lcdstock_nom_article ON lcdstock_nomenclature(article);
CREATE INDEX IF NOT EXISTS idx_lcdstock_nom_updated ON lcdstock_nomenclature(updated_at);

CREATE TABLE IF NOT EXISTS lcdstock_product_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nomenclature_id UUID NOT NULL REFERENCES lcdstock_nomenclature(id) ON DELETE CASCADE,
    outlet_id UUID,
    url TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT lcdstock_product_urls_url_unique UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx_lcdstock_product_urls_nom ON lcdstock_product_urls(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_lcdstock_product_urls_updated ON lcdstock_product_urls(updated_at);

-- ========================= orizhka =========================

CREATE TABLE IF NOT EXISTS orizhka_staging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outlet_code VARCHAR(50),
    article VARCHAR(255),
    name TEXT,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    product_url TEXT,
    loaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_orizhka_staging_article ON orizhka_staging(article);

CREATE TABLE IF NOT EXISTS orizhka_nomenclature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article VARCHAR(100) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    device_type VARCHAR(50),
    product_id VARCHAR(255),
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    normalized_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_orizhka_nom_article ON orizhka_nomenclature(article);
CREATE INDEX IF NOT EXISTS idx_orizhka_nom_updated ON orizhka_nomenclature(updated_at);

CREATE TABLE IF NOT EXISTS orizhka_product_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nomenclature_id UUID NOT NULL REFERENCES orizhka_nomenclature(id) ON DELETE CASCADE,
    outlet_id UUID,
    url TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT orizhka_product_urls_url_unique UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx_orizhka_product_urls_nom ON orizhka_product_urls(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_orizhka_product_urls_updated ON orizhka_product_urls(updated_at);

-- ========================= moysklad_naffas =========================

CREATE TABLE IF NOT EXISTS moysklad_naffas_staging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outlet_code VARCHAR(50),
    article VARCHAR(255),
    name TEXT,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    product_url TEXT,
    loaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_moysklad_naffas_staging_article ON moysklad_naffas_staging(article);

CREATE TABLE IF NOT EXISTS moysklad_naffas_nomenclature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article VARCHAR(100) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    device_type VARCHAR(50),
    product_id VARCHAR(255),
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    normalized_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_moysklad_naffas_nom_article ON moysklad_naffas_nomenclature(article);
CREATE INDEX IF NOT EXISTS idx_moysklad_naffas_nom_updated ON moysklad_naffas_nomenclature(updated_at);

CREATE TABLE IF NOT EXISTS moysklad_naffas_product_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nomenclature_id UUID NOT NULL REFERENCES moysklad_naffas_nomenclature(id) ON DELETE CASCADE,
    outlet_id UUID,
    url TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT moysklad_naffas_product_urls_url_unique UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx_moysklad_naffas_product_urls_nom ON moysklad_naffas_product_urls(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_moysklad_naffas_product_urls_updated ON moysklad_naffas_product_urls(updated_at);

-- ========================= moba =========================

CREATE TABLE IF NOT EXISTS moba_staging (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outlet_code VARCHAR(50),
    article VARCHAR(255),
    name TEXT,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    category VARCHAR(100),
    url TEXT,
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    product_url TEXT,
    loaded_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_moba_staging_article ON moba_staging(article);

CREATE TABLE IF NOT EXISTS moba_nomenclature (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article VARCHAR(100) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    barcode VARCHAR(50),
    brand_raw VARCHAR(200),
    model_raw VARCHAR(200),
    part_type_raw VARCHAR(200),
    category_raw TEXT,
    category VARCHAR(100),
    brand VARCHAR(100),
    model VARCHAR(200),
    part_type VARCHAR(100),
    device_type VARCHAR(50),
    product_id VARCHAR(255),
    price NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    zip_nomenclature_id UUID,
    zip_brand_id UUID,
    zip_part_type_id INTEGER,
    zip_quality_id INTEGER,
    zip_color_id INTEGER,
    normalized_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_moba_nom_article ON moba_nomenclature(article);
CREATE INDEX IF NOT EXISTS idx_moba_nom_updated ON moba_nomenclature(updated_at);

CREATE TABLE IF NOT EXISTS moba_product_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nomenclature_id UUID NOT NULL REFERENCES moba_nomenclature(id) ON DELETE CASCADE,
    outlet_id UUID,
    url TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT moba_product_urls_url_unique UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx_moba_product_urls_nom ON moba_product_urls(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_moba_product_urls_updated ON moba_product_urls(updated_at);

-- ========================= Готово =========================
-- v10: 10 магазинов × 3 таблицы (nomenclature + product_urls + staging) = 30 таблиц + zip_outlets = 31 таблица
