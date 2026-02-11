# ZipMobile Platform — Прогресс
Обновлено: 2026-02-11 22:00 (GMT+4)

## tenant-auth (микросервис авторизации)
- [x] Код написан (2600+ строк, 50+ файлов)
- [x] Config, Storage, Middleware, Providers, Models, Routers, Services
- [x] Dockerfile + requirements.txt
- [x] БД: миграции 001_init.sql + 002_seed.sql + 003_telegram_auth.sql выполнены
- [x] Исправлены баги: supervisor_id, verify-otp комментарии, billing limits
- [x] Тест полного flow: register → verify-otp → profile → billing/plans → billing/current → logout → login → verify-otp
- [x] Telegram Mini App авторизация (модели, сервис, роутер, миграция 003)
- [x] Telegram Web Login (POST /auth/v1/telegram/web-login, валидация Login Widget hash)
- [x] Bot setup script (src/bot/setup_bot.py)
- [ ] Деплой на homelab (Docker)

## frontend-miniapp (Telegram Mini App)
- [x] Инициализирован (Vue 3 + Naive UI + Vite + TypeScript)
- [x] Composable useTelegram (WebApp SDK)
- [x] API layer (auth.ts), Pinia store (auth.ts)
- [x] Views: LoginView, RegisterView, DashboardView, VerifyPhoneView
- [x] Компонент ChannelSelector
- [x] Три режима: новый пользователь → регистрация, phone_verified=false → верификация, полный доступ → дашборд
- [x] Сборка проходит без ошибок
- [ ] E2E тест в Telegram (нужен HTTPS туннель)

## frontend-admin (веб-приложение)
- [x] Инициализирован (Vue 3 + Naive UI + Vite + TypeScript, порт 3000)
- [x] Vite proxy /auth/v1 → localhost:8090
- [x] Pinia store (auth.ts), API layer (auth.ts), router с guards
- [x] LandingView — Telegram Login Widget + QR-код на бота
- [x] DashboardView — карточки сервисов (заглушки)
- [x] ProfileView — просмотр/редактирование профиля (PATCH /auth/v1/profile)
- [x] VerifyPhoneView — подтверждение номера через бота
- [x] Компоненты: TelegramLoginButton, MiniAppQR, AppHeader
- [ ] E2E тест (нужен HTTPS туннель + домен в BotFather)

## parts-api — пусто (будущее)
