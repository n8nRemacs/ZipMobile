-- ============================================
-- Profi: Таблица для СЫРЫХ данных (ЭТАП 1)
-- ============================================
-- Все данные из Excel БЕЗ нормализации
-- После обработки в n8n переносятся в profi_nomenclature

CREATE TABLE IF NOT EXISTS public.profi_nomenclature_all (
    id SERIAL PRIMARY KEY,

    -- Основные данные
    article VARCHAR(255) UNIQUE,              -- Артикул (уникальный)
    barcode VARCHAR(50),                      -- Штрих-код
    name TEXT NOT NULL,                       -- Название товара

    -- СЫРЫЕ данные (как есть из Excel по font-size)
    brand_raw TEXT,                           -- "1. ЗАПЧАСТИ ДЛЯ APPLE"
    model_raw TEXT,                           -- "ЗАПЧАСТИ ДЛЯ APPLE IPHONE"
    part_type_raw TEXT,                       -- "Дисплеи для iPhone 14"
    category_raw TEXT,                        -- Полная категория (для отладки)

    -- Метаданные парсинга
    city VARCHAR(100),                        -- Город
    shop VARCHAR(100),                        -- Название магазина
    outlet_code VARCHAR(50),                  -- Код точки продаж

    -- Цена (на момент парсинга)
    price NUMERIC(12,2),

    -- Timestamps
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),  -- Когда впервые появился
    updated_at TIMESTAMPTZ DEFAULT NOW(),     -- Последнее обновление

    -- Статус обработки
    processed BOOLEAN DEFAULT false,          -- Обработан ли в n8n
    processed_at TIMESTAMPTZ                  -- Когда обработан
);

-- Индексы для ускорения
CREATE INDEX IF NOT EXISTS idx_profi_nom_all_article ON public.profi_nomenclature_all(article);
CREATE INDEX IF NOT EXISTS idx_profi_nom_all_outlet ON public.profi_nomenclature_all(outlet_code);
CREATE INDEX IF NOT EXISTS idx_profi_nom_all_processed ON public.profi_nomenclature_all(processed) WHERE processed = false;
CREATE INDEX IF NOT EXISTS idx_profi_nom_all_updated ON public.profi_nomenclature_all(updated_at);

-- Полнотекстовый поиск
CREATE INDEX IF NOT EXISTS idx_profi_nom_all_name_gin ON public.profi_nomenclature_all USING gin(to_tsvector('russian', name));

-- Комментарии
COMMENT ON TABLE public.profi_nomenclature_all IS 'Profi - СЫРЫЕ данные из Excel (ЭТАП 1). После n8n нормализации переносятся в profi_nomenclature';
COMMENT ON COLUMN public.profi_nomenclature_all.brand_raw IS 'Сырой бренд из Excel (по font-size 11): "1. ЗАПЧАСТИ ДЛЯ APPLE"';
COMMENT ON COLUMN public.profi_nomenclature_all.model_raw IS 'Сырая модель из Excel (по font-size 10): "ЗАПЧАСТИ ДЛЯ APPLE IPHONE"';
COMMENT ON COLUMN public.profi_nomenclature_all.part_type_raw IS 'Сырой тип из Excel (по font-size 9): "Дисплеи для iPhone 14"';
COMMENT ON COLUMN public.profi_nomenclature_all.processed IS 'TRUE = уже обработан в n8n Upload.json';
