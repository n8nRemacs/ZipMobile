-- Координация парсеров через PostgreSQL (режим Redis)
-- LISTEN/NOTIFY для pub/sub уведомлений

-- 1. Серверы парсинга
CREATE TABLE IF NOT EXISTS parser_servers (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,          -- 'server-a', 'server-b'
    ssh_command TEXT,                    -- команда запуска на этом сервере
    status TEXT DEFAULT 'idle',          -- idle / working / banned
    current_city TEXT,                   -- какой город сейчас парсит
    banned_until TIMESTAMP,              -- до какого времени забанен
    last_heartbeat TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. Очередь городов
CREATE TABLE IF NOT EXISTS parser_queue (
    id SERIAL PRIMARY KEY,
    city TEXT NOT NULL,
    city_id INT,                         -- ID из outlets
    priority INT DEFAULT 0,              -- выше = важнее
    status TEXT DEFAULT 'pending',       -- pending / in_progress / done / failed
    assigned_to TEXT,                    -- какой сервер взял (name из parser_servers)
    attempts INT DEFAULT 0,              -- сколько раз пытались
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. Прогресс парсинга (для продолжения после бана)
CREATE TABLE IF NOT EXISTS parser_progress (
    id SERIAL PRIMARY KEY,
    city TEXT NOT NULL,
    category_slug TEXT NOT NULL,
    current_page INT DEFAULT 0,
    total_pages INT,
    products_parsed INT DEFAULT 0,
    status TEXT DEFAULT 'pending',       -- pending / in_progress / done
    server_name TEXT,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(city, category_slug)
);

-- 4. Функция для взятия города из очереди (атомарно)
CREATE OR REPLACE FUNCTION take_city_from_queue(p_server_name TEXT)
RETURNS TABLE(city TEXT, city_id INT) AS $$
DECLARE
    v_city TEXT;
    v_city_id INT;
BEGIN
    -- Берём первый pending город с блокировкой
    SELECT pq.city, pq.city_id INTO v_city, v_city_id
    FROM parser_queue pq
    WHERE pq.status = 'pending'
    ORDER BY pq.priority DESC, pq.id ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;

    IF v_city IS NOT NULL THEN
        -- Помечаем как in_progress
        UPDATE parser_queue pq
        SET status = 'in_progress',
            assigned_to = p_server_name,
            started_at = NOW(),
            attempts = attempts + 1
        WHERE pq.city = v_city AND pq.status = 'pending';

        -- Обновляем статус сервера
        UPDATE parser_servers
        SET status = 'working',
            current_city = v_city,
            last_heartbeat = NOW()
        WHERE name = p_server_name;
    END IF;

    RETURN QUERY SELECT v_city, v_city_id;
END;
$$ LANGUAGE plpgsql;

-- 5. Функция при бане — уведомляет другие серверы
CREATE OR REPLACE FUNCTION on_server_banned(p_server_name TEXT, p_ban_minutes INT DEFAULT 18)
RETURNS VOID AS $$
BEGIN
    -- Обновляем статус сервера
    UPDATE parser_servers
    SET status = 'banned',
        banned_until = NOW() + (p_ban_minutes || ' minutes')::INTERVAL,
        last_heartbeat = NOW()
    WHERE name = p_server_name;

    -- Возвращаем город в очередь (если был)
    UPDATE parser_queue
    SET status = 'pending',
        assigned_to = NULL
    WHERE assigned_to = p_server_name AND status = 'in_progress';

    -- NOTIFY другим серверам
    PERFORM pg_notify('parser_events', json_build_object(
        'event', 'server_banned',
        'server', p_server_name,
        'banned_until', NOW() + (p_ban_minutes || ' minutes')::INTERVAL
    )::text);
END;
$$ LANGUAGE plpgsql;

-- 6. Функция для сохранения прогресса категории
CREATE OR REPLACE FUNCTION save_category_progress(
    p_city TEXT,
    p_category TEXT,
    p_page INT,
    p_total_pages INT,
    p_products INT,
    p_server TEXT
) RETURNS VOID AS $$
BEGIN
    INSERT INTO parser_progress (city, category_slug, current_page, total_pages, products_parsed, server_name, status, updated_at)
    VALUES (p_city, p_category, p_page, p_total_pages, p_products, p_server, 'in_progress', NOW())
    ON CONFLICT (city, category_slug) DO UPDATE SET
        current_page = p_page,
        total_pages = p_total_pages,
        products_parsed = parser_progress.products_parsed + p_products,
        server_name = p_server,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- 7. Получить прогресс для города (чтобы продолжить)
CREATE OR REPLACE FUNCTION get_city_progress(p_city TEXT)
RETURNS TABLE(category_slug TEXT, current_page INT, total_pages INT, status TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT pp.category_slug, pp.current_page, pp.total_pages, pp.status
    FROM parser_progress pp
    WHERE pp.city = p_city
    ORDER BY pp.category_slug;
END;
$$ LANGUAGE plpgsql;

-- Индексы
CREATE INDEX IF NOT EXISTS idx_parser_queue_status ON parser_queue(status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_parser_progress_city ON parser_progress(city);
CREATE INDEX IF NOT EXISTS idx_parser_servers_status ON parser_servers(status);

-- Вставляем серверы (настроить под свои)
-- INSERT INTO parser_servers (name, ssh_command) VALUES
--     ('server-a', 'ssh user@server-a "cd /path/to/parser && python parser.py --resume"'),
--     ('server-b', 'ssh user@server-b "cd /path/to/parser && python parser.py --resume"');
