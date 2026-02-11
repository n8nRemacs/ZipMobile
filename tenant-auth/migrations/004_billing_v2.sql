-- ============================================
-- 004_billing_v2.sql — Новая модель биллинга
-- Сервисы, планы, подписки, места, счётчики
-- ============================================

-- Каталог сервисов платформы
CREATE TABLE IF NOT EXISTS platform_services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    icon TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Тарифные планы для каждого сервиса
CREATE TABLE IF NOT EXISTS service_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_id UUID NOT NULL REFERENCES platform_services(id) ON DELETE CASCADE,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    price_monthly DECIMAL(10,2) DEFAULT 0,
    limits JSONB NOT NULL DEFAULT '{}',
    features JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(service_id, slug)
);

-- Подписки тенанта на сервисы
CREATE TABLE IF NOT EXISTS tenant_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    service_id UUID NOT NULL REFERENCES platform_services(id),
    plan_id UUID NOT NULL REFERENCES service_plans(id),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'expired', 'past_due')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    auto_renew BOOLEAN DEFAULT TRUE,
    cancelled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, service_id)
);

-- Пакеты мест (сотрудников)
CREATE TABLE IF NOT EXISTS seat_packages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    max_seats INT NOT NULL,
    price_monthly DECIMAL(10,2) DEFAULT 0,
    price_per_seat DECIMAL(10,2),
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Подписка тенанта на пакет мест
CREATE TABLE IF NOT EXISTS tenant_seat_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE UNIQUE,
    package_id UUID NOT NULL REFERENCES seat_packages(id),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'expired')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    auto_renew BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Дневные счётчики использования
CREATE TABLE IF NOT EXISTS usage_counters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    service_id UUID NOT NULL REFERENCES platform_services(id),
    counter_name TEXT NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    used INT NOT NULL DEFAULT 0,
    max_limit INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, service_id, counter_name, date)
);

-- История платежей (на будущее, пока пустая)
CREATE TABLE IF NOT EXISTS payment_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    amount DECIMAL(10,2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'RUB',
    description TEXT,
    payment_method TEXT,
    external_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_service_plans_service ON service_plans(service_id);
CREATE INDEX IF NOT EXISTS idx_tenant_subs_tenant ON tenant_subscriptions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_subs_service ON tenant_subscriptions(service_id);
CREATE INDEX IF NOT EXISTS idx_tenant_seat_subs_tenant ON tenant_seat_subscriptions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_usage_counters_tenant_date ON usage_counters(tenant_id, date);
CREATE INDEX IF NOT EXISTS idx_usage_counters_lookup ON usage_counters(tenant_id, service_id, counter_name, date);
CREATE INDEX IF NOT EXISTS idx_payment_history_tenant ON payment_history(tenant_id);
