-- Setup TAGGSM в центральной БД zip_*
-- Выполнить один раз: psql -h localhost -p 5432 -U postgres -d postgres -f setup_taggsm_in_zip.sql

-- ============================================
-- 1. МАГАЗИН (zip_shops)
-- ============================================

INSERT INTO zip_shops (code, name, website, shop_type, company_name, parser_enabled, is_active)
VALUES (
    'taggsm',
    'TAGGSM',
    'https://taggsm.ru',
    'wholesale',
    'TAGGSM',
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
    ('adler', 'Адлер', '', true),
    ('armavir', 'Армавир', '', true),
    ('arkhangelsk', 'Архангельск', '', true),
    ('astrakhan', 'Астрахань', '', true),
    ('barnaul', 'Барнаул', '', true),
    ('belgorod', 'Белгород', '', true),
    ('birobidzhan', 'Биробиджан', '', true),
    ('blagoveschensk', 'Благовещенск', '', true),
    ('bryansk', 'Брянск', '', true),
    ('budennovsk', 'Буденновск', '', true),
    ('vladivostok', 'Владивосток', '', true),
    ('vladikavkaz', 'Владикавказ', '', true),
    ('volgograd', 'Волгоград', '', true),
    ('volgodonsk', 'Волгодонск', '', true),
    ('vologda', 'Вологда', '', true),
    ('voronezh', 'Воронеж', '', true),
    ('gelendzhik', 'Геленджик', '', true),
    ('groznyy', 'Грозный', '', true),
    ('dzhankoy', 'Джанкой', '', true),
    ('dzerzhinsk', 'Дзержинск', '', true),
    ('dimitrovgrad', 'Димитровград', '', true),
    ('donetsk-dnr', 'Донецк (ДНР)', '', true),
    ('donetsk-rost', 'Донецк (Рост.)', '', true),
    ('dubna', 'Дубна', '', true),
    ('evpatoriya', 'Евпатория', '', true),
    ('eysk', 'Ейск', '', true),
    ('ekaterinburg', 'Екатеринбург', '', true),
    ('essentuki', 'Ессентуки', '', true),
    ('zaporozhe', 'Запорожье', '', true),
    ('ivanovo', 'Иваново', '', true),
    ('izhevsk', 'Ижевск', '', true),
    ('irkutsk', 'Иркутск', '', true),
    ('kazan', 'Казань', '', true),
    ('kaliningrad', 'Калининград', '', true),
    ('kaluga', 'Калуга', '', true),
    ('kemerovo', 'Кемерово', '', true),
    ('kerch', 'Керчь', '', true),
    ('kislovodsk', 'Кисловодск', '', true),
    ('krasnodar', 'Краснодар', '', true),
    ('krasnoyarsk', 'Красноярск', '', true),
    ('kurgan', 'Курган', '', true),
    ('kursk', 'Курск', '', true),
    ('lipetsk', 'Липецк', '', true),
    ('lugansk', 'Луганск', '', true),
    ('mariupol', 'Мариуполь', '', true),
    ('makhachkala', 'Махачкала', '', true),
    ('melitopol', 'Мелитополь', '', true),
    ('moskva', 'Москва', '', true),
    ('murmansk', 'Мурманск', '', true),
    ('nefteyugansk', 'Нефтеюганск', '', true),
    ('nizhnevartovsk', 'Нижневартовск', '', true),
    ('nizhniy-novgorod', 'Нижний Новгород', '', true),
    ('novokuznetsk', 'Новокузнецк', '', true),
    ('novorossiysk', 'Новороссийск', '', true),
    ('omsk', 'Омск', '', true),
    ('orel', 'Орел', '', true),
    ('penza', 'Пенза', '', true),
    ('perm', 'Пермь', '', true),
    ('pyatigorsk', 'Пятигорск', '', true),
    ('rostov-na-donu', 'Ростов-на-Дону', '', true),
    ('ryazan', 'Рязань', '', true),
    ('samara', 'Самара', '', true),
    ('sankt-peterburg', 'Санкт-Петербург', '', true),
    ('saratov', 'Саратов', '', true),
    ('sevastopol', 'Севастополь', '', true),
    ('simferopol', 'Симферополь', '', true),
    ('smolensk', 'Смоленск', '', true),
    ('sochi', 'Сочи', '', true),
    ('stavropol', 'Ставрополь', '', true),
    ('surgut', 'Сургут', '', true),
    ('syzran', 'Сызрань', '', true),
    ('taganrog', 'Таганрог', '', true),
    ('tver', 'Тверь', '', true),
    ('tolyatti', 'Тольятти', '', true),
    ('tomsk', 'Томск', '', true),
    ('tula', 'Тула', '', true),
    ('tyumen', 'Тюмень', '', true),
    ('ulan-ude', 'Улан-Удэ', '', true),
    ('ulyanovsk', 'Ульяновск', '', true),
    ('ufa', 'Уфа', '', true),
    ('khabarovsk', 'Хабаровск', '', true),
    ('khanty-mansiysk', 'Ханты-Мансийск', '', true),
    ('kherson', 'Херсон', '', true),
    ('chelyabinsk', 'Челябинск', '', true),
    ('chita', 'Чита', '', true),
    ('yuzhno-sakhalinsk', 'Южно-Сахалинск', '', true),
    ('yalta', 'Ялта', '', true),
    ('yaroslavl', 'Ярославль', '', true)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name;

-- ============================================
-- 3. ТОРГОВЫЕ ТОЧКИ (zip_outlets)
-- ============================================

WITH shop AS (
    SELECT id FROM zip_shops WHERE code = 'taggsm'
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
    ('adler', 'taggsm-206220', 'TAGGSM Адлер', '{"fias_id": "206220"}'),
    ('armavir', 'taggsm-4168', 'TAGGSM Армавир', '{"fias_id": "4168"}'),
    ('arkhangelsk', 'taggsm-4929', 'TAGGSM Архангельск', '{"fias_id": "4929"}'),
    ('astrakhan', 'taggsm-4892', 'TAGGSM Астрахань', '{"fias_id": "4892"}'),
    ('barnaul', 'taggsm-4761', 'TAGGSM Барнаул', '{"fias_id": "4761"}'),
    ('belgorod', 'taggsm-2786', 'TAGGSM Белгород', '{"fias_id": "2786"}'),
    ('birobidzhan', 'taggsm-4115', 'TAGGSM Биробиджан', '{"fias_id": "4115"}'),
    ('blagoveschensk', 'taggsm-5753', 'TAGGSM Благовещенск', '{"fias_id": "5753"}'),
    ('bryansk', 'taggsm-3762', 'TAGGSM Брянск', '{"fias_id": "3762"}'),
    ('budennovsk', 'taggsm-4375', 'TAGGSM Буденновск', '{"fias_id": "4375"}'),
    ('vladivostok', 'taggsm-5033', 'TAGGSM Владивосток', '{"fias_id": "5033"}'),
    ('vladikavkaz', 'taggsm-3854', 'TAGGSM Владикавказ', '{"fias_id": "3854"}'),
    ('volgograd', 'taggsm-3734', 'TAGGSM Волгоград', '{"fias_id": "3734"}'),
    ('volgodonsk', 'taggsm-4637', 'TAGGSM Волгодонск', '{"fias_id": "4637"}'),
    ('vologda', 'taggsm-2281', 'TAGGSM Вологда', '{"fias_id": "2281"}'),
    ('voronezh', 'taggsm-3145', 'TAGGSM Воронеж', '{"fias_id": "3145"}'),
    ('gelendzhik', 'taggsm-3981', 'TAGGSM Геленджик', '{"fias_id": "3981"}'),
    ('groznyy', 'taggsm-3388', 'TAGGSM Грозный', '{"fias_id": "3388"}'),
    ('dzhankoy', 'taggsm-204261', 'TAGGSM Джанкой', '{"fias_id": "204261"}'),
    ('dzerzhinsk', 'taggsm-2304', 'TAGGSM Дзержинск', '{"fias_id": "2304"}'),
    ('dimitrovgrad', 'taggsm-7326', 'TAGGSM Димитровград', '{"fias_id": "7326"}'),
    ('donetsk-dnr', 'taggsm-400741', 'TAGGSM Донецк (ДНР)', '{"fias_id": "400741"}'),
    ('donetsk-rost', 'taggsm-2587', 'TAGGSM Донецк (Рост.)', '{"fias_id": "2587"}'),
    ('dubna', 'taggsm-2532', 'TAGGSM Дубна', '{"fias_id": "2532"}'),
    ('evpatoriya', 'taggsm-205739', 'TAGGSM Евпатория', '{"fias_id": "205739"}'),
    ('eysk', 'taggsm-4213', 'TAGGSM Ейск', '{"fias_id": "4213"}'),
    ('ekaterinburg', 'taggsm-3187', 'TAGGSM Екатеринбург', '{"fias_id": "3187"}'),
    ('essentuki', 'taggsm-3238', 'TAGGSM Ессентуки', '{"fias_id": "3238"}'),
    ('zaporozhe', 'taggsm-400760', 'TAGGSM Запорожье', '{"fias_id": "400760"}'),
    ('ivanovo', 'taggsm-4768', 'TAGGSM Иваново', '{"fias_id": "4768"}'),
    ('izhevsk', 'taggsm-3256', 'TAGGSM Ижевск', '{"fias_id": "3256"}'),
    ('irkutsk', 'taggsm-3278', 'TAGGSM Иркутск', '{"fias_id": "3278"}'),
    ('kazan', 'taggsm-4006', 'TAGGSM Казань', '{"fias_id": "4006"}'),
    ('kaliningrad', 'taggsm-3736', 'TAGGSM Калининград', '{"fias_id": "3736"}'),
    ('kaluga', 'taggsm-3541', 'TAGGSM Калуга', '{"fias_id": "3541"}'),
    ('kemerovo', 'taggsm-3224', 'TAGGSM Кемерово', '{"fias_id": "3224"}'),
    ('kerch', 'taggsm-205078', 'TAGGSM Керчь', '{"fias_id": "205078"}'),
    ('kislovodsk', 'taggsm-4753', 'TAGGSM Кисловодск', '{"fias_id": "4753"}'),
    ('krasnodar', 'taggsm-5723', 'TAGGSM Краснодар', '{"fias_id": "5723"}'),
    ('krasnoyarsk', 'taggsm-3753', 'TAGGSM Красноярск', '{"fias_id": "3753"}'),
    ('kurgan', 'taggsm-4202', 'TAGGSM Курган', '{"fias_id": "4202"}'),
    ('kursk', 'taggsm-7292', 'TAGGSM Курск', '{"fias_id": "7292"}'),
    ('lipetsk', 'taggsm-2749', 'TAGGSM Липецк', '{"fias_id": "2749"}'),
    ('lugansk', 'taggsm-400874', 'TAGGSM Луганск', '{"fias_id": "400874"}'),
    ('mariupol', 'taggsm-400894', 'TAGGSM Мариуполь', '{"fias_id": "400894"}'),
    ('makhachkala', 'taggsm-2844', 'TAGGSM Махачкала', '{"fias_id": "2844"}'),
    ('melitopol', 'taggsm-400900', 'TAGGSM Мелитополь', '{"fias_id": "400900"}'),
    ('moskva', 'taggsm-41', 'TAGGSM Москва', '{"fias_id": "41"}'),
    ('murmansk', 'taggsm-3314', 'TAGGSM Мурманск', '{"fias_id": "3314"}'),
    ('nefteyugansk', 'taggsm-6292', 'TAGGSM Нефтеюганск', '{"fias_id": "6292"}'),
    ('nizhnevartovsk', 'taggsm-6285', 'TAGGSM Нижневартовск', '{"fias_id": "6285"}'),
    ('nizhniy-novgorod', 'taggsm-2990', 'TAGGSM Нижний Новгород', '{"fias_id": "2990"}'),
    ('novokuznetsk', 'taggsm-3317', 'TAGGSM Новокузнецк', '{"fias_id": "3317"}'),
    ('novorossiysk', 'taggsm-4825', 'TAGGSM Новороссийск', '{"fias_id": "4825"}'),
    ('omsk', 'taggsm-3704', 'TAGGSM Омск', '{"fias_id": "3704"}'),
    ('orel', 'taggsm-5221', 'TAGGSM Орел', '{"fias_id": "5221"}'),
    ('penza', 'taggsm-6123', 'TAGGSM Пенза', '{"fias_id": "6123"}'),
    ('perm', 'taggsm-4131', 'TAGGSM Пермь', '{"fias_id": "4131"}'),
    ('pyatigorsk', 'taggsm-2630', 'TAGGSM Пятигорск', '{"fias_id": "2630"}'),
    ('rostov-na-donu', 'taggsm-4187', 'TAGGSM Ростов-на-Дону', '{"fias_id": "4187"}'),
    ('ryazan', 'taggsm-4682', 'TAGGSM Рязань', '{"fias_id": "4682"}'),
    ('samara', 'taggsm-2782', 'TAGGSM Самара', '{"fias_id": "2782"}'),
    ('sankt-peterburg', 'taggsm-86', 'TAGGSM Санкт-Петербург', '{"fias_id": "86"}'),
    ('saratov', 'taggsm-3737', 'TAGGSM Саратов', '{"fias_id": "3737"}'),
    ('sevastopol', 'taggsm-203915', 'TAGGSM Севастополь', '{"fias_id": "203915"}'),
    ('simferopol', 'taggsm-205105', 'TAGGSM Симферополь', '{"fias_id": "205105"}'),
    ('smolensk', 'taggsm-3385', 'TAGGSM Смоленск', '{"fias_id": "3385"}'),
    ('sochi', 'taggsm-2877', 'TAGGSM Сочи', '{"fias_id": "2877"}'),
    ('stavropol', 'taggsm-4986', 'TAGGSM Ставрополь', '{"fias_id": "4986"}'),
    ('surgut', 'taggsm-6980', 'TAGGSM Сургут', '{"fias_id": "6980"}'),
    ('syzran', 'taggsm-4357', 'TAGGSM Сызрань', '{"fias_id": "4357"}'),
    ('taganrog', 'taggsm-5003', 'TAGGSM Таганрог', '{"fias_id": "5003"}'),
    ('tver', 'taggsm-4333', 'TAGGSM Тверь', '{"fias_id": "4333"}'),
    ('tolyatti', 'taggsm-2857', 'TAGGSM Тольятти', '{"fias_id": "2857"}'),
    ('tomsk', 'taggsm-3053', 'TAGGSM Томск', '{"fias_id": "3053"}'),
    ('tula', 'taggsm-4145', 'TAGGSM Тула', '{"fias_id": "4145"}'),
    ('tyumen', 'taggsm-6115', 'TAGGSM Тюмень', '{"fias_id": "6115"}'),
    ('ulan-ude', 'taggsm-4186', 'TAGGSM Улан-Удэ', '{"fias_id": "4186"}'),
    ('ulyanovsk', 'taggsm-4521', 'TAGGSM Ульяновск', '{"fias_id": "4521"}'),
    ('ufa', 'taggsm-6125', 'TAGGSM Уфа', '{"fias_id": "6125"}'),
    ('khabarovsk', 'taggsm-2638', 'TAGGSM Хабаровск', '{"fias_id": "2638"}'),
    ('khanty-mansiysk', 'taggsm-6804', 'TAGGSM Ханты-Мансийск', '{"fias_id": "6804"}'),
    ('kherson', 'taggsm-401107', 'TAGGSM Херсон', '{"fias_id": "401107"}'),
    ('chelyabinsk', 'taggsm-4778', 'TAGGSM Челябинск', '{"fias_id": "4778"}'),
    ('chita', 'taggsm-3218', 'TAGGSM Чита', '{"fias_id": "3218"}'),
    ('yuzhno-sakhalinsk', 'taggsm-2730', 'TAGGSM Южно-Сахалинск', '{"fias_id": "2730"}'),
    ('yalta', 'taggsm-205310', 'TAGGSM Ялта', '{"fias_id": "205310"}'),
    ('yaroslavl', 'taggsm-4119', 'TAGGSM Ярославль', '{"fias_id": "4119"}')
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
    o.api_config->>'fias_id' AS fias_id
FROM zip_outlets o
JOIN zip_shops s ON o.shop_id = s.id
JOIN zip_cities c ON o.city_id = c.id
WHERE s.code = 'taggsm'
ORDER BY c.name;
