# ZipMobile Platform — Прогресс
Обновлено: 2026-02-12 02:00 (GMT+4)

## tenant-auth (микросервис авторизации)
- [x] Код написан (3000+ строк, 55+ файлов)
- [x] Config, Storage, Middleware, Providers, Models, Routers, Services
- [x] Dockerfile + requirements.txt
- [x] БД: миграции 001–005 выполнены (включая billing v2)
- [x] Исправлены баги: supervisor_id, verify-otp комментарии, billing limits
- [x] Тест полного flow: register → verify-otp → profile → billing/plans → billing/current → logout → login → verify-otp
- [x] Telegram Mini App авторизация (модели, сервис, роутер, миграция 003)
- [x] Telegram Web Login (POST /auth/v1/telegram/web-login, валидация Login Widget hash)
- [x] Bot setup script (src/bot/setup_bot.py)
- [x] Биллинг v2: сервисы, планы, подписки, места, счётчики (004+005 миграции, сервис, роутер, модели)
- [x] Автоматические free-подписки при регистрации (Telegram + OTP)
- [x] POST /auth/v1/register-via-telegram — единый эндпоинт регистрации/входа через Telegram (Login Widget + Dev Login)
- [ ] Деплой на homelab (Docker)

## frontend-miniapp (Telegram Mini App)
- [x] Инициализирован (Vue 3 + Naive UI + Vite + TypeScript)
- [x] Composable useTelegram (WebApp SDK)
- [x] API layer (auth.ts), Pinia store (auth.ts)
- [x] Views: LoginView, RegisterView, DashboardView, VerifyPhoneView
- [x] Компонент ChannelSelector
- [x] Три режима: новый пользователь → регистрация, phone_verified=false → верификация, полный доступ → дашборд
- [x] DashboardView загружает реальные данные из /billing/v2/my
- [x] Сборка проходит без ошибок
- [ ] E2E тест в Telegram (нужен HTTPS туннель)

## frontend-admin (веб-приложение) — ТЗ-4 выполнено
- [x] Инициализирован (Vue 3 + Naive UI + Vite + TypeScript, порт 3000)
- [x] Vite proxy /auth/v1 → localhost:8090
- [x] API layer (auth.ts) — registerViaTelegram, logout, getProfile, billing v2, refresh interceptor
- [x] Composable useAuth (composables/useAuth.ts) — loginWithTelegram, devLogin, logout, fetchProfile
- [x] Pinia store (stores/auth.ts) — упрощённый, isAuthenticated, fetchProfile, logout
- [x] LoginView — Telegram Widget (production) + Dev Login (localhost), без OTP/телефона
- [x] OnboardingView — 3 шага: приветствие с first_name, выбор сервисов, итого
- [x] DashboardView — карточки сервисов с прогресс-барами (цветовая кодировка 0-70/70-90/90+%)
- [x] AppHeader — навигация: Дашборд, Биллинг (скоро), Команда (скоро), API-ключи (скоро), имя пользователя, Выйти
- [x] TelegramLoginButton — компонент Telegram Login Widget
- [x] Router: /login, /onboarding, /dashboard, catch-all → /dashboard
- [x] Router guards: requiresAuth, guest redirect
- [x] Сборка проходит без ошибок (vue-tsc + vite build)
- [ ] E2E тест (нужен HTTPS туннель + домен в BotFather)

## parts-api — пусто (будущее)
