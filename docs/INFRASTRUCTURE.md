# Infrastructure Access

## Server

| Parameter | Value |
|-----------|-------|
| IP | 85.198.98.104 |
| SSH | `ssh root@85.198.98.104` |
| Password | Mi31415926pSss! |

## Domains (pending DNS setup)

| Service | Domain | DNS Record |
|---------|--------|------------|
| n8n | n8n.zipmobile.ru | A → 85.198.98.104 |

## Services

### n8n

| Parameter | Value |
|-----------|-------|
| URL | https://n8n.zipmobile.ru |
| Direct URL | http://85.198.98.104:5678 |
| Login | dk.remacs@gmail.com |
| Password | Mi31415926pSss! |
| Config | `/opt/n8n/docker-compose.yml` |

### Supabase Cloud

> **ВАЖНО**: Локальный Supabase удалён с сервера 85.198.98.104 (24.01.2026).
> Все данные перенесены в облачный Supabase.

| Parameter | Value |
|-----------|-------|
| Dashboard | https://supabase.com/dashboard/project/griexhozxrqtepcilfnu |
| Project ID | `griexhozxrqtepcilfnu` |
| Region | `eu-west-3` (Paris) |

#### Database Connection

| Parameter | Value |
|-----------|-------|
| Host (Pooler) | `aws-1-eu-west-3.pooler.supabase.com` |
| Host (Direct) | `db.griexhozxrqtepcilfnu.supabase.co` |
| Port | **5432** |
| Database | `postgres` |
| User (Pooler) | `postgres.griexhozxrqtepcilfnu` |
| User (Direct) | `postgres` |
| Password | `Mi31415926pSss!` |
| SSL | `require` |

**Connection String (Pooler - рекомендуется):**
```
postgresql://postgres.griexhozxrqtepcilfnu:Mi31415926pSss!@aws-1-eu-west-3.pooler.supabase.com:5432/postgres?sslmode=require
```

> **Примечание**: Direct connection работает только через IPv6. Сервер 85.198.98.104 не имеет IPv6, поэтому используйте Pooler.

#### Database Structure

Все таблицы находятся в единой БД `postgres` с уникальными префиксами:

| Prefix | Shop | Tables |
|--------|------|--------|
| `zip_` | Central | `zip_shops`, `zip_outlets`, `zip_dict_brands`, `zip_nomenclature`, ... |
| `profi_` | Profi | `profi_nomenclature`, `profi_current_prices`, `profi_staging` |
| `greenspark_` | GreenSpark | `greenspark_nomenclature`, `greenspark_parser_progress` |
| `taggsm_` | TAGGSM | `taggsm_nomenclature`, `taggsm_prices` |
| `memstech_` | MemsTech | `memstech_nomenclature`, `memstech_prices` |
| `liberti_` | Liberti | `liberti_nomenclature`, `liberti_prices` |
| `lcdstock_` | LCD-Stock | `lcdstock_nomenclature_v2`, `lcdstock_prices_v2`, `lcdstock_products` |
| `signal23_` | Signal23 | `signal23_nomenclature`, `signal23_prices` |
| `orizhka_` | Orizhka | `orizhka_nomenclature`, `orizhka_prices` |
| `_05gsm_` | 05GSM | `_05gsm_nomenclature`, `_05gsm_prices` |
| `moysklad_naffas_` | NAFFAS | `moysklad_naffas_nomenclature`, `moysklad_naffas_prices` |
| `moba_` | Moba | `moba_nomenclature`, `moba_prices` |
| `master_` | Master | `master_unified_nomenclature` |

#### n8n PostgreSQL Credentials

Для n8n workflows используйте:

| Parameter | Value |
|-----------|-------|
| Host | `aws-1-eu-west-3.pooler.supabase.com` |
| Port | `5432` |
| Database | `postgres` |
| User | `postgres.griexhozxrqtepcilfnu` |
| Password | `Mi31415926pSss!` |
| SSL | `require` |

#### Python Parsers Connection

Все парсеры используют `SHOPS/db_wrapper.py` для подключения:

```python
# В парсере:
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_wrapper import get_db

conn = get_db()  # Подключение к Supabase Cloud с автоматическим маппингом таблиц
```

Конфигурация: `SHOPS/db_config.py`

## Management Commands

```bash
# SSH to server
ssh root@85.198.98.104

# n8n
cd /opt/n8n && docker compose logs -f
cd /opt/n8n && docker compose restart

# PostgreSQL (Supabase Cloud)
psql "postgresql://postgres.griexhozxrqtepcilfnu:Mi31415926pSss!@aws-1-eu-west-3.pooler.supabase.com:5432/postgres?sslmode=require"

# Nginx
systemctl status nginx
nginx -t && systemctl reload nginx

# Get SSL certificates (after DNS setup)
certbot --nginx -d n8n.zipmobile.ru --non-interactive --agree-tos --email admin@zipmobile.ru --redirect
```

## Nginx Configs

- `/etc/nginx/sites-available/n8n`
