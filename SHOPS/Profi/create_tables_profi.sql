-- Таблицы для парсера Profi с префиксом PROFI_
-- Создано на основе воркера pars_excel.json

-- Staging таблица для загрузки данных
CREATE TABLE IF NOT EXISTS public.PROFI_price_for_update (
    id SERIAL PRIMARY KEY,
    name TEXT,
    article TEXT,
    barcode TEXT,
    price_rub NUMERIC(12,2),
    note TEXT,
    brand_attr TEXT,
    model_attr TEXT,
    part_type_attr TEXT,
    seller TEXT
);

-- Основная таблица цен
CREATE TABLE IF NOT EXISTS public.PROFI_price (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fix TEXT,
    article TEXT,
    barcode TEXT,
    name TEXT,
    price_rub NUMERIC(12,2),
    note TEXT,
    brand_attr TEXT,
    model_attr TEXT,
    part_type_attr TEXT,
    seller TEXT,
    source_url TEXT,
    loaded_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для ускорения запросов
CREATE INDEX IF NOT EXISTS idx_profi_price_article ON public.PROFI_price(article);
CREATE INDEX IF NOT EXISTS idx_profi_price_seller ON public.PROFI_price(seller);
CREATE INDEX IF NOT EXISTS idx_profi_price_barcode ON public.PROFI_price(barcode);

CREATE INDEX IF NOT EXISTS idx_profi_pfu_article ON public.PROFI_price_for_update(article);
CREATE INDEX IF NOT EXISTS idx_profi_pfu_seller ON public.PROFI_price_for_update(seller);

-- Комментарии к таблицам
COMMENT ON TABLE public.PROFI_price_for_update IS 'Staging таблица для загрузки прайса Profi';
COMMENT ON TABLE public.PROFI_price IS 'Основная таблица цен Profi';
