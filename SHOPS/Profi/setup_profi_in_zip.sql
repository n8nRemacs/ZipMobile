-- Добавление магазина Профи и всех торговых точек в архитектуру zip_*
-- Выполнить один раз для инициализации

-- ============================================
-- 1. МАГАЗИН (zip_shops)
-- ============================================

INSERT INTO zip_shops (code, name, website, shop_type, company_name, parser_enabled, is_active)
VALUES (
    'profi',
    'Профи',
    'https://siriust.ru',
    'wholesale',
    'ООО «СИРИУС-Т»',
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
    ('adler', 'Адлер', 'Краснодарский край', true),
    ('arkhangelsk', 'Архангельск', 'Архангельская область', true),
    ('astrakhan', 'Астрахань', 'Астраханская область', true),
    ('volgograd', 'Волгоград', 'Волгоградская область', true),
    ('voronezh', 'Воронеж', 'Воронежская область', true),
    ('ekaterinburg', 'Екатеринбург', 'Свердловская область', true),
    ('izhevsk', 'Ижевск', 'Удмуртская Республика', true),
    ('kazan', 'Казань', 'Республика Татарстан', true),
    ('kaliningrad', 'Калининград', 'Калининградская область', true),
    ('krasnodar', 'Краснодар', 'Краснодарский край', true),
    ('krasnoyarsk', 'Красноярск', 'Красноярский край', true),
    ('nizhniy-novgorod', 'Нижний Новгород', 'Нижегородская область', true),
    ('novosibirsk', 'Новосибирск', 'Новосибирская область', true),
    ('omsk', 'Омск', 'Омская область', true),
    ('perm', 'Пермь', 'Пермский край', true),
    ('rostov-na-donu', 'Ростов-на-Дону', 'Ростовская область', true),
    ('samara', 'Самара', 'Самарская область', true),
    ('saratov', 'Саратов', 'Саратовская область', true),
    ('tyumen', 'Тюмень', 'Тюменская область', true),
    ('ufa', 'Уфа', 'Республика Башкортостан', true),
    ('chelyabinsk', 'Челябинск', 'Челябинская область', true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    region_name = EXCLUDED.region_name;

-- ============================================
-- 3. ТОРГОВЫЕ ТОЧКИ (zip_outlets)
-- ============================================

-- Получаем ID магазина Профи
WITH shop AS (
    SELECT id FROM zip_shops WHERE code = 'profi'
),
-- Маппинг city_code -> city_id
cities AS (
    SELECT code, id FROM zip_cities
)
INSERT INTO zip_outlets (shop_id, city_id, code, name, is_active)
SELECT
    s.id,
    c.id,
    v.outlet_code,
    v.outlet_name,
    true
FROM shop s
CROSS JOIN (VALUES
    -- Москва
    ('moskva', 'profi-msk-opt', 'Отдел оптовых продаж'),
    ('moskva', 'profi-msk-savelovo', 'Савеловский радиорынок'),
    ('moskva', 'profi-msk-mitino', 'Митинский радиорынок'),
    ('moskva', 'profi-msk-yuzhny', 'Радиокомплекс Южный'),
    -- Санкт-Петербург
    ('spb', 'profi-spb-1', 'СПб точка 1'),
    ('spb', 'profi-spb-2', 'СПб точка 2'),
    -- Адлер
    ('adler', 'profi-adler', 'Профи Адлер'),
    -- Архангельск
    ('arkhangelsk', 'profi-arkhangelsk', 'Профи Архангельск'),
    -- Астрахань
    ('astrakhan', 'profi-astrakhan', 'Профи Астрахань'),
    -- Волгоград
    ('volgograd', 'profi-volgograd', 'Профи Волгоград'),
    -- Воронеж
    ('voronezh', 'profi-voronezh', 'Профи Воронеж'),
    -- Екатеринбург
    ('ekaterinburg', 'profi-ekb-1', 'Екатеринбург точка 1'),
    ('ekaterinburg', 'profi-ekb-2', 'Екатеринбург точка 2'),
    -- Ижевск
    ('izhevsk', 'profi-izhevsk-1', 'Ижевск точка 1'),
    ('izhevsk', 'profi-izhevsk-2', 'Ижевск точка 2'),
    -- Казань
    ('kazan', 'profi-kazan-1', 'Казань точка 1'),
    ('kazan', 'profi-kazan-2', 'Казань точка 2'),
    -- Калининград
    ('kaliningrad', 'profi-kaliningrad', 'Профи Калининград'),
    -- Краснодар
    ('krasnodar', 'profi-krasnodar-1', 'Краснодар точка 1'),
    ('krasnodar', 'profi-krasnodar-2', 'Краснодар точка 2'),
    -- Красноярск
    ('krasnoyarsk', 'profi-krasnoyarsk-1', 'Красноярск точка 1'),
    ('krasnoyarsk', 'profi-krasnoyarsk-2', 'Красноярск точка 2'),
    -- Нижний Новгород
    ('nizhniy-novgorod', 'profi-nn-1', 'Нижний Новгород точка 1'),
    ('nizhniy-novgorod', 'profi-nn-2', 'Нижний Новгород точка 2'),
    -- Новосибирск
    ('novosibirsk', 'profi-nsk-1', 'Новосибирск точка 1'),
    ('novosibirsk', 'profi-nsk-2', 'Новосибирск точка 2'),
    -- Омск
    ('omsk', 'profi-omsk', 'Профи Омск'),
    -- Пермь
    ('perm', 'profi-perm-1', 'Пермь точка 1'),
    ('perm', 'profi-perm-2', 'Пермь точка 2'),
    -- Ростов-на-Дону
    ('rostov-na-donu', 'profi-rostov-1', 'Ростов точка 1'),
    ('rostov-na-donu', 'profi-rostov-2', 'Ростов точка 2'),
    -- Самара
    ('samara', 'profi-samara-1', 'Самара точка 1'),
    ('samara', 'profi-samara-2', 'Самара точка 2'),
    -- Саратов
    ('saratov', 'profi-saratov', 'Профи Саратов'),
    -- Тюмень
    ('tyumen', 'profi-tyumen', 'Профи Тюмень'),
    -- Уфа
    ('ufa', 'profi-ufa', 'Профи Уфа'),
    -- Челябинск
    ('chelyabinsk', 'profi-chelyabinsk', 'Профи Челябинск')
) AS v(city_code, outlet_code, outlet_name)
JOIN cities c ON c.code = v.city_code
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name;

-- ============================================
-- 4. ПРОВЕРКА
-- ============================================

-- Вывести все точки Профи
SELECT
    o.code AS outlet_code,
    o.name AS outlet_name,
    c.name AS city,
    s.name AS shop
FROM zip_outlets o
JOIN zip_shops s ON o.shop_id = s.id
JOIN zip_cities c ON o.city_id = c.id
WHERE s.code = 'profi'
ORDER BY c.name, o.name;
