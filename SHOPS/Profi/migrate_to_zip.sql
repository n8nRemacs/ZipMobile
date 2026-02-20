-- Миграция Profi в архитектуру zip_*

-- 1. Добавить магазин Профи в zip_shops (если не существует)
INSERT INTO zip_shops (code, name, website, shop_type, is_active)
VALUES ('profi', 'Профи', 'https://siriust.ru', 'wholesale', true)
ON CONFLICT (code) DO NOTHING;

-- 2. Добавить города (если не существуют)
INSERT INTO zip_cities (code, name, region_name) VALUES
('moskva', 'Москва', 'Москва'),
('spb', 'Санкт-Петербург', 'Санкт-Петербург'),
('adler', 'Адлер', 'Краснодарский край'),
('arkhangelsk', 'Архангельск', 'Архангельская область'),
('astrakhan', 'Астрахань', 'Астраханская область'),
('volgograd', 'Волгоград', 'Волгоградская область'),
('voronezh', 'Воронеж', 'Воронежская область'),
('ekaterinburg', 'Екатеринбург', 'Свердловская область'),
('izhevsk', 'Ижевск', 'Удмуртская Республика'),
('kazan', 'Казань', 'Республика Татарстан'),
('kaliningrad', 'Калининград', 'Калининградская область'),
('krasnodar', 'Краснодар', 'Краснодарский край'),
('krasnoyarsk', 'Красноярск', 'Красноярский край'),
('nizhniy_novgorod', 'Нижний Новгород', 'Нижегородская область'),
('novosibirsk', 'Новосибирск', 'Новосибирская область'),
('omsk', 'Омск', 'Омская область'),
('perm', 'Пермь', 'Пермский край'),
('rostov', 'Ростов-на-Дону', 'Ростовская область'),
('samara', 'Самара', 'Самарская область'),
('saratov', 'Саратов', 'Саратовская область'),
('tyumen', 'Тюмень', 'Тюменская область'),
('ufa', 'Уфа', 'Республика Башкортостан'),
('chelyabinsk', 'Челябинск', 'Челябинская область')
ON CONFLICT (code) DO NOTHING;

-- 3. Добавить торговые точки (outlets)
-- Сначала получаем ID магазина Профи
DO $$
DECLARE
    profi_shop_id INTEGER;
BEGIN
    SELECT id INTO profi_shop_id FROM zip_shops WHERE code = 'profi';

    -- Москва - Опт
    INSERT INTO zip_outlets (shop_id, city_id, code, name)
    SELECT profi_shop_id, c.id, 'profi-msk-opt', 'Отдел оптовых продаж'
    FROM zip_cities c WHERE c.code = 'moskva'
    ON CONFLICT (code) DO NOTHING;

    -- Москва - Савеловский
    INSERT INTO zip_outlets (shop_id, city_id, code, name)
    SELECT profi_shop_id, c.id, 'profi-msk-savelovo', 'Савеловский радиорынок'
    FROM zip_cities c WHERE c.code = 'moskva'
    ON CONFLICT (code) DO NOTHING;

    -- Москва - Митино
    INSERT INTO zip_outlets (shop_id, city_id, code, name)
    SELECT profi_shop_id, c.id, 'profi-msk-mitino', 'Митинский радиорынок'
    FROM zip_cities c WHERE c.code = 'moskva'
    ON CONFLICT (code) DO NOTHING;

    -- Москва - Южный
    INSERT INTO zip_outlets (shop_id, city_id, code, name)
    SELECT profi_shop_id, c.id, 'profi-msk-yuzhny', 'Радиокомплекс Южный'
    FROM zip_cities c WHERE c.code = 'moskva'
    ON CONFLICT (code) DO NOTHING;

    -- Региональные точки (по одной или две на город)
    -- Астрахань
    INSERT INTO zip_outlets (shop_id, city_id, code, name)
    SELECT profi_shop_id, c.id, 'profi-astrakhan', 'Профи Астрахань'
    FROM zip_cities c WHERE c.code = 'astrakhan'
    ON CONFLICT (code) DO NOTHING;

    -- И так далее для всех городов...
END $$;

-- Примечание: полный список outlets будет добавлен парсером автоматически
