-- Setup Naffas в центральной БД zip_*
-- Выполнить один раз: psql -h localhost -p 5432 -U postgres -d postgres -f setup_naffas_in_zip.sql

-- ============================================
-- 1. МАГАЗИН (zip_shops)
-- ============================================

INSERT INTO zip_shops (code, name, website, shop_type, company_name, parser_enabled, is_active)
VALUES (
    'naffas',
    'Naffas',
    'https://naffas.ru',
    'wholesale',
    'Naffas (МойСклад)',
    true,
    true
)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    website = EXCLUDED.website,
    parser_enabled = EXCLUDED.parser_enabled;

-- ============================================
-- 2. ГОРОДА (zip_cities)
-- ============================================

-- Naffas работает только онлайн (Москва)
INSERT INTO zip_cities (code, name, region_name, is_active) VALUES
    ('moskva', 'Москва', 'Москва', true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    region_name = EXCLUDED.region_name;

-- ============================================
-- 3. ТОРГОВЫЕ ТОЧКИ (zip_outlets)
-- ============================================

WITH shop AS (
    SELECT id FROM zip_shops WHERE code = 'naffas'
),
cities AS (
    SELECT code, id FROM zip_cities
)
INSERT INTO zip_outlets (shop_id, city_id, code, name, is_active, api_config)
SELECT
    s.id,
    c.id,
    'naffas-online',
    'Naffas Online (МойСклад)',
    true,
    '{"source": "moysklad"}'::jsonb
FROM shop s
JOIN cities c ON c.code = 'moskva'
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    api_config = EXCLUDED.api_config;

-- ============================================
-- 4. ПРОВЕРКА
-- ============================================

SELECT
    o.code AS outlet_code,
    o.name AS outlet_name,
    c.name AS city,
    s.name AS shop
FROM zip_outlets o
JOIN zip_shops s ON o.shop_id = s.id
JOIN zip_cities c ON o.city_id = c.id
WHERE s.code = 'naffas';
