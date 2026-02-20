-- Добавление колонок city и shop в таблицы Profi
-- Выполнить один раз перед запуском парсера с --all

-- ============================================
-- 1. Таблица для обновлений
-- ============================================
ALTER TABLE public.profi_price_for_update
ADD COLUMN IF NOT EXISTS city TEXT,
ADD COLUMN IF NOT EXISTS shop TEXT;

-- ============================================
-- 2. Основная таблица
-- ============================================
ALTER TABLE public.profi_price
ADD COLUMN IF NOT EXISTS city TEXT,
ADD COLUMN IF NOT EXISTS shop TEXT;

-- ============================================
-- 3. Индексы
-- ============================================
CREATE INDEX IF NOT EXISTS idx_profi_price_city ON public.profi_price(city);
CREATE INDEX IF NOT EXISTS idx_profi_price_shop ON public.profi_price(shop);
CREATE INDEX IF NOT EXISTS idx_profi_price_city_shop ON public.profi_price(city, shop);
CREATE INDEX IF NOT EXISTS idx_profi_price_article_city_shop ON public.profi_price(article, city, shop);

CREATE INDEX IF NOT EXISTS idx_profi_price_for_update_city ON public.profi_price_for_update(city);
CREATE INDEX IF NOT EXISTS idx_profi_price_for_update_shop ON public.profi_price_for_update(shop);

-- ============================================
-- 4. Комментарии
-- ============================================
COMMENT ON COLUMN public.profi_price.city IS 'Город магазина';
COMMENT ON COLUMN public.profi_price.shop IS 'Название магазина/точки';
COMMENT ON COLUMN public.profi_price_for_update.city IS 'Город магазина';
COMMENT ON COLUMN public.profi_price_for_update.shop IS 'Название магазина/точки';

-- ============================================
-- 5. Обновление старых записей (Астрахань по умолчанию)
-- ============================================
UPDATE public.profi_price
SET city = 'Астрахань', shop = 'Профи Астрахань'
WHERE city IS NULL;
