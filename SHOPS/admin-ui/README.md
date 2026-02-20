# ZipMobile Admin UI

Административная панель для управления нормализацией товаров ZipMobile. Позволяет модерировать AI-предложения, управлять справочниками и отслеживать статистику нормализации по магазинам.

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                   Admin UI (:3000)                       │
│                                                          │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────┐     │
│  │Dashboard │  │ Moderation   │  │ Dictionaries   │     │
│  │          │  │              │  │                │     │
│  │ Статис-  │  │ Таблица      │  │ Бренды         │     │
│  │ тика по  │  │ pending      │  │ Модели         │     │
│  │ магази-  │  │ записей      │  │ Типы запчастей │     │
│  │ нам      │  │      │       │  │ Цвета          │     │
│  │          │  │      ▼       │  │                │     │
│  │ Кнопки   │  │ Модалка      │  │                │     │
│  │ запуска  │  │ разрешения:  │  │                │     │
│  │ нормали- │  │ - Autocomplete│  │                │     │
│  │ зации    │  │ - Создать    │  │                │     │
│  │          │  │   новый      │  │                │     │
│  └──────────┘  └──────────────┘  └────────────────┘     │
│                         │                                │
│                    Axios / Vite Proxy                     │
│                         │                                │
└─────────────────────────┼────────────────────────────────┘
                          ▼
              Normalizer API (:8200)
                          │
                          ▼
                Supabase PostgreSQL
```

## Стек технологий

- **React 18** — UI-фреймворк
- **TypeScript** — типизация
- **Vite 6** — сборка и dev-сервер
- **React Router 6** — клиентская маршрутизация
- **Ant Design 5** — UI-компоненты (таблицы, формы, модалки, лейаут)
- **TanStack React Query 5** — data fetching, кэширование, инвалидация
- **TanStack React Table 8** — расширяемые таблицы
- **Axios** — HTTP-клиент
- **dayjs** — форматирование дат

## Структура файлов

```
admin-ui/
├── package.json                # Зависимости и скрипты
├── tsconfig.json               # TypeScript конфиг
├── vite.config.ts              # Vite конфиг + proxy /api → :8200
├── index.html                  # Входная точка HTML
└── src/
    ├── main.tsx                # ReactDOM.createRoot + providers
    ├── App.tsx                 # Layout (Sider + Header) + Router
    ├── api/
    │   └── client.ts           # Axios-клиент ко всем эндпоинтам Normalizer API
    ├── types/
    │   └── index.ts            # TypeScript-интерфейсы (ModerationItem, Brand, Model, и т.д.)
    ├── pages/
    │   ├── ModerationList.tsx  # Главная: таблица модерации + фильтры + модалка
    │   ├── Dashboard.tsx       # Статистика по магазинам + запуск нормализации
    │   └── Dictionaries.tsx    # CRUD справочников (табы: бренды/модели/типы/цвета)
    └── components/
        ├── DataTable.tsx       # Обёртка над antd Table с пагинацией
        ├── StatusBadge.tsx     # Цветной тег статуса
        ├── BrandSelect.tsx     # Autocomplete-селект брендов (с поиском)
        ├── ModelSelect.tsx     # Autocomplete-селект моделей (фильтр по бренду)
        └── ModerationModal.tsx # Модалка разрешения: существующий / создать новый
```

## Страницы

### Dashboard (`/dashboard`)

Обзорная панель с ключевыми метриками:

- **Карточки сверху:** общее кол-во товаров / нормализовано / ожидают нормализации / в модерации
- **Таблица по магазинам:**
  - Магазин, код, всего, нормализовано, ожидает, покрытие (%)
  - Кнопка "Normalize (N)" — запуск фоновой нормализации для магазина
- **Таблица модерации:** кол-во pending/resolved записей по типам сущностей

API-вызовы:
- `GET /normalize/status` — статистика по магазинам
- `GET /moderate/stats` — статистика модерации
- `POST /normalize/shop/{code}` — запуск нормализации

### Moderation (`/moderation`) — главная страница

Очередь записей, ожидающих модерации:

- **Фильтры:** тип сущности (brand/model/part_type/color), магазин
- **Таблица:** ID, тип, предложение AI, исходное наименование, артикул, магазин, confidence, статус, дата
- **Сортировка:** по дате, по confidence
- **Клик на строку** → открывает ModerationModal

**ModerationModal** — модальное окно разрешения записи:
1. Показывает исходное наименование товара (крупно)
2. AI-предложение с confidence и reasoning
3. **Вариант 1 — использовать существующий:**
   - Autocomplete-поиск по справочнику (BrandSelect / ModelSelect)
   - Кнопка "Use existing"
4. **Вариант 2 — создать новый:**
   - Поле ввода имени (предзаполнено AI-предложением)
   - Для моделей — выбор бренда
   - Кнопка "Create new"

API-вызовы:
- `GET /moderate` — список pending записей
- `POST /moderate/{id}/resolve` — разрешение записи

### Dictionaries (`/dictionaries`)

Просмотр справочников в табах:

- **Бренды** — ID, Name
- **Модели** — ID, Name, Brand ID
- **Типы запчастей** — ID, Name
- **Цвета** — ID, Name

Каждый таб показывает количество записей в заголовке: `Brands (150)`.

API-вызовы:
- `GET /dict/brands`
- `GET /dict/models`
- `GET /dict/part_types`
- `GET /dict/colors`

## Компоненты

### `DataTable<T>`
Обёртка над `antd Table`. Принимает `columns`, `data`, `loading`, `rowKey`, `pagination`, `onRow`. По умолчанию пагинация 20 записей с переключателем размера.

### `StatusBadge`
Цветной `antd Tag` по статусу:
- `pending` — оранжевый
- `resolved` / `normalized` / `completed` — зелёный
- `needs_moderation` — красно-оранжевый
- `running` — синий
- `failed` — красный

### `BrandSelect`
`antd Select` с серверным поиском. При вводе текста делает `GET /dict/brands?q=...`, кэшируется через React Query.

### `ModelSelect`
`antd Select mode="multiple"` с серверным поиском. Фильтрует модели по `brand_id`. Заблокирован пока бренд не выбран.

### `ModerationModal`
Модалка разрешения записи модерации. Два варианта:
1. Привязать к существующей сущности (autocomplete)
2. Создать новую (ввод имени + доп. данные)

После разрешения — инвалидирует кэш React Query и закрывает модалку.

## API-клиент

Файл `src/api/client.ts` — Axios-инстанс с `baseURL: '/api'`.

В development Vite проксирует `/api/*` → `http://localhost:8200/*` (настроено в `vite.config.ts`).

Все функции типизированы:

```typescript
// Нормализация
normalizeShop(shopCode: string): Promise<{task_id: string, total: number}>
getNormalizeStatus(): Promise<ShopNormStatus[]>
getTask(taskId: string): Promise<TaskInfo>

// Модерация
getModerationList(params): Promise<ModerationItem[]>
getModerationItem(id: number): Promise<ModerationItem>
resolveModeration(id: number, req: ResolveRequest): Promise<{resolved_entity_id: number}>
getModerationStats(): Promise<ModerationStats>

// Справочники
getBrands(q?: string): Promise<Brand[]>
getModels(brandId?: number, q?: string): Promise<Model[]>
getPartTypes(): Promise<PartType[]>
getColors(): Promise<Color[]>
```

## TypeScript типы

Определены в `src/types/index.ts`:

| Тип | Описание |
|---|---|
| `ModerationItem` | Запись очереди модерации |
| `ResolveRequest` | Запрос на разрешение модерации |
| `Brand` | Бренд из справочника |
| `Model` | Модель из справочника (+ brand_id) |
| `PartType` | Тип запчасти |
| `Color` | Цвет |
| `ShopNormStatus` | Статистика нормализации одного магазина |
| `ModerationStats` | Агрегат модерации по типам/статусам |
| `TaskInfo` | Информация о фоновой задаче |

## Конфигурация

### Vite Proxy (development)

В `vite.config.ts`:
```typescript
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8200',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
    },
  },
}
```

Все запросы `http://localhost:3000/api/*` проксируются на `http://localhost:8200/*`.

### Production

Для production сборки (`npm run build`) нужно настроить nginx/reverse proxy, чтобы `/api` роутился на Normalizer API.

## Запуск

```bash
# Установка зависимостей
cd SHOPS/admin-ui
npm install

# Development (hot reload)
npm run dev
# → http://localhost:3000

# Production build
npm run build
# → dist/

# Preview production build
npm run preview
```

## Требования

- **Node.js 18+**
- **Normalizer API** запущен на `:8200` (для backend данных)

## Связь с другими сервисами

- **Normalizer API** (`:8200`) — все данные приходят через REST API нормализатора
- **n8n** (`:5678`) — AI-воркфлоу (вызывается из Normalizer API, не напрямую из UI)
- **Supabase PostgreSQL** — данные хранятся в БД (доступ через Normalizer API)

## Маршруты

| Путь | Страница | Описание |
|---|---|---|
| `/` | → redirect | Перенаправление на `/moderation` |
| `/dashboard` | Dashboard | Статистика и управление |
| `/moderation` | ModerationList | Очередь модерации |
| `/dictionaries` | Dictionaries | Справочники |
