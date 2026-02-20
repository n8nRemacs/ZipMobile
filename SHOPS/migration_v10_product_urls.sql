-- =============================================================================
-- migration_v10_product_urls.sql
-- Миграция v10: {shop}_prices → {shop}_product_urls
-- price, price_wholesale переезжают в {shop}_nomenclature
--
-- Запуск: psql "postgresql://postgres:Mi31415926pSss!@localhost:5433/postgres" < migration_v10_product_urls.sql
-- =============================================================================

BEGIN;

-- ========================= _05gsm =========================

ALTER TABLE _05gsm_nomenclature ADD COLUMN IF NOT EXISTS price NUMERIC(12,2);
ALTER TABLE _05gsm_nomenclature ADD COLUMN IF NOT EXISTS price_wholesale NUMERIC(12,2);

UPDATE _05gsm_nomenclature n SET
    price = p.price
FROM (
    SELECT DISTINCT ON (nomenclature_id) nomenclature_id, price
    FROM _05gsm_prices
    ORDER BY nomenclature_id, updated_at DESC
) p
WHERE n.id = p.nomenclature_id;

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

INSERT INTO _05gsm_product_urls (nomenclature_id, outlet_id, url, updated_at)
SELECT DISTINCT ON (product_url) nomenclature_id, NULL, product_url, updated_at
FROM _05gsm_prices
WHERE product_url IS NOT NULL AND product_url != ''
ORDER BY product_url, updated_at DESC
ON CONFLICT (url) DO NOTHING;

ALTER TABLE _05gsm_prices RENAME TO _05gsm_prices_deprecated;

-- ========================= memstech (multi-URL) =========================

ALTER TABLE memstech_nomenclature ADD COLUMN IF NOT EXISTS price NUMERIC(12,2);
ALTER TABLE memstech_nomenclature ADD COLUMN IF NOT EXISTS price_wholesale NUMERIC(12,2);

UPDATE memstech_nomenclature n SET
    price = p.price
FROM (
    SELECT DISTINCT ON (nomenclature_id) nomenclature_id, price
    FROM memstech_prices
    ORDER BY nomenclature_id, updated_at DESC
) p
WHERE n.id = p.nomenclature_id;

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

-- MemsTech = multi-URL, сохраняем outlet_id
INSERT INTO memstech_product_urls (nomenclature_id, outlet_id, url, updated_at)
SELECT DISTINCT ON (product_url) nomenclature_id, outlet_id, product_url, updated_at
FROM memstech_prices
WHERE product_url IS NOT NULL AND product_url != ''
ORDER BY product_url, updated_at DESC
ON CONFLICT (url) DO NOTHING;

ALTER TABLE memstech_prices RENAME TO memstech_prices_deprecated;

-- ========================= signal23 =========================

ALTER TABLE signal23_nomenclature ADD COLUMN IF NOT EXISTS price NUMERIC(12,2);
ALTER TABLE signal23_nomenclature ADD COLUMN IF NOT EXISTS price_wholesale NUMERIC(12,2);

UPDATE signal23_nomenclature n SET
    price = p.price
FROM (
    SELECT DISTINCT ON (nomenclature_id) nomenclature_id, price
    FROM signal23_prices
    ORDER BY nomenclature_id, updated_at DESC
) p
WHERE n.id = p.nomenclature_id;

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

INSERT INTO signal23_product_urls (nomenclature_id, outlet_id, url, updated_at)
SELECT DISTINCT ON (product_url) nomenclature_id, NULL, product_url, updated_at
FROM signal23_prices
WHERE product_url IS NOT NULL AND product_url != ''
ORDER BY product_url, updated_at DESC
ON CONFLICT (url) DO NOTHING;

ALTER TABLE signal23_prices RENAME TO signal23_prices_deprecated;

-- ========================= taggsm =========================

ALTER TABLE taggsm_nomenclature ADD COLUMN IF NOT EXISTS price NUMERIC(12,2);
ALTER TABLE taggsm_nomenclature ADD COLUMN IF NOT EXISTS price_wholesale NUMERIC(12,2);

UPDATE taggsm_nomenclature n SET
    price = p.price
FROM (
    SELECT DISTINCT ON (nomenclature_id) nomenclature_id, price
    FROM taggsm_prices
    ORDER BY nomenclature_id, updated_at DESC
) p
WHERE n.id = p.nomenclature_id;

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

INSERT INTO taggsm_product_urls (nomenclature_id, outlet_id, url, updated_at)
SELECT DISTINCT ON (product_url) nomenclature_id, NULL, product_url, updated_at
FROM taggsm_prices
WHERE product_url IS NOT NULL AND product_url != ''
ORDER BY product_url, updated_at DESC
ON CONFLICT (url) DO NOTHING;

ALTER TABLE taggsm_prices RENAME TO taggsm_prices_deprecated;

-- ========================= liberti =========================

ALTER TABLE liberti_nomenclature ADD COLUMN IF NOT EXISTS price NUMERIC(12,2);
ALTER TABLE liberti_nomenclature ADD COLUMN IF NOT EXISTS price_wholesale NUMERIC(12,2);

UPDATE liberti_nomenclature n SET
    price = p.price
FROM (
    SELECT DISTINCT ON (nomenclature_id) nomenclature_id, price
    FROM liberti_prices
    ORDER BY nomenclature_id, updated_at DESC
) p
WHERE n.id = p.nomenclature_id;

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

INSERT INTO liberti_product_urls (nomenclature_id, outlet_id, url, updated_at)
SELECT DISTINCT ON (product_url) nomenclature_id, NULL, product_url, updated_at
FROM liberti_prices
WHERE product_url IS NOT NULL AND product_url != ''
ORDER BY product_url, updated_at DESC
ON CONFLICT (url) DO NOTHING;

ALTER TABLE liberti_prices RENAME TO liberti_prices_deprecated;

-- ========================= profi =========================

ALTER TABLE profi_nomenclature ADD COLUMN IF NOT EXISTS price NUMERIC(12,2);
ALTER TABLE profi_nomenclature ADD COLUMN IF NOT EXISTS price_wholesale NUMERIC(12,2);

UPDATE profi_nomenclature n SET
    price = p.price
FROM (
    SELECT DISTINCT ON (nomenclature_id) nomenclature_id, price
    FROM profi_prices
    ORDER BY nomenclature_id, updated_at DESC
) p
WHERE n.id = p.nomenclature_id;

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

INSERT INTO profi_product_urls (nomenclature_id, outlet_id, url, updated_at)
SELECT DISTINCT ON (product_url) nomenclature_id, NULL, product_url, updated_at
FROM profi_prices
WHERE product_url IS NOT NULL AND product_url != ''
ORDER BY product_url, updated_at DESC
ON CONFLICT (url) DO NOTHING;

ALTER TABLE profi_prices RENAME TO profi_prices_deprecated;

-- ========================= lcdstock =========================

ALTER TABLE lcdstock_nomenclature ADD COLUMN IF NOT EXISTS price NUMERIC(12,2);
ALTER TABLE lcdstock_nomenclature ADD COLUMN IF NOT EXISTS price_wholesale NUMERIC(12,2);

UPDATE lcdstock_nomenclature n SET
    price = p.price
FROM (
    SELECT DISTINCT ON (nomenclature_id) nomenclature_id, price
    FROM lcdstock_prices
    ORDER BY nomenclature_id, updated_at DESC
) p
WHERE n.id = p.nomenclature_id;

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

INSERT INTO lcdstock_product_urls (nomenclature_id, outlet_id, url, updated_at)
SELECT DISTINCT ON (product_url) nomenclature_id, NULL, product_url, updated_at
FROM lcdstock_prices
WHERE product_url IS NOT NULL AND product_url != ''
ORDER BY product_url, updated_at DESC
ON CONFLICT (url) DO NOTHING;

ALTER TABLE lcdstock_prices RENAME TO lcdstock_prices_deprecated;

-- ========================= orizhka =========================

ALTER TABLE orizhka_nomenclature ADD COLUMN IF NOT EXISTS price NUMERIC(12,2);
ALTER TABLE orizhka_nomenclature ADD COLUMN IF NOT EXISTS price_wholesale NUMERIC(12,2);

UPDATE orizhka_nomenclature n SET
    price = p.price
FROM (
    SELECT DISTINCT ON (nomenclature_id) nomenclature_id, price
    FROM orizhka_prices
    ORDER BY nomenclature_id, updated_at DESC
) p
WHERE n.id = p.nomenclature_id;

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

INSERT INTO orizhka_product_urls (nomenclature_id, outlet_id, url, updated_at)
SELECT DISTINCT ON (product_url) nomenclature_id, NULL, product_url, updated_at
FROM orizhka_prices
WHERE product_url IS NOT NULL AND product_url != ''
ORDER BY product_url, updated_at DESC
ON CONFLICT (url) DO NOTHING;

ALTER TABLE orizhka_prices RENAME TO orizhka_prices_deprecated;

-- ========================= moysklad_naffas =========================

ALTER TABLE moysklad_naffas_nomenclature ADD COLUMN IF NOT EXISTS price NUMERIC(12,2);
ALTER TABLE moysklad_naffas_nomenclature ADD COLUMN IF NOT EXISTS price_wholesale NUMERIC(12,2);

UPDATE moysklad_naffas_nomenclature n SET
    price = p.price
FROM (
    SELECT DISTINCT ON (nomenclature_id) nomenclature_id, price
    FROM moysklad_naffas_prices
    ORDER BY nomenclature_id, updated_at DESC
) p
WHERE n.id = p.nomenclature_id;

-- Naffas не имеет URL, таблицу создаём для единообразия
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

-- Naffas: нет product_url, вставка не нужна

ALTER TABLE moysklad_naffas_prices RENAME TO moysklad_naffas_prices_deprecated;

-- ========================= moba (multi-URL) =========================

ALTER TABLE moba_nomenclature ADD COLUMN IF NOT EXISTS price NUMERIC(12,2);
ALTER TABLE moba_nomenclature ADD COLUMN IF NOT EXISTS price_wholesale NUMERIC(12,2);

UPDATE moba_nomenclature n SET
    price = p.price
FROM (
    SELECT DISTINCT ON (nomenclature_id) nomenclature_id, price
    FROM moba_prices
    ORDER BY nomenclature_id, updated_at DESC
) p
WHERE n.id = p.nomenclature_id;

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

-- Moba = multi-URL, сохраняем outlet_id
INSERT INTO moba_product_urls (nomenclature_id, outlet_id, url, updated_at)
SELECT DISTINCT ON (product_url) nomenclature_id, outlet_id, product_url, updated_at
FROM moba_prices
WHERE product_url IS NOT NULL AND product_url != ''
ORDER BY product_url, updated_at DESC
ON CONFLICT (url) DO NOTHING;

ALTER TABLE moba_prices RENAME TO moba_prices_deprecated;

-- ========================= greenspark =========================

ALTER TABLE greenspark_nomenclature ADD COLUMN IF NOT EXISTS price NUMERIC(12,2);
ALTER TABLE greenspark_nomenclature ADD COLUMN IF NOT EXISTS price_wholesale NUMERIC(12,2);

UPDATE greenspark_nomenclature n SET
    price = p.price
FROM (
    SELECT DISTINCT ON (nomenclature_id) nomenclature_id, price
    FROM greenspark_prices
    ORDER BY nomenclature_id, updated_at DESC
) p
WHERE n.id = p.nomenclature_id;

CREATE TABLE IF NOT EXISTS greenspark_product_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nomenclature_id UUID NOT NULL REFERENCES greenspark_nomenclature(id) ON DELETE CASCADE,
    outlet_id UUID,
    url TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT greenspark_product_urls_url_unique UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS idx_greenspark_product_urls_nom ON greenspark_product_urls(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_greenspark_product_urls_updated ON greenspark_product_urls(updated_at);

INSERT INTO greenspark_product_urls (nomenclature_id, outlet_id, url, updated_at)
SELECT DISTINCT ON (product_url) nomenclature_id, NULL, product_url, updated_at
FROM greenspark_prices
WHERE product_url IS NOT NULL AND product_url != ''
ORDER BY product_url, updated_at DESC
ON CONFLICT (url) DO NOTHING;

ALTER TABLE greenspark_prices RENAME TO greenspark_prices_deprecated;

-- ========================= Верификация =========================

-- Проверяем что все product_urls таблицы создались
DO $$
DECLARE
    cnt INTEGER;
BEGIN
    SELECT count(*) INTO cnt
    FROM information_schema.tables
    WHERE table_name LIKE '%_product_urls%'
      AND table_schema = 'public';
    RAISE NOTICE 'product_urls tables created: %', cnt;

    SELECT count(*) INTO cnt
    FROM information_schema.tables
    WHERE table_name LIKE '%_prices_deprecated%'
      AND table_schema = 'public';
    RAISE NOTICE 'prices tables deprecated: %', cnt;

    SELECT count(*) INTO cnt
    FROM information_schema.columns
    WHERE table_name LIKE '%_nomenclature%'
      AND column_name = 'price'
      AND table_schema = 'public';
    RAISE NOTICE 'nomenclature tables with price column: %', cnt;
END $$;

COMMIT;
