-- ============================================
-- 003_telegram_auth.sql — Поддержка Telegram-авторизации
-- ============================================

-- Новые поля в tenant_users
ALTER TABLE tenant_users
    ADD COLUMN IF NOT EXISTS available_channels TEXT[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS preferred_channel TEXT,
    ADD COLUMN IF NOT EXISTS telegram_chat_id BIGINT UNIQUE,
    ADD COLUMN IF NOT EXISTS telegram_username TEXT,
    ADD COLUMN IF NOT EXISTS telegram_phone TEXT,
    ADD COLUMN IF NOT EXISTS telegram_first_name TEXT,
    ADD COLUMN IF NOT EXISTS telegram_last_name TEXT;

-- Новые поля в tenants (данные сервисного центра)
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS company_name TEXT,
    ADD COLUMN IF NOT EXISTS city TEXT,
    ADD COLUMN IF NOT EXISTS address TEXT;

-- Индекс для быстрого поиска по chat_id (автологин)
CREATE INDEX IF NOT EXISTS idx_tenant_users_tg_chat ON tenant_users(telegram_chat_id);
