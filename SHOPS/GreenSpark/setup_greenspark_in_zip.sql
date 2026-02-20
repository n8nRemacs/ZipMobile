-- Setup GreenSpark в центральной БД zip_*
-- Выполнить один раз: psql -h localhost -p 5432 -U postgres -d postgres -f setup_greenspark_in_zip.sql

-- ============================================
-- 1. МАГАЗИН (zip_shops)
-- ============================================

INSERT INTO zip_shops (code, name, website, shop_type, company_name, parser_enabled, is_active)
VALUES (
    'greenspark',
    'GreenSpark',
    'https://greenspark.ru',
    'wholesale',
    'GreenSpark',
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
    ('abakan', 'Абакан', '', true),
    ('adler', 'Адлер', '', true),
    ('astrakhan', 'Астрахань', '', true),
    ('barnaul', 'Барнаул', '', true),
    ('belgorod', 'Белгород', '', true),
    ('bryansk', 'Брянск', '', true),
    ('vladikavkaz', 'Владикавказ', '', true),
    ('volgograd', 'Волгоград', '', true),
    ('volgodonsk', 'Волгодонск', '', true),
    ('vologda', 'Вологда', '', true),
    ('ekaterinburg', 'Екатеринбург', '', true),
    ('ivanovo', 'Иваново', '', true),
    ('irkutsk', 'Иркутск', '', true),
    ('yoshkar-ola', 'Йошкар-Ола', '', true),
    ('kazan', 'Казань', '', true),
    ('kaliningrad', 'Калининград', '', true),
    ('kamensk-shakhtinskiy', 'Каменск-Шахтинский', '', true),
    ('kirov', 'Киров', '', true),
    ('komsomolsk-na-amure', 'Комсомольск-на-Амуре', '', true),
    ('krasnodar', 'Краснодар', '', true),
    ('kursk', 'Курск', '', true),
    ('lesnoy', 'Лесной', '', true),
    ('lipetsk', 'Липецк', '', true),
    ('maykop', 'Майкоп', '', true),
    ('moskva', 'Москва', '', true),
    ('murmansk', 'Мурманск', '', true),
    ('naberezhnye-chelny', 'Набережные Челны', '', true),
    ('neftekamsk', 'Нефтекамск', '', true),
    ('novorossiysk', 'Новороссийск', '', true),
    ('noyabrsk', 'Ноябрьск', '', true),
    ('orenburg', 'Оренбург', '', true),
    ('orsk', 'Орск', '', true),
    ('penza', 'Пенза', '', true),
    ('perm', 'Пермь', '', true),
    ('podolsk', 'Подольск', '', true),
    ('pskov', 'Псков', '', true),
    ('rossosh', 'Россошь', '', true),
    ('rostov-na-donu', 'Ростов-на-Дону', '', true),
    ('rubtsovsk', 'Рубцовск', '', true),
    ('ryazan', 'Рязань', '', true),
    ('samara', 'Самара', '', true),
    ('sankt-peterburg', 'Санкт-Петербург', '', true),
    ('saransk', 'Саранск', '', true),
    ('saratov', 'Саратов', '', true),
    ('smolensk', 'Смоленск', '', true),
    ('sochi', 'Сочи', '', true),
    ('stavropol', 'Ставрополь', '', true),
    ('staryy-oskol', 'Старый Оскол', '', true),
    ('sterlitamak', 'Стерлитамак', '', true),
    ('tambov', 'Тамбов', '', true),
    ('tver', 'Тверь', '', true),
    ('tula', 'Тула', '', true),
    ('tyumen', 'Тюмень', '', true),
    ('ulan-ude', 'Улан-Удэ', '', true),
    ('ulyanovsk', 'Ульяновск', '', true),
    ('ufa', 'Уфа', '', true),
    ('ukhta', 'Ухта', '', true),
    ('cheboksary', 'Чебоксары', '', true),
    ('cherepovets', 'Череповец', '', true),
    ('yaroslavl', 'Ярославль', '', true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name;

-- ============================================
-- 3. ТОРГОВЫЕ ТОЧКИ (zip_outlets)
-- ============================================

WITH shop AS (
    SELECT id FROM zip_shops WHERE code = 'greenspark'
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
    ('abakan', 'greenspark-289687', 'GreenSpark Абакан', '{"set_city": 289687}'),
    ('adler', 'greenspark-289829', 'GreenSpark Адлер', '{"set_city": 289829}'),
    ('astrakhan', 'greenspark-289785', 'GreenSpark Астрахань', '{"set_city": 289785}'),
    ('barnaul', 'greenspark-289689', 'GreenSpark Барнаул', '{"set_city": 289689}'),
    ('belgorod', 'greenspark-289814', 'GreenSpark Белгород', '{"set_city": 289814}'),
    ('bryansk', 'greenspark-289717', 'GreenSpark Брянск', '{"set_city": 289717}'),
    ('vladikavkaz', 'greenspark-289724', 'GreenSpark Владикавказ', '{"set_city": 289724}'),
    ('volgograd', 'greenspark-289762', 'GreenSpark Волгоград', '{"set_city": 289762}'),
    ('volgodonsk', 'greenspark-289763', 'GreenSpark Волгодонск', '{"set_city": 289763}'),
    ('vologda', 'greenspark-289766', 'GreenSpark Вологда', '{"set_city": 289766}'),
    ('ekaterinburg', 'greenspark-290304', 'GreenSpark Екатеринбург', '{"set_city": 290304}'),
    ('ivanovo', 'greenspark-289873', 'GreenSpark Иваново', '{"set_city": 289873}'),
    ('irkutsk', 'greenspark-289916', 'GreenSpark Иркутск', '{"set_city": 289916}'),
    ('yoshkar-ola', 'greenspark-289966', 'GreenSpark Йошкар-Ола', '{"set_city": 289966}'),
    ('kazan', 'greenspark-289877', 'GreenSpark Казань', '{"set_city": 289877}'),
    ('kaliningrad', 'greenspark-289883', 'GreenSpark Калининград', '{"set_city": 289883}'),
    ('kamensk-shakhtinskiy', 'greenspark-289895', 'GreenSpark Каменск-Шахтинский', '{"set_city": 289895}'),
    ('kirov', 'greenspark-289923', 'GreenSpark Киров', '{"set_city": 289923}'),
    ('komsomolsk-na-amure', 'greenspark-289953', 'GreenSpark Комсомольск-на-Амуре', '{"set_city": 289953}'),
    ('krasnodar', 'greenspark-289912', 'GreenSpark Краснодар', '{"set_city": 289912}'),
    ('kursk', 'greenspark-289977', 'GreenSpark Курск', '{"set_city": 289977}'),
    ('lesnoy', 'greenspark-290002', 'GreenSpark Лесной', '{"set_city": 290002}'),
    ('lipetsk', 'greenspark-289936', 'GreenSpark Липецк', '{"set_city": 289936}'),
    ('maykop', 'greenspark-290024', 'GreenSpark Майкоп', '{"set_city": 290024}'),
    ('moskva', 'greenspark-290112', 'GreenSpark Москва', '{"set_city": 290112}'),
    ('murmansk', 'greenspark-290122', 'GreenSpark Мурманск', '{"set_city": 290122}'),
    ('naberezhnye-chelny', 'greenspark-290015', 'GreenSpark Набережные Челны', '{"set_city": 290015}'),
    ('neftekamsk', 'greenspark-290149', 'GreenSpark Нефтекамск', '{"set_city": 290149}'),
    ('novorossiysk', 'greenspark-290081', 'GreenSpark Новороссийск', '{"set_city": 290081}'),
    ('noyabrsk', 'greenspark-290117', 'GreenSpark Ноябрьск', '{"set_city": 290117}'),
    ('orenburg', 'greenspark-290044', 'GreenSpark Оренбург', '{"set_city": 290044}'),
    ('orsk', 'greenspark-290042', 'GreenSpark Орск', '{"set_city": 290042}'),
    ('penza', 'greenspark-290141', 'GreenSpark Пенза', '{"set_city": 290141}'),
    ('perm', 'greenspark-290137', 'GreenSpark Пермь', '{"set_city": 290137}'),
    ('podolsk', 'greenspark-290116', 'GreenSpark Подольск', '{"set_city": 290116}'),
    ('pskov', 'greenspark-290119', 'GreenSpark Псков', '{"set_city": 290119}'),
    ('rossosh', 'greenspark-289853', 'GreenSpark Россошь', '{"set_city": 289853}'),
    ('rostov-na-donu', 'greenspark-289855', 'GreenSpark Ростов-на-Дону', '{"set_city": 289855}'),
    ('rubtsovsk', 'greenspark-289857', 'GreenSpark Рубцовск', '{"set_city": 289857}'),
    ('ryazan', 'greenspark-289868', 'GreenSpark Рязань', '{"set_city": 289868}'),
    ('samara', 'greenspark-290168', 'GreenSpark Самара', '{"set_city": 290168}'),
    ('sankt-peterburg', 'greenspark-290170', 'GreenSpark Санкт-Петербург', '{"set_city": 290170}'),
    ('saransk', 'greenspark-290160', 'GreenSpark Саранск', '{"set_city": 290160}'),
    ('saratov', 'greenspark-290162', 'GreenSpark Саратов', '{"set_city": 290162}'),
    ('smolensk', 'greenspark-290193', 'GreenSpark Смоленск', '{"set_city": 290193}'),
    ('sochi', 'greenspark-290197', 'GreenSpark Сочи', '{"set_city": 290197}'),
    ('stavropol', 'greenspark-290198', 'GreenSpark Ставрополь', '{"set_city": 290198}'),
    ('staryy-oskol', 'greenspark-290203', 'GreenSpark Старый Оскол', '{"set_city": 290203}'),
    ('sterlitamak', 'greenspark-290210', 'GreenSpark Стерлитамак', '{"set_city": 290210}'),
    ('tambov', 'greenspark-290237', 'GreenSpark Тамбов', '{"set_city": 290237}'),
    ('tver', 'greenspark-290241', 'GreenSpark Тверь', '{"set_city": 290241}'),
    ('tula', 'greenspark-290279', 'GreenSpark Тула', '{"set_city": 290279}'),
    ('tyumen', 'greenspark-290289', 'GreenSpark Тюмень', '{"set_city": 290289}'),
    ('ulan-ude', 'greenspark-290254', 'GreenSpark Улан-Удэ', '{"set_city": 290254}'),
    ('ulyanovsk', 'greenspark-290260', 'GreenSpark Ульяновск', '{"set_city": 290260}'),
    ('ufa', 'greenspark-290277', 'GreenSpark Уфа', '{"set_city": 290277}'),
    ('ukhta', 'greenspark-290281', 'GreenSpark Ухта', '{"set_city": 290281}'),
    ('cheboksary', 'greenspark-290350', 'GreenSpark Чебоксары', '{"set_city": 290350}'),
    ('cherepovets', 'greenspark-290360', 'GreenSpark Череповец', '{"set_city": 290360}'),
    ('yaroslavl', 'greenspark-290382', 'GreenSpark Ярославль', '{"set_city": 290382}')
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
    o.api_config->>'set_city' AS set_city
FROM zip_outlets o
JOIN zip_shops s ON o.shop_id = s.id
JOIN zip_cities c ON o.city_id = c.id
WHERE s.code = 'greenspark'
ORDER BY c.name;
