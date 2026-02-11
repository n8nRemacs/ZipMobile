# tenant-auth — Микросервис авторизации
Обновлено: 2026-02-09 20:11 (GMT+4)

## Назначение
Авторизация тенантов, управление пользователями, биллинг, API-ключи, команда.
Общая платформа для ZipMobile, X-API и будущих сервисов.

## Параметры
- Порт: 8090
- Префикс API: `/auth/v1`
- БД: Supabase `dskhyumhxgbzmuefmrax` (service_role key)
- Контракт API: `/CONTRACTS/tenant-auth.yaml`
- Запуск: `uvicorn src.main:app --host 0.0.0.0 --port 8090`
- Docker: `docker build -t tenant-auth . && docker run -p 8090:8090 --env-file .env tenant-auth`

## Связь с другими сервисами
- `avito-gateway` читает JWT через shared JWT_SECRET (без сетевого вызова)
- `avito-gateway` резолвит API-ключи через `GET /auth/v1/tenants/by-api-key-hash/{hash}` (X-Internal-Secret)
- Фронтенд (`frontend-admin`) вызывает все `/auth/v1/*` эндпоинты

## Текущая структура файлов
```
tenant-auth/
├── CLAUDE.md              ← этот файл
├── Dockerfile             ← Python 3.12-slim, uvicorn
├── requirements.txt       ← fastapi, pyjwt, httpx, pydantic-settings
├── .env.example
└── src/
    ├── main.py            ← точка входа: FastAPI app, middleware, роутеры
    ├── config.py           ← Pydantic BaseSettings из .env
    ├── dependencies.py     ← get_current_user(), require_role(), require_email_verified(), require_internal_secret()
    ├── middleware/
    │   ├── error_handler.py    ← ловит необработанные исключения → JSON 500
    │   └── jwt_auth.py         ← Bearer token → request.state.current_user
    ├── storage/
    │   └── supabase.py         ← собственный PostgREST wrapper (httpx, НЕ supabase-py)
    ├── providers/               ← OTP-провайдеры (ABC + реализации)
    │   ├── base.py              ← OtpProvider ABC: send_otp(), channel
    │   ├── console.py           ← dev: логирует OTP в stdout ← РАБОТАЕТ
    │   ├── sms.py               ← заглушка (логирует как console)
    │   ├── telegram.py          ← заглушка
    │   ├── whatsapp.py          ← заглушка
    │   ├── vk_max.py            ← заглушка
    │   └── email_provider.py    ← заглушка
    ├── models/                  ← Pydantic v2 модели (request/response)
    │   ├── auth.py              ← RegisterRequest, LoginRequest, VerifyOtpRequest, TokenPair, OtpSentResponse
    │   ├── telegram_auth.py     ← TelegramRegisterRequest, TelegramAuthResponse, TelegramAutoLogin*
    │   ├── user.py              ← UserProfile, UserUpdate, ChangePhoneRequest, ChangeEmailRequest
    │   ├── api_key.py           ← ApiKeyCreate, ApiKeyResponse, ApiKeyCreatedResponse
    │   ├── billing.py           ← PlanInfo, CurrentPlanResponse, UsageStats, UpgradeRequest
    │   ├── invite.py            ← InviteCreate, InviteResponse, InviteAcceptRequest, TeamMemberResponse
    │   ├── notification.py      ← NotificationPref, NotificationPrefsUpdate, NotificationHistoryItem
    │   └── common.py            ← HealthResponse, ReadyResponse, ErrorResponse
    ├── routers/                 ← FastAPI роутеры (тонкие — вызывают services)
    │   ├── auth.py              ← /register, /login, /verify-otp, /refresh, /logout, /logout-all
    │   ├── telegram_auth.py     ← /telegram/register, /telegram/auto-login
    │   ├── profile.py           ← /profile (GET/PATCH), change-phone/email, verify-phone/email
    │   ├── api_keys.py          ← /api-keys (CRUD + rotate)
    │   ├── billing.py           ← /billing/plans, /current, /usage, /upgrade
    │   ├── invites.py           ← /team, /team/invite, /team/invites, role, remove
    │   ├── sessions.py          ← /sessions (GET, DELETE all, DELETE one)
    │   ├── notifications.py     ← /notifications/preferences, /history
    │   ├── tenant_params.py     ← /tenants/{id}/params, /by-api-key-hash/{hash} (internal)
    │   └── health.py            ← /health, /ready
    ├── bot/
    │   └── setup_bot.py         ← одноразовый скрипт настройки Telegram бота
    └── services/                ← бизнес-логика (вызывают storage/supabase.py)
        ├── otp_service.py       ← generate_code(), send_otp(), verify_otp(), check_rate_limit()
        ├── jwt_service.py       ← create_token_pair(), verify_access_token(), rotate_refresh(), revoke_*()
        ├── user_service.py      ← create_tenant_and_user(), get_user_by_phone(), set_*_verified(), team ops
        ├── telegram_auth_service.py ← validate_init_data(), register_via_telegram(), auto_login_via_telegram()
        ├── api_key_service.py   ← generate/create/list/update/delete/rotate_api_key()
        ├── billing_service.py   ← list_plans(), get_current_plan(), get_usage(), upgrade_plan()
        ├── invite_service.py    ← create/list/cancel/accept_invite()
        └── notification_service.py ← get/update_preferences(), get_history()
```

## Таблицы БД (Supabase — dskhyumhxgbzmuefmrax)
001_init.sql: supervisors, tenants, billing_plans, api_keys, tenant_users, verification_codes, refresh_tokens, tenant_invites, notification_preferences, notification_history, avito_sessions
002_seed.sql: billing_plans (free/starter/pro), supervisor (dev default a0000000-...)
003_telegram_auth.sql: +telegram_chat_id/username/phone/first_name/last_name + available_channels, preferred_channel в tenant_users; +company_name/city/address в tenants

## Переменные окружения
```
SUPABASE_URL=https://dskhyumhxgbzmuefmrax.supabase.co
SUPABASE_KEY=<service_role_key>
HOST=0.0.0.0
PORT=8090
LOG_LEVEL=info
JWT_SECRET=<shared-secret-min-32-chars>   ← общий с avito-gateway
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
OTP_PROVIDER=console                       ← console = все каналы → stdout
OTP_LENGTH=6
OTP_EXPIRE_MINUTES=5
OTP_MAX_ATTEMPTS=5
OTP_MAX_CODES_PER_HOUR=5
INTERNAL_SECRET=<secret-for-inter-service>
TELEGRAM_BOT_TOKEN=<bot-token-from-botfather>
TELEGRAM_BOT_USERNAME=zipmobile_bot
CORS_ORIGINS=["http://localhost:3000","http://localhost:3001","https://localhost:3001","https://avito.newlcd.ru"]
```

## Система ролей
| Роль | Профиль | API-ключи | Команда | Биллинг | Сессии |
|------|---------|-----------|---------|---------|--------|
| owner | read/write | CRUD | CRUD + invite | upgrade | read/revoke |
| admin | read/write | CRUD | CRUD + invite | read | read/revoke |
| manager | read/write | read | read | read | read/revoke |
| viewer | read | — | — | — | read |

## Публичные пути (без JWT)
/health, /ready, /docs, /openapi.json, /redoc
/auth/v1/register, /auth/v1/login, /auth/v1/verify-otp, /auth/v1/refresh
/auth/v1/billing/plans
/auth/v1/team/invites/{token}/accept
/auth/v1/telegram/* (Telegram Mini App, защита через initData подпись)
/auth/v1/tenants/* (internal, защищён X-Internal-Secret)

## Известные проблемы (TODO)
1. ❗ Все сервисы СИНХРОННЫЕ (httpx.Client) — блокируют event loop при нагрузке
2. ✅ user_service.create_tenant_and_user() — supervisor_id: теперь _get_default_supervisor_id() создаёт если нет
3. ❗ profile.py: verify-phone/email ищет OTP без привязки к user_id — TODO-комментарий добавлен, для MVP приемлемо
4. ✅ auth.py: verify-otp change_phone/change_email — добавлены комментарии, смена идёт через /profile/verify-*
5. ✅ Проверка лимитов billing добавлена в api_keys.py (create_key) и invites.py (create_invite)
6. ⚠️ revoke_all_user_tokens() — N отдельных UPDATE вместо batch
7. ⚠️ notification_service.update_preferences() — удаляет по одному вместо batch DELETE

## Архитектурные заметки
- Supabase wrapper синхронный (httpx.Client) — скопирован из avito-xapi
- JWT: HS256, shared secret с avito-gateway
- Refresh token: SHA-256 hash в БД, raw token отдаётся клиенту
- API key: формат `ak_` + 32 символа URL-safe base64, в БД SHA-256 hash
- OTP: при OTP_PROVIDER=console ВСЕ каналы (sms, telegram, etc.) логируют в stdout
