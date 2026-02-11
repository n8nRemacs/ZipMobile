# ТЗ-3: Миграция биллинга — сервисы, планы, подписки, места

## Контекст
Проект ZipMobile/. Работают: tenant-auth (8090), frontend-miniapp (3001), frontend-admin (3000).
Текущий биллинг: таблица billing_plans с 3 захардкоженными планами (free/starter/pro), поле tenants.billing_plan_id.
Нужно: перейти на модель "каждый сервис — отдельный продукт со своими планами" + пакеты мест для сотрудников.

## Параметры БД
```
DATABASE_URL=postgresql://postgres.dskhyumhxgbzmuefmrax:Mi31415926pSss!@aws-1-eu-west-1.pooler.supabase.com:5432/postgres
```

---

## Новая модель биллинга

### Принцип
- Каждый сервис платформы (поиск запчастей, мессенджер, API) — отдельный продукт
- У каждого сервиса свои тарифные планы (free/standard/pro)
- Тенант подписывается на каждый сервис независимо
- Места (сотрудники) — отдельная подписка
- Лимиты — дневные (сбрасываются в 00:00 GMT+3)
- Оплата — помесячно (позже скидки за квартал/год)

### Тарифная сетка

**Поиск запчастей (parts_search):**

| План | Цена | Текст запросов/день | Голос запросов/день |
|------|------|--------------------|--------------------|
| free | 0₽ | 5 | 0 |
| standard | 290₽/мес | безлимит | 3 |
| pro | 590₽/мес | безлимит | 30 |

**Авито Мессенджер (avito_messenger):**

| План | Цена | Аккаунты | Сообщения/день |
|------|------|----------|---------------|
| free | 0₽ | 1 | 50 |
| standard | 990₽/мес | 3 | безлимит |
| pro | 2990₽/мес | 10 | безлимит |

**API доступ (api_access):**

| План | Цена | Ключи | Запросы/день |
|------|------|-------|-------------|
| free | 0₽ | 1 | 100 |
| starter | 490₽/мес | 3 | 1000 |
| pro | 1490₽/мес | 10 | безлимит |

**Пакеты мест (seats):**

| Пакет | Всего мест | Цена | За место |
|-------|-----------|------|----------|
| free | 1 (owner) | 0₽ | — |
| seat_1 | 2 | 190₽/мес | 190₽ |
| seat_3 | 4 | 390₽/мес | 130₽ |
| seat_5 | 6 | 590₽/мес | 118₽ |
| seat_10 | 11 | 990₽/мес | 99₽ |

---

## Шаг 1: SQL-миграция

Создать файл `tenant-auth/migrations/004_billing_v2.sql`:

```sql
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
```

Создать файл `tenant-auth/migrations/005_billing_v2_seed.sql`:

```sql
-- ============================================
-- 005_billing_v2_seed.sql — Начальные данные биллинга v2
-- ============================================

-- === Сервисы ===

INSERT INTO platform_services (id, slug, name, description, icon, sort_order) VALUES
    ('b0000000-0000-0000-0000-000000000001', 'parts_search', 'Поиск запчастей', 'Поиск запчастей по лучшим ценам от поставщиков. Текстовый и голосовой поиск.', '🔍', 1),
    ('b0000000-0000-0000-0000-000000000002', 'avito_messenger', 'Авито Мессенджер', 'Управление сообщениями Avito. Омниканальный мессенджер.', '💬', 2),
    ('b0000000-0000-0000-0000-000000000003', 'api_access', 'API доступ', 'Программный доступ к платформе через API-ключи.', '🔑', 3)
ON CONFLICT (slug) DO NOTHING;

-- === Планы: Поиск запчастей ===

INSERT INTO service_plans (id, service_id, slug, name, price_monthly, limits, features, sort_order) VALUES
    ('c0000000-0000-0000-0001-000000000001',
     'b0000000-0000-0000-0000-000000000001',
     'free', 'Free', 0,
     '{"text_queries_per_day": 5, "voice_queries_per_day": 0}',
     '{"description": "5 текстовых запросов в день"}',
     1),
    ('c0000000-0000-0000-0001-000000000002',
     'b0000000-0000-0000-0000-000000000001',
     'standard', 'Standard', 290,
     '{"text_queries_per_day": -1, "voice_queries_per_day": 3}',
     '{"description": "Безлимит текстовых + 3 голосовых в день"}',
     2),
    ('c0000000-0000-0000-0001-000000000003',
     'b0000000-0000-0000-0000-000000000001',
     'pro', 'Pro', 590,
     '{"text_queries_per_day": -1, "voice_queries_per_day": 30}',
     '{"description": "Безлимит текстовых + 30 голосовых в день"}',
     3)
ON CONFLICT (service_id, slug) DO NOTHING;

-- === Планы: Авито Мессенджер ===

INSERT INTO service_plans (id, service_id, slug, name, price_monthly, limits, features, sort_order) VALUES
    ('c0000000-0000-0000-0002-000000000001',
     'b0000000-0000-0000-0000-000000000002',
     'free', 'Free', 0,
     '{"accounts": 1, "messages_per_day": 50}',
     '{"description": "1 аккаунт, 50 сообщений в день"}',
     1),
    ('c0000000-0000-0000-0002-000000000002',
     'b0000000-0000-0000-0000-000000000002',
     'standard', 'Standard', 990,
     '{"accounts": 3, "messages_per_day": -1}',
     '{"description": "3 аккаунта, безлимит сообщений"}',
     2),
    ('c0000000-0000-0000-0002-000000000003',
     'b0000000-0000-0000-0000-000000000002',
     'pro', 'Pro', 2990,
     '{"accounts": 10, "messages_per_day": -1}',
     '{"description": "10 аккаунтов, безлимит сообщений"}',
     3)
ON CONFLICT (service_id, slug) DO NOTHING;

-- === Планы: API доступ ===

INSERT INTO service_plans (id, service_id, slug, name, price_monthly, limits, features, sort_order) VALUES
    ('c0000000-0000-0000-0003-000000000001',
     'b0000000-0000-0000-0000-000000000003',
     'free', 'Free', 0,
     '{"api_keys": 1, "requests_per_day": 100}',
     '{"description": "1 ключ, 100 запросов в день"}',
     1),
    ('c0000000-0000-0000-0003-000000000002',
     'b0000000-0000-0000-0000-000000000003',
     'starter', 'Starter', 490,
     '{"api_keys": 3, "requests_per_day": 1000}',
     '{"description": "3 ключа, 1000 запросов в день"}',
     2),
    ('c0000000-0000-0000-0003-000000000003',
     'b0000000-0000-0000-0000-000000000003',
     'pro', 'Pro', 1490,
     '{"api_keys": 10, "requests_per_day": -1}',
     '{"description": "10 ключей, безлимит запросов"}',
     3)
ON CONFLICT (service_id, slug) DO NOTHING;

-- === Пакеты мест ===

INSERT INTO seat_packages (id, slug, name, max_seats, price_monthly, price_per_seat, sort_order) VALUES
    ('d0000000-0000-0000-0000-000000000001', 'free', 'Бесплатно', 1, 0, 0, 1),
    ('d0000000-0000-0000-0000-000000000002', 'seat_1', '+1 место', 2, 190, 190, 2),
    ('d0000000-0000-0000-0000-000000000003', 'seat_3', 'Пакет 3', 4, 390, 130, 3),
    ('d0000000-0000-0000-0000-000000000004', 'seat_5', 'Пакет 5', 6, 590, 118, 4),
    ('d0000000-0000-0000-0000-000000000005', 'seat_10', 'Пакет 10', 11, 990, 99, 5)
ON CONFLICT (slug) DO NOTHING;

-- === Автоматическая подписка на free-планы при регистрации ===
-- Это будет делаться в коде при создании тенанта.
-- Здесь только seed-данные.
```

Выполнить миграции:
```bash
cd tenant-auth
psql "postgresql://postgres.dskhyumhxgbzmuefmrax:Mi31415926pSss!@aws-1-eu-west-1.pooler.supabase.com:5432/postgres" -f migrations/004_billing_v2.sql
psql "postgresql://postgres.dskhyumhxgbzmuefmrax:Mi31415926pSss!@aws-1-eu-west-1.pooler.supabase.com:5432/postgres" -f migrations/005_billing_v2_seed.sql
```

Проверить:
```sql
SELECT s.slug, sp.slug, sp.price_monthly, sp.limits
FROM service_plans sp
JOIN platform_services s ON s.id = sp.service_id
ORDER BY s.sort_order, sp.sort_order;
```

---

## Шаг 2: Сервис биллинга v2

Создать `src/services/billing_v2_service.py`:

```python
# Новый сервис биллинга. Старый billing_service.py НЕ удалять (обратная совместимость).

# Функции:

# get_platform_services() -> list[dict]
#   Возвращает все активные сервисы платформы

# get_service_plans(service_slug: str) -> list[dict]
#   Возвращает планы для конкретного сервиса

# get_seat_packages() -> list[dict]
#   Возвращает все пакеты мест

# get_tenant_subscriptions(tenant_id: str) -> list[dict]
#   Возвращает все подписки тенанта (сервисы + план + статус)

# get_tenant_seat_info(tenant_id: str) -> dict
#   Возвращает пакет мест тенанта + сколько занято

# create_free_subscriptions(tenant_id: str)
#   Создаёт подписки на free-план для ВСЕХ сервисов + free пакет мест
#   Вызывается при регистрации нового тенанта

# check_limit(tenant_id: str, service_slug: str, counter_name: str) -> dict
#   Проверяет дневной лимит: {"allowed": bool, "used": int, "limit": int}
#   Если limit = -1 (безлимит) → always allowed

# increment_usage(tenant_id: str, service_slug: str, counter_name: str) -> dict
#   Увеличивает счётчик на 1, возвращает {"used": int, "limit": int}
#   Создаёт запись на текущую дату если нет (upsert)

# get_tenant_billing_summary(tenant_id: str) -> dict
#   Возвращает сводку: подписки, места, общая сумма/мес
```

### Лимиты: -1 = безлимит
В JSONB limits значение -1 означает безлимит. При проверке:
```python
if limit == -1:
    return {"allowed": True, "used": used, "limit": "unlimited"}
```

---

## Шаг 3: Автоматические free-подписки при регистрации

В `src/services/telegram_auth_service.py` (функция register_via_telegram):
После создания tenant + user → вызвать `billing_v2_service.create_free_subscriptions(tenant_id)`.

Это создаст:
- Подписку parts_search → free
- Подписку avito_messenger → free
- Подписку api_access → free
- Подписку seat → free (1 место)

Аналогично в `src/services/user_service.py` (функция create_tenant_and_user) для OTP-регистрации.

---

## Шаг 4: Новые эндпоинты

### Роутер: `src/routers/billing_v2.py`

```
GET /auth/v1/billing/v2/services
  → Список сервисов платформы с их планами
  → Публичный (без JWT)

GET /auth/v1/billing/v2/seats
  → Список пакетов мест с ценами
  → Публичный (без JWT)

GET /auth/v1/billing/v2/my
  → Сводка подписок текущего тенанта (сервисы + места + сумма)
  → Требует JWT

GET /auth/v1/billing/v2/usage
  → Текущее использование за сегодня по всем сервисам
  → Требует JWT

POST /auth/v1/billing/v2/check-limit
  → {"service": "parts_search", "counter": "text_queries_per_day"}
  → Возвращает {"allowed": true/false, "used": 3, "limit": 5}
  → Требует JWT
```

Подключить в main.py. Добавить публичные пути в jwt_auth.py middleware.

Старые эндпоинты /billing/* НЕ удалять — обратная совместимость.

---

## Шаг 5: Модели

Создать `src/models/billing_v2.py`:

```python
from pydantic import BaseModel

class PlatformServiceResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    icon: str | None
    plans: list["ServicePlanResponse"]

class ServicePlanResponse(BaseModel):
    id: str
    slug: str
    name: str
    price_monthly: float
    limits: dict
    features: dict

class SeatPackageResponse(BaseModel):
    id: str
    slug: str
    name: str
    max_seats: int
    price_monthly: float
    price_per_seat: float | None

class TenantSubscriptionResponse(BaseModel):
    service_slug: str
    service_name: str
    plan_slug: str
    plan_name: str
    price_monthly: float
    limits: dict
    status: str

class TenantBillingSummary(BaseModel):
    subscriptions: list[TenantSubscriptionResponse]
    seat_package: SeatPackageResponse | None
    seats_used: int
    seats_total: int
    total_monthly: float

class UsageResponse(BaseModel):
    service_slug: str
    counters: dict  # {"text_queries_per_day": {"used": 3, "limit": 5}}

class CheckLimitRequest(BaseModel):
    service: str
    counter: str

class CheckLimitResponse(BaseModel):
    allowed: bool
    used: int
    limit: int | str  # int или "unlimited"
```

---

## Шаг 6: Обновить дашборды

### Mini App DashboardView
Вместо захардкоженных карточек → загружать из GET /billing/v2/my:
- Показывать реальные сервисы с реальными планами
- "Поиск запчастей — Free (5 запросов/день)"
- "Авито Мессенджер — Free (заглушка)"

### Frontend-admin DashboardView
Аналогично — загружать из API.

---

## Шаг 7: Обновить документацию

Обновить `tenant-auth/CLAUDE.md`:
- Добавить в таблицы БД: platform_services, service_plans, tenant_subscriptions, seat_packages, tenant_seat_subscriptions, usage_counters, payment_history
- Добавить: billing_v2_service.py, routers/billing_v2.py, models/billing_v2.py
- Обновить метку времени

Обновить `PROGRESS.md`:
- [x] Биллинг v2: сервисы, планы, подписки, места (структура БД + заглушки)
- Обновить метку времени

---

## Что НЕ делать
- НЕ удалять старый billing_service.py и эндпоинты /billing/*
- НЕ реализовывать оплату (ЮKassa, Stripe и т.п.)
- НЕ реализовывать автоматическое продление/отмену подписок
- НЕ реализовывать UI для смены тарифа (позже)
- НЕ реализовывать UI для покупки мест (позже)
- НЕ удалять таблицу billing_plans (старая, для совместимости)
- НЕ создавать README.md

## Порядок выполнения
1. Создать миграции и выполнить через psql
2. Создать модели billing_v2.py
3. Создать сервис billing_v2_service.py
4. Создать роутер billing_v2.py, подключить в main.py
5. Добавить create_free_subscriptions при регистрации
6. Обновить дашборды (Mini App + frontend-admin) — загрузка из API
7. Протестировать: зарегистрировать нового пользователя → проверить что free-подписки создались
8. Обновить CLAUDE.md и PROGRESS.md
