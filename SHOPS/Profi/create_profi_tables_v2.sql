-- ============================================
-- Profi: Изолированные таблицы по структуре zip_*
-- ============================================

-- ============================================
-- 1. НОМЕНКЛАТУРА (уникальные товары)
-- ============================================
CREATE TABLE IF NOT EXISTS public.profi_nomenclature (
    id SERIAL PRIMARY KEY,
    article VARCHAR(100) NOT NULL,           -- Артикул (уникальный ключ)
    barcode VARCHAR(50),                      -- Штрихкод
    name TEXT NOT NULL,                       -- Название товара

    -- Классификация
    brand VARCHAR(100),                       -- Бренд (Apple, Samsung, etc.)
    device_type VARCHAR(50),                  -- Тип устройства (Смартфон, Планшет)
    model VARCHAR(200),                       -- Модель (iPhone 15 Pro Max)
    part_type VARCHAR(100),                   -- Тип запчасти (Дисплей, АКБ)

    -- Исходные данные из прайса
    brand_raw VARCHAR(200),                   -- Оригинальный brand_attr
    model_raw VARCHAR(200),                   -- Оригинальный model_attr
    part_type_raw VARCHAR(200),               -- Оригинальный part_type_attr

    -- Метаданные
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),  -- Когда впервые появился
    updated_at TIMESTAMPTZ DEFAULT NOW(),     -- Последнее обновление

    CONSTRAINT profi_nomenclature_article_unique UNIQUE (article)
);

-- Индексы для номенклатуры
CREATE INDEX IF NOT EXISTS idx_profi_nom_brand ON public.profi_nomenclature(brand);
CREATE INDEX IF NOT EXISTS idx_profi_nom_model ON public.profi_nomenclature(model);
CREATE INDEX IF NOT EXISTS idx_profi_nom_part_type ON public.profi_nomenclature(part_type);
CREATE INDEX IF NOT EXISTS idx_profi_nom_name_gin ON public.profi_nomenclature USING gin(to_tsvector('russian', name));

-- ============================================
-- 2. ЦЕНЫ (по точкам, текущие)
-- ============================================
CREATE TABLE IF NOT EXISTS public.profi_prices (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER NOT NULL REFERENCES public.profi_nomenclature(id) ON DELETE CASCADE,
    outlet_code VARCHAR(50) NOT NULL,         -- Код точки (profi-msk-savelovo)

    -- Цена и наличие
    price NUMERIC(12,2),                      -- Цена
    -- Метаданные
    loaded_at TIMESTAMPTZ DEFAULT NOW(),      -- Когда загружено

    CONSTRAINT profi_prices_nom_outlet_unique UNIQUE (nomenclature_id, outlet_code)
);

-- Индексы для цен
CREATE INDEX IF NOT EXISTS idx_profi_prices_outlet ON public.profi_prices(outlet_code);
CREATE INDEX IF NOT EXISTS idx_profi_prices_nom ON public.profi_prices(nomenclature_id);

-- ============================================
-- 3. ИСТОРИЯ ЦЕН (для отслеживания изменений)
-- ============================================
CREATE TABLE IF NOT EXISTS public.profi_price_history (
    id SERIAL PRIMARY KEY,
    nomenclature_id INTEGER NOT NULL REFERENCES public.profi_nomenclature(id) ON DELETE CASCADE,
    outlet_code VARCHAR(50) NOT NULL,

    price NUMERIC(12,2),

    recorded_at TIMESTAMPTZ DEFAULT NOW()     -- Когда записано
);

-- Индексы для истории
CREATE INDEX IF NOT EXISTS idx_profi_history_nom ON public.profi_price_history(nomenclature_id);
CREATE INDEX IF NOT EXISTS idx_profi_history_outlet ON public.profi_price_history(outlet_code);
CREATE INDEX IF NOT EXISTS idx_profi_history_date ON public.profi_price_history(recorded_at);

-- ============================================
-- 4. STAGING TABLE (для загрузки)
-- ============================================
-- profi_price_for_update уже существует, оставляем как есть

-- ============================================
-- 5. VIEW: Цены с номенклатурой
-- ============================================
CREATE OR REPLACE VIEW public.profi_prices_view AS
SELECT
    n.id AS nomenclature_id,
    n.article,
    n.barcode,
    n.name,
    n.brand,
    n.model,
    n.part_type,
    p.outlet_code,
    o.name AS outlet_name,
    c.name AS city,
    p.price,
    p.loaded_at
FROM public.profi_nomenclature n
JOIN public.profi_prices p ON p.nomenclature_id = n.id
LEFT JOIN public.zip_outlets o ON o.code = p.outlet_code
LEFT JOIN public.zip_cities c ON c.id = o.city_id;

-- ============================================
-- 6. КОММЕНТАРИИ
-- ============================================
COMMENT ON TABLE public.profi_nomenclature IS 'Номенклатура Profi - уникальные товары';
COMMENT ON TABLE public.profi_prices IS 'Текущие цены Profi по торговым точкам';
COMMENT ON TABLE public.profi_price_history IS 'История изменений цен Profi';

COMMENT ON COLUMN public.profi_nomenclature.article IS 'Уникальный артикул товара';
COMMENT ON COLUMN public.profi_nomenclature.brand_raw IS 'Оригинальное значение brand_attr из прайса';
COMMENT ON COLUMN public.profi_prices.outlet_code IS 'Код торговой точки (связь с zip_outlets)';
