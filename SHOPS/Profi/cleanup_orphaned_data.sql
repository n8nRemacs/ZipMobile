-- ============================================
-- Очистка устаревших данных в Profi
-- ============================================
-- Удаляет цены и наличие по удалённой номенклатуре

-- 1. Удаляем цены для товаров, которых нет в nomenclature
DELETE FROM profi_current_prices
WHERE nomenclature_id NOT IN (
    SELECT id FROM profi_nomenclature
);

-- 2. Удаляем историю цен для удалённых товаров
DELETE FROM profi_price_history
WHERE nomenclature_id NOT IN (
    SELECT id FROM profi_nomenclature
);

-- 3. Статистика очистки
SELECT
    'profi_current_prices' as table_name,
    COUNT(*) as remaining_rows
FROM profi_current_prices

UNION ALL

SELECT
    'profi_price_history' as table_name,
    COUNT(*) as remaining_rows
FROM profi_price_history

UNION ALL

SELECT
    'profi_nomenclature' as table_name,
    COUNT(*) as total_products
FROM profi_nomenclature;
