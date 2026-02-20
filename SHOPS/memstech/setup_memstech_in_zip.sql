-- Setup MemsTech в центральной БД zip_*
-- Выполнить один раз: psql -h localhost -p 5432 -U postgres -d postgres -f setup_memstech_in_zip.sql

-- ============================================
-- 1. МАГАЗИН (zip_shops)
-- ============================================

INSERT INTO zip_shops (code, name, website, shop_type, company_name, parser_enabled, is_active)
VALUES (
    'memstech',
    'MemsTech',
    'https://memstech.ru',
    'retailer',
    'MemsTech',
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

INSERT INTO zip_cities (code, name, region_name, is_active) VALUES
    ('moskva', 'Москва', 'Москва', true),
    ('spb', 'Санкт-Петербург', 'Санкт-Петербург', true),
    ('ekaterinburg', 'Екатеринбург', 'Свердловская область', true),
    ('khabarovsk', 'Хабаровск', 'Хабаровский край', true),
    ('krasnodar', 'Краснодар', 'Краснодарский край', true),
    ('kotlas', 'Котлас', 'Архангельская область', true),
    ('magnitogorsk', 'Магнитогорск', 'Челябинская область', true),
    ('kazan', 'Казань', 'Республика Татарстан', true),
    ('omsk', 'Омск', 'Омская область', true),
    ('rostov-na-donu', 'Ростов-на-Дону', 'Ростовская область', true),
    ('syktyvkar', 'Сыктывкар', 'Республика Коми', true),
    ('nizhniy-novgorod', 'Нижний Новгород', 'Нижегородская область', true),
    ('chelyabinsk', 'Челябинск', 'Челябинская область', true),
    ('yaroslavl', 'Ярославль', 'Ярославская область', true),
    ('perm', 'Пермь', 'Пермский край', true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    region_name = EXCLUDED.region_name;

-- ============================================
-- 3. ТОРГОВЫЕ ТОЧКИ (zip_outlets)
-- ============================================

WITH shop AS (
    SELECT id FROM zip_shops WHERE code = 'memstech'
),
cities AS (
    SELECT code, id FROM zip_cities
)
INSERT INTO zip_outlets (shop_id, city_id, code, name, is_active, api_config)
SELECT
    s.id,
    c.id,
    v.outlet_code,
    v.outlet_name,
    true,
    v.api_config::jsonb
FROM shop s
CROSS JOIN (VALUES
    -- Москва (4 магазина, парсим как одну точку)
    ('moskva', 'memstech-memstech.ru', 'MemsTech Москва', '{"subdomain": "memstech.ru", "shops_count": 4}'),
    -- Санкт-Петербург (2 магазина)
    ('spb', 'memstech-spb', 'MemsTech Санкт-Петербург', '{"subdomain": "spb", "shops_count": 2}'),
    -- Остальные города (по 1 магазину)
    ('ekaterinburg', 'memstech-ekb', 'MemsTech Екатеринбург', '{"subdomain": "ekb"}'),
    ('khabarovsk', 'memstech-khb', 'MemsTech Хабаровск', '{"subdomain": "khb"}'),
    ('krasnodar', 'memstech-krd', 'MemsTech Краснодар', '{"subdomain": "krd"}'),
    ('kotlas', 'memstech-ktl', 'MemsTech Котлас', '{"subdomain": "ktl"}'),
    ('magnitogorsk', 'memstech-mgg', 'MemsTech Магнитогорск', '{"subdomain": "mgg"}'),
    ('kazan', 'memstech-kzn', 'MemsTech Казань', '{"subdomain": "kzn"}'),
    ('omsk', 'memstech-omsk', 'MemsTech Омск', '{"subdomain": "omsk"}'),
    ('rostov-na-donu', 'memstech-rnd', 'MemsTech Ростов-на-Дону', '{"subdomain": "rnd"}'),
    ('syktyvkar', 'memstech-skt', 'MemsTech Сыктывкар', '{"subdomain": "skt"}'),
    ('nizhniy-novgorod', 'memstech-nn', 'MemsTech Нижний Новгород', '{"subdomain": "nn"}'),
    ('chelyabinsk', 'memstech-chel', 'MemsTech Челябинск', '{"subdomain": "chel"}'),
    ('yaroslavl', 'memstech-yar', 'MemsTech Ярославль', '{"subdomain": "yar"}'),
    ('perm', 'memstech-perm', 'MemsTech Пермь', '{"subdomain": "perm"}')
) AS v(city_code, outlet_code, outlet_name, api_config)
JOIN cities c ON c.code = v.city_code
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
    s.name AS shop,
    o.api_config->>'subdomain' AS subdomain
FROM zip_outlets o
JOIN zip_shops s ON o.shop_id = s.id
JOIN zip_cities c ON o.city_id = c.id
WHERE s.code = 'memstech'
ORDER BY c.name;
