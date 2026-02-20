-- Таблица конфигурации парсеров для real-time парсинга
-- Хранит правила извлечения данных для каждого магазина

CREATE TABLE IF NOT EXISTS shop_parser_configs (
    id SERIAL PRIMARY KEY,
    shop_code VARCHAR(50) NOT NULL UNIQUE,  -- 'greenspark', '05gsm', 'taggsm'

    -- Определение магазина
    domain_patterns TEXT[] NOT NULL,         -- ['green-spark.ru', 'greenspark.ru']

    -- Тип парсинга
    parser_type VARCHAR(20) NOT NULL,        -- 'api_json', 'html', 'api_xml'

    -- Конфигурация API (для parser_type = 'api_json')
    api_config JSONB DEFAULT '{}',
    -- {
    --   "base_url": "https://green-spark.ru",
    --   "detail_endpoint": "/local/api/catalog/detail/",
    --   "url_to_path_regex": "/catalog/(.+?)(?:\\.html)?/?$",
    --   "path_param_format": "path[]={part}",
    --   "headers": {"Accept": "application/json"}
    -- }

    -- JSON paths для извлечения данных (для API)
    json_paths JSONB DEFAULT '{}',
    -- {
    --   "price": "product.prices[?(@.name=='Розница')].price",
    --   "price_wholesale": "product.prices[?(@.name=='Грин 5')].price",
    --   "stock": "product.quantity",
    --   "article": "product.article",
    --   "name": "product.name",
    --   "in_stock_values": ["many", "few", "one"]  -- значения = в наличии
    -- }

    -- CSS селекторы для HTML парсинга
    html_selectors JSONB DEFAULT '{}',
    -- {
    --   "price": ".product-price .value",
    --   "price_wholesale": ".wholesale-price",
    --   "stock": ".stock-status",
    --   "article": ".product-sku",
    --   "in_stock_class": "in-stock",
    --   "out_of_stock_text": ["нет в наличии", "под заказ"]
    -- }

    -- Regex паттерны (альтернатива селекторам)
    regex_patterns JSONB DEFAULT '{}',
    -- {
    --   "price": "Цена[:\\s]*(\\d+[\\s\\d]*)",
    --   "article": "Артикул[:\\s]*([A-Z]{2,3}-\\d+)"
    -- }

    -- Настройки запросов
    request_config JSONB DEFAULT '{}',
    -- {
    --   "delay": 1.0,
    --   "timeout": 30,
    --   "cookies_required": true,
    --   "cookies_source": "file:cookies.json" или "db:shop_cookies"
    --   "user_agent": "Mozilla/5.0...",
    --   "headers": {}
    -- }

    -- Трансформация данных
    transformers JSONB DEFAULT '{}',
    -- {
    --   "price": "float",  -- тип данных
    --   "price_multiplier": 1.0,  -- множитель
    --   "stock_mapping": {"many": 5, "few": 2, "one": 1, "none": 0}
    -- }

    -- Метаданные
    is_active BOOLEAN DEFAULT true,
    last_tested_at TIMESTAMP,
    test_url TEXT,  -- URL для тестирования конфигурации
    notes TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_parser_configs_shop ON shop_parser_configs(shop_code);
CREATE INDEX IF NOT EXISTS idx_parser_configs_active ON shop_parser_configs(is_active);

-- Таблица для хранения cookies (опционально)
CREATE TABLE IF NOT EXISTS shop_cookies (
    id SERIAL PRIMARY KEY,
    shop_code VARCHAR(50) NOT NULL REFERENCES shop_parser_configs(shop_code),
    cookies JSONB NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Лог запросов real-time парсера
CREATE TABLE IF NOT EXISTS parser_request_log (
    id SERIAL PRIMARY KEY,
    shop_code VARCHAR(50),
    url TEXT,
    success BOOLEAN,
    price NUMERIC(12,2),
    in_stock BOOLEAN,
    response_time_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_parser_log_created ON parser_request_log(created_at);
CREATE INDEX IF NOT EXISTS idx_parser_log_shop ON parser_request_log(shop_code);

-- Пример конфигурации для GreenSpark
INSERT INTO shop_parser_configs (shop_code, domain_patterns, parser_type, api_config, json_paths, request_config)
VALUES (
    'greenspark',
    ARRAY['green-spark.ru', 'greenspark.ru'],
    'api_json',
    '{
        "base_url": "https://green-spark.ru",
        "detail_endpoint": "/local/api/catalog/detail/",
        "url_to_path_regex": "/catalog/(.+?)(?:\\.html)?/?$",
        "path_param_format": "path[]={part}",
        "path_separator": "&"
    }'::jsonb,
    '{
        "price": "product.prices[0].price",
        "price_path_filter": {"field": "name", "value": "Розница"},
        "stock": "product.quantity",
        "article": "product.article",
        "name": "product.name",
        "in_stock_check": "not_in",
        "out_of_stock_values": ["none", "", null]
    }'::jsonb,
    '{
        "delay": 1.0,
        "timeout": 30,
        "cookies_required": true,
        "cookies_source": "file:cookies.json"
    }'::jsonb
) ON CONFLICT (shop_code) DO UPDATE SET
    domain_patterns = EXCLUDED.domain_patterns,
    api_config = EXCLUDED.api_config,
    json_paths = EXCLUDED.json_paths,
    request_config = EXCLUDED.request_config,
    updated_at = NOW();

-- Пример конфигурации для 05GSM (HTML парсинг)
INSERT INTO shop_parser_configs (shop_code, domain_patterns, parser_type, html_selectors, request_config)
VALUES (
    '05gsm',
    ARRAY['05gsm.ru'],
    'html',
    '{
        "price": ".product-detail-price .price-value",
        "stock": ".product-availability",
        "article": ".product-article span",
        "in_stock_text": ["в наличии", "есть"],
        "out_of_stock_text": ["нет в наличии", "под заказ", "ожидается"]
    }'::jsonb,
    '{
        "delay": 1.5,
        "timeout": 30,
        "cookies_required": false
    }'::jsonb
) ON CONFLICT (shop_code) DO UPDATE SET
    domain_patterns = EXCLUDED.domain_patterns,
    html_selectors = EXCLUDED.html_selectors,
    request_config = EXCLUDED.request_config,
    updated_at = NOW();
