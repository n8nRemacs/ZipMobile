-- Migration v9.0: Remove stock tables and columns
-- Run on Homelab PostgreSQL (port 5433)
-- Date: 2026-02-20

BEGIN;

-- 1. Drop central stock tables
DROP TABLE IF EXISTS zip_current_stock CASCADE;
DROP TABLE IF EXISTS zip_stock_history CASCADE;

-- 2. Drop stock_mode from zip_outlets
ALTER TABLE zip_outlets DROP COLUMN IF EXISTS stock_mode;

-- 3. Drop stock columns from {shop}_prices (all 11 shops)
DO $$
DECLARE
    shop TEXT;
BEGIN
    FOR shop IN SELECT unnest(ARRAY[
        '_05gsm', 'greenspark', 'taggsm', 'memstech', 'liberti',
        'profi', 'lcdstock', 'orizhka', 'moba', 'moysklad_naffas', 'signal23'
    ])
    LOOP
        EXECUTE format('ALTER TABLE IF EXISTS %I_prices DROP COLUMN IF EXISTS in_stock', shop);
        EXECUTE format('ALTER TABLE IF EXISTS %I_prices DROP COLUMN IF EXISTS stock_stars', shop);
        EXECUTE format('ALTER TABLE IF EXISTS %I_prices DROP COLUMN IF EXISTS quantity', shop);
    END LOOP;
END $$;

-- 4. Drop stock columns from {shop}_staging (all 11 shops)
DO $$
DECLARE
    shop TEXT;
BEGIN
    FOR shop IN SELECT unnest(ARRAY[
        '_05gsm', 'greenspark', 'taggsm', 'memstech', 'liberti',
        'profi', 'lcdstock', 'orizhka', 'moba', 'moysklad_naffas', 'signal23'
    ])
    LOOP
        EXECUTE format('ALTER TABLE IF EXISTS %I_staging DROP COLUMN IF EXISTS in_stock', shop);
        EXECUTE format('ALTER TABLE IF EXISTS %I_staging DROP COLUMN IF EXISTS stock_level', shop);
    END LOOP;
END $$;

COMMIT;

-- Verification queries (run after migration):
-- SELECT table_name FROM information_schema.tables WHERE table_name IN ('zip_current_stock','zip_stock_history');
-- Should return 0 rows

-- SELECT table_name, column_name FROM information_schema.columns
-- WHERE table_name LIKE '%_prices' AND column_name IN ('in_stock','stock_stars','quantity');
-- Should return 0 rows

-- SELECT column_name FROM information_schema.columns
-- WHERE table_name = 'zip_outlets' AND column_name = 'stock_mode';
-- Should return 0 rows
