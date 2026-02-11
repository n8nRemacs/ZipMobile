# ТЗ: Развёртывание tenant-auth — БД, конфигурация, исправление багов, тест

## Контекст
Проект ZipMobile/ уже создан. Код tenant-auth на месте.
Создан новый чистый Supabase проект `TenantSystem`.
Нужно: создать таблицы, настроить .env, исправить известные баги, протестировать полный flow.

## Параметры Supabase
```
SUPABASE_URL=https://dskhyumhxgbzmuefmrax.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRza2h5dW1oeGdiem11ZWZtcmF4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDY1MTkyMSwiZXhwIjoyMDg2MjI3OTIxfQ.EKELj3L3lcB-qtu0_YEpL1bEOLx7JK4qLcFHwNumAQE
DATABASE_URL=postgresql://postgres.dskhyumhxgbzmuefmrax:Mi31415926pSss!@aws-1-eu-west-1.pooler.supabase.com:5432/postgres
```

## Прямой доступ к БД
Opus имеет прямой доступ к PostgreSQL через psql или psycopg2.
Для выполнения SQL-миграций использовать:
```bash
psql "postgresql://postgres.dskhyumhxgbzmuefmrax:Mi31415926pSss!@aws-1-eu-west-1.pooler.supabase.com:5432/postgres" -f migrations/001_init.sql
```
НЕ нужно просить пользователя заходить в Supabase Dashboard — всё делать самостоятельно.

---

## Шаг 1: Создать SQL-миграции

Создать файл `tenant-auth/migrations/001_init.sql`:

```sql
-- ============================================
-- 001_init.sql — Базовые таблицы платформы
-- Для проекта TenantSystem (dskhyumhxgbzmuefmrax)
-- ============================================

-- Расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Supervisors (партнёры/реселлеры)
CREATE TABLE IF NOT EXISTS supervisors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    email TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Billing Plans (тарифные планы)
CREATE TABLE IF NOT EXISTS billing_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    price_monthly DECIMAL(10,2) DEFAULT 0,
    max_api_keys INT DEFAULT 1,
    max_sessions INT DEFAULT 1,
    max_sub_users INT DEFAULT 1,
    features JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tenants (SaaS-клиенты)
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    supervisor_id UUID REFERENCES supervisors(id),
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    settings JSONB DEFAULT '{}',
    billing_plan_id UUID REFERENCES billing_plans(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- API Keys
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL UNIQUE,
    name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tenant Users (пользователи тенанта)
CREATE TABLE IF NOT EXISTS tenant_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone TEXT NOT NULL UNIQUE,
    email TEXT,
    email_verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE,
    name TEXT,
    avatar_url TEXT,
    role TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('owner', 'admin', 'manager', 'viewer')),
    settings JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Verification Codes (OTP)
CREATE TABLE IF NOT EXISTS verification_codes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    target TEXT NOT NULL,
    target_type TEXT NOT NULL CHECK (target_type IN ('phone', 'email')),
    code TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('sms', 'telegram', 'whatsapp', 'vk_max', 'email', 'console')),
    purpose TEXT NOT NULL CHECK (purpose IN ('register', 'login', 'verify_email', 'change_phone', 'change_email')),
    attempts INT DEFAULT 0,
    max_attempts INT DEFAULT 5,
    is_used BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Refresh Tokens (JWT сессии)
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    token_hash TEXT NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES tenant_users(id) ON DELETE CASCADE,
    device_info JSONB DEFAULT '{}',
    is_revoked BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tenant Invites (приглашения sub-пользователей)
CREATE TABLE IF NOT EXISTS tenant_invites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    invited_by UUID NOT NULL REFERENCES tenant_users(id),
    phone TEXT,
    email TEXT,
    role TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('admin', 'manager', 'viewer')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'cancelled', 'expired')),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Notification Preferences
CREATE TABLE IF NOT EXISTS notification_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES tenant_users(id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK (channel IN ('sms', 'telegram', 'whatsapp', 'vk_max', 'email')),
    event_type TEXT NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, channel, event_type)
);

-- Notification History
CREATE TABLE IF NOT EXISTS notification_history (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES tenant_users(id) ON DELETE CASCADE,
    channel TEXT NOT NULL,
    event_type TEXT NOT NULL,
    title TEXT,
    body TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant ON tenant_users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_users_phone ON tenant_users(phone);
CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_verification_codes_target ON verification_codes(target, purpose);
CREATE INDEX IF NOT EXISTS idx_tenant_invites_tenant ON tenant_invites(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_invites_hash ON tenant_invites(token_hash);
CREATE INDEX IF NOT EXISTS idx_notification_prefs_user ON notification_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_history_user ON notification_history(user_id);
```

Создать файл `tenant-auth/migrations/002_seed.sql`:

```sql
-- ============================================
-- 002_seed.sql — Начальные данные
-- ============================================

-- Billing Plans
INSERT INTO billing_plans (id, name, price_monthly, max_api_keys, max_sessions, max_sub_users, features) VALUES
    ('e0000000-0000-0000-0000-000000000001', 'free', 0, 1, 1, 1, '{"description": "Бесплатный тариф"}'),
    ('e0000000-0000-0000-0000-000000000002', 'starter', 990, 3, 5, 3, '{"description": "Начальный тариф"}'),
    ('e0000000-0000-0000-0000-000000000003', 'pro', 2990, 10, 20, 10, '{"description": "Профессиональный тариф"}')
ON CONFLICT (name) DO NOTHING;

-- Default Supervisor (для dev/test)
INSERT INTO supervisors (id, name, email) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'DevSupervisor', 'dev@zipmobile.ru')
ON CONFLICT (id) DO NOTHING;
```

---

## Шаг 2: Выполнить миграции в Supabase

Выполнить миграции напрямую через psql:

```bash
cd tenant-auth

# Установить psql если нет
# Ubuntu/Debian: sudo apt-get install -y postgresql-client
# macOS: brew install libpq

# Выполнить миграции
psql "postgresql://postgres.dskhyumhxgbzmuefmrax:Mi31415926pSss!@aws-1-eu-west-1.pooler.supabase.com:5432/postgres" -f migrations/001_init.sql
psql "postgresql://postgres.dskhyumhxgbzmuefmrax:Mi31415926pSss!@aws-1-eu-west-1.pooler.supabase.com:5432/postgres" -f migrations/002_seed.sql
```

Если psql недоступен — использовать Python:
```python
import psycopg2
conn = psycopg2.connect("postgresql://postgres.dskhyumhxgbzmuefmrax:Mi31415926pSss!@aws-1-eu-west-1.pooler.supabase.com:5432/postgres")
cur = conn.cursor()
with open("migrations/001_init.sql") as f:
    cur.execute(f.read())
conn.commit()
with open("migrations/002_seed.sql") as f:
    cur.execute(f.read())
conn.commit()
conn.close()
```

**Проверить что таблицы создались:**
```sql
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;
```
Ожидаемый результат: api_keys, billing_plans, notification_history, notification_preferences, refresh_tokens, supervisors, tenant_invites, tenant_users, tenants, verification_codes.

---

## Шаг 3: Создать .env файл

Создать `tenant-auth/.env` (НЕ коммитить в git!):

```
SUPABASE_URL=https://dskhyumhxgbzmuefmrax.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRza2h5dW1oeGdiem11ZWZtcmF4Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MDY1MTkyMSwiZXhwIjoyMDg2MjI3OTIxfQ.EKELj3L3lcB-qtu0_YEpL1bEOLx7JK4qLcFHwNumAQE
DATABASE_URL=postgresql://postgres.dskhyumhxgbzmuefmrax:Mi31415926pSss!@aws-1-eu-west-1.pooler.supabase.com:5432/postgres
HOST=0.0.0.0
PORT=8090
LOG_LEVEL=info
JWT_SECRET=zipmobile-jwt-secret-change-in-production-2026
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
OTP_PROVIDER=console
OTP_LENGTH=6
OTP_EXPIRE_MINUTES=5
OTP_MAX_ATTEMPTS=5
OTP_MAX_CODES_PER_HOUR=5
INTERNAL_SECRET=zipmobile-internal-secret-change-in-production
CORS_ORIGINS=["http://localhost:3000","https://avito.newlcd.ru"]
```

---

## Шаг 4: Исправить баги

### Баг 1: supervisor_id хардкод
Файл: `src/services/user_service.py`, функция `create_tenant_and_user()`

**Проблема:** хардкод `"supervisor_id": "a0000000-0000-0000-0000-000000000001"`. Если supervisor не существует — ошибка FK.

**Исправление:** Сначала проверять наличие supervisor, если нет — создать:
```python
def _get_default_supervisor_id() -> str:
    """Получить ID dev-supervisor, создать если не существует."""
    sb = get_supabase()
    DEFAULT_ID = "a0000000-0000-0000-0000-000000000001"
    resp = sb.table("supervisors").select("id").eq("id", DEFAULT_ID).limit(1).execute()
    if resp.data:
        return DEFAULT_ID
    # Создаём если нет (seed не выполнялся)
    sb.table("supervisors").insert({
        "id": DEFAULT_ID,
        "name": "DefaultSupervisor",
        "email": "dev@zipmobile.ru",
    }).execute()
    return DEFAULT_ID
```
И использовать `_get_default_supervisor_id()` вместо хардкода.

### Баг 2: verify-otp не обрабатывает change_phone / change_email
Файл: `src/routers/auth.py`, функция `verify_otp()`, строки ~111-116

**Проблема:** `elif req.purpose == "change_phone": pass` и `elif req.purpose == "change_email": pass`

**Исправление:**
```python
elif req.purpose == "change_phone":
    # target OTP — это новый телефон, ищем его
    from src.storage.supabase import get_supabase
    sb = get_supabase()
    # Код уже верифицирован выше (otp_service.verify_otp)
    # target в verification_codes = новый телефон
    user_service.change_phone(user["id"], req.phone)
    # Примечание: req.phone тут — старый телефон (по нему нашли user)
    # Новый телефон нужно брать из verification_codes target
    # Но это сложнее — пока пропускаем, смена phone работает через /profile/verify-phone

elif req.purpose == "change_email":
    # Аналогично — работает через /profile/verify-email
    pass
```
**Решение:** Оставить pass, но добавить комментарий что смена phone/email идёт через /profile/verify-phone и /profile/verify-email, а не через общий /verify-otp. Это не баг а design — через /verify-otp проходят только register, login, verify_email.

### Баг 3: profile verify-phone/email ищет OTP без привязки к user_id
Файл: `src/routers/profile.py`, функция `verify_phone()`, строки ~66-75

**Проблема:** Запрос к verification_codes фильтрует только по `purpose="change_phone"` без привязки к user_id. Теоретически один пользователь может увидеть код другого.

**Исправление:** Добавить фильтр. Но target в verification_codes — это новый телефон, а не user_id. Поэтому нужно хранить user_id в verification_codes или искать по target = new_phone, которому мы только что отправили код. Простое решение: при запросе change_phone мы знаем new_phone, сохраняем его в request.state или session. Но у нас stateless API.

**Прагматичное решение для MVP:** Добавить фильтр по `target` из текущего пользователя. В verify_phone:
1. Получить user из JWT
2. Найти последний OTP с purpose=change_phone, is_used=False для этого пользователя
3. Но мы не знаем target (новый телефон) из JWT

**Реальное исправление:** При создании verification_code для change_phone/change_email — добавить поле `user_id` в verification_codes. Но это меняет схему БД.

**Решение на сейчас:** Добавить в verification_codes неразрывную связку: при создании OTP на change_phone сохранять user_id текущего пользователя. Но таблица verification_codes не имеет поля user_id.

**Итого:** НЕ чинить сейчас. Добавить TODO-комментарий в код. Для MVP это приемлемый риск — эксплуатация требует знания нового телефона И кода одновременно.

### Баг 4: Нет проверки лимитов billing
Файл: `src/routers/api_keys.py`, функция `create_key()`
Файл: `src/routers/invites.py`, функция `create_invite()`

**Исправление для api_keys.py — в create_key() после require_email_verified:**
```python
# Проверить лимит тарифа
from src.services import billing_service
usage = billing_service.get_usage(user["tenant_id"])
if usage["api_keys_used"] >= usage["api_keys_limit"]:
    raise HTTPException(status_code=403, detail=f"API key limit reached ({usage['api_keys_limit']}). Upgrade your plan.")
```

**Исправление для invites.py — в create_invite() после require_email_verified:**
```python
from src.services import billing_service
usage = billing_service.get_usage(user["tenant_id"])
if usage["sub_users_used"] >= usage["sub_users_limit"]:
    raise HTTPException(status_code=403, detail=f"Team member limit reached ({usage['sub_users_limit']}). Upgrade your plan.")
```

---

## Шаг 5: Установить зависимости и запустить

```bash
cd tenant-auth
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8090 --reload
```

Проверить:
```bash
curl http://localhost:8090/health
# Ожидаем: {"status":"ok","version":"0.1.0"}

curl http://localhost:8090/ready
# Ожидаем: {"status":"ready","supabase":true}
```

Если /ready возвращает `"supabase": false` — проблема с подключением к Supabase (проверь .env).

---

## Шаг 6: Тест полного flow

```bash
# 1. Регистрация
curl -s -X POST http://localhost:8090/auth/v1/register \
  -H "Content-Type: application/json" \
  -d '{"phone":"+79990001234","email":"test@test.com","name":"TestCompany","otp_channel":"console"}'

# Ожидаем: {"message":"OTP sent for registration","channel":"console","expires_in":300}
# В логах сервера появится OTP CODE — запомнить его!

# 2. Верификация OTP (подставить реальный код из логов)
curl -s -X POST http://localhost:8090/auth/v1/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"phone":"+79990001234","code":"XXXXXX","purpose":"register"}'

# Ожидаем: {"access_token":"eyJ...","refresh_token":"...","token_type":"bearer","expires_in":1800}
# СОХРАНИТЬ access_token!

# 3. Проверить профиль
curl -s http://localhost:8090/auth/v1/profile \
  -H "Authorization: Bearer <access_token>"

# Ожидаем: {"id":"...","tenant_id":"...","phone":"+79990001234","email":"test@test.com","role":"owner",...}

# 4. Посмотреть тарифы
curl -s http://localhost:8090/auth/v1/billing/plans

# Ожидаем: массив из 3 планов (free, starter, pro)

# 5. Посмотреть текущий план
curl -s http://localhost:8090/auth/v1/billing/current \
  -H "Authorization: Bearer <access_token>"

# Ожидаем: {"plan":{"name":"free",...},"usage":{"api_keys_used":0,"api_keys_limit":1,...}}

# 6. Создать API-ключ (ВНИМАНИЕ: нужен email_verified!)
# Для тест-обхода: сначала вручную верифицируем email в БД
# Или через OTP на email (будет в логах если OTP_PROVIDER=console)

# 7. Logout
curl -s -X POST http://localhost:8090/auth/v1/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'

# Ожидаем: {"message":"Logged out"}

# 8. Логин (повторный вход)
curl -s -X POST http://localhost:8090/auth/v1/login \
  -H "Content-Type: application/json" \
  -d '{"phone":"+79990001234","otp_channel":"console"}'
# Повторить verify-otp с новым кодом
```

---

## Шаг 7: Обновить CLAUDE.md

После выполнения всех шагов обновить `tenant-auth/CLAUDE.md`:
- В разделе "Параметры" обновить Supabase URL на `dskhyumhxgbzmuefmrax`
- В разделе "Известные проблемы" пометить исправленные баги как ✅
- Обновить метку времени

Также обновить `PROGRESS.md`:
- Пометить чекбоксы выполненных пунктов

---

## Что НЕ делать
- НЕ менять структуру файлов/папок
- НЕ переключать httpx на async (оставить на потом)
- НЕ рефакторить рабочий код без явного указания
- НЕ создавать тестовых пользователей в seed (кроме supervisor и billing_plans)
- НЕ создавать файлы README.md, ARCHITECTURE.md и т.п.

## Порядок выполнения
1. Создать папку migrations/ и файлы SQL
2. Сообщить пользователю: "Выполни SQL в Supabase Dashboard → SQL Editor"
3. Создать .env
4. Исправить баги (шаг 4)
5. Установить зависимости и запустить (шаг 5)
6. Провести тесты (шаг 6)
7. Обновить CLAUDE.md и PROGRESS.md (шаг 7)
