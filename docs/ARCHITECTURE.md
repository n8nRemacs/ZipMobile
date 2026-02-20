# Server Architecture

## Overview

Home server (Proxmox) accessible from the internet through a VPS relay using SSH reverse tunnels.
ISP uses CGNAT and kills long-lived UDP/non-standard TCP connections, so only standard SSH (port 22) works reliably.

```
                                    ┌──────────────────────────┐
                                    │   Supabase (Cloud DB)    │
                                    │   griexhozxrqtepcilfnu   │
                                    │   Free tier              │
                                    │                          │
                                    │   PostgreSQL (90+ таблиц)│
                                    │   Агрегация цен + Memory │
                                    │   ⚠ Засыпает через 7д   │
                                    └────────────▲─────────────┘
                                                 │
                                    keepalive cron (every 12h)
                                                 │
Internet Users                                   │
      │                                          │
      ▼                                          │
┌─────────────┐     Cloudflare DNS               │
│  Cloudflare  │     *.newlcd.ru → 155.212.221.67│
└──────┬──────┘                                  │
       │                                         │
       ▼ (HTTPS :443)                            │
┌──────────────────────────────────┐             │
│         VPS (Relay)              │─────────────┘
│     155.212.221.67               │
│     Ubuntu 22.04 LTS            │
│                                  │
│  Nginx (reverse proxy + SSL)     │
│  ┌────────────────────────────┐  │
│  │ proxmox.newlcd.ru :443    │──┼──→ localhost:8006 ─┐
│  │ n8n.newlcd.ru     :443    │──┼──→ localhost:5678 ─┤
│  │ SSH               :2222   │──┼──→ localhost:2222 ─┤
│  └────────────────────────────┘  │                    │
│                                  │   SSH Reverse      │
│  Marzban (VPN panel)             │   Tunnels          │
│  ┌────────────────────────────┐  │   (autossh)        │
│  │ :8000 :8443 :8880 :1080   │  │                    │
│  └────────────────────────────┘  │                    │
└──────────────────────────────────┘                    │
       ▲                                                │
       │  SSH tunnel (port 22)                          │
       │  (only protocol ISP doesn't kill)              │
       │                                                │
┌──────┴───────────────────────────┐                    │
│       Homelab (Proxmox)          │◄───────────────────┘
│     192.168.31.97 (LAN)          │
│     Debian 13 (trixie)           │
│     Proxmox VE 9.1.1            │
│                                  │
│  ┌────────────────────────────┐  │
│  │ Proxmox Web UI     :8006  │  │
│  │ SSH                :22    │  │
│  │ n8n (Docker)       :5678  │  │
│  └────────────────────────────┘  │
│                                  │
│  Docker Engine                   │
│  autossh (systemd service)       │
└──────────────────────────────────┘
       │
   Xiaomi Router (CGNAT)
       │
   ISP (100.64.0.0/10)
```

---

## Servers

### VPS - Relay Server

| Parameter | Value |
|-----------|-------|
| IP | 155.212.221.67 |
| OS | Ubuntu 22.04.5 LTS |
| CPU | 1 core |
| RAM | 1 GB |
| Role | Reverse proxy, SSL termination, SSH relay |
| SSH | Port 22 (root) |

**Services:**

| Service | Port | Description |
|---------|------|-------------|
| Nginx | 80, 443 | Reverse proxy + SSL (Let's Encrypt) |
| SSH | 22 | System SSH |
| Marzban | 8000, 8443, 8880, 1080 | VPN management panel (pre-existing) |

**Key configs:**
- `/etc/nginx/sites-available/proxmox` - Proxmox reverse proxy
- `/etc/nginx/sites-available/n8n` - n8n reverse proxy
- SSL certs managed by Certbot (auto-renewal)

### Homelab - Proxmox Server

| Parameter | Value |
|-----------|-------|
| LAN IP | 192.168.31.97 |
| OS | Debian 13 (trixie) |
| Proxmox | VE 9.1.1 |
| CPU | 16 cores (Intel) |
| RAM | 32 GB |
| Role | Main compute, containers, VMs |
| SSH | Port 22 (root) |

**Services:**

| Service | Port | Description |
|---------|------|-------------|
| Proxmox Web UI | 8006 | VM/container management |
| SSH | 22 | System SSH |
| n8n | 5678 | Workflow automation (Docker) |
| Docker Engine | - | Container runtime |
| autossh | - | Persistent SSH tunnel to VPS |

**Key configs:**
- `/etc/systemd/system/ssh-tunnel.service` - autossh tunnel service
- `/opt/n8n/docker-compose.yml` - n8n container
- `/etc/sysctl.d/99-keepalive.conf` - TCP keepalive (15s)

---

## Network

### DNS (Cloudflare - newlcd.ru)

| Record | Type | Value |
|--------|------|-------|
| proxmox.newlcd.ru | A | 155.212.221.67 |
| n8n.newlcd.ru | A | 155.212.221.67 |

Cloudflare proxy: OFF (DNS only, grey cloud) - SSL terminates on VPS via Let's Encrypt.

### SSH Reverse Tunnel

```
Homelab (autossh) ──SSH──▶ VPS:22

Port forwarding:
  VPS localhost:8006  ◄──▶  Homelab localhost:8006  (Proxmox)
  VPS localhost:2222  ◄──▶  Homelab localhost:22    (SSH)
  VPS localhost:5678  ◄──▶  Homelab localhost:5678  (n8n)
```

Tunnel options:
- `ServerAliveInterval=15` - keepalive every 15s
- `ServerAliveCountMax=3` - drop after 3 missed
- `ExitOnForwardFailure=yes` - fail fast on port conflicts
- `AUTOSSH_GATETIME=0` - no initial connection delay
- `Restart=always`, `RestartSec=10` - systemd auto-restart

### ISP Limitations

- **CGNAT**: ISP uses `100.64.0.0/10` address space, no public IP
- **Connection killing**: ISP/router kills long-lived UDP flows and non-standard TCP connections
- **What doesn't work**: Cloudflare Tunnel (port 7844), WireGuard (UDP), direct port forwarding
- **What works**: SSH on port 22 (standard, ISP doesn't interfere)

---

## Traffic Flow

### Web Request (e.g. proxmox.newlcd.ru)

```
1. Browser → DNS query → Cloudflare → 155.212.221.67
2. Browser → HTTPS:443 → VPS Nginx
3. Nginx → proxy_pass → localhost:8006
4. localhost:8006 → SSH tunnel → Homelab:8006
5. Proxmox responds back through the same chain
```

### SSH Access to Homelab

```
ssh root@155.212.221.67 -p 2222
  → VPS localhost:2222
  → SSH tunnel
  → Homelab:22
```

---

## Services Detail

### n8n (Workflow Automation)

- **URL**: https://n8n.newlcd.ru
- **Location**: Homelab Docker
- **Config**: `/opt/n8n/docker-compose.yml`
- **Data**: Docker volume `n8n_data` → `/home/node/.n8n`
- **Environment**:
  - `N8N_HOST=n8n.newlcd.ru`
  - `N8N_PROTOCOL=https`
  - `WEBHOOK_URL=https://n8n.newlcd.ru/`
  - `N8N_SECURE_COOKIE=true`

### Proxmox VE

- **URL**: https://proxmox.newlcd.ru
- **Location**: Homelab native
- **Port**: 8006 (HTTPS natively)
- **Note**: Nginx uses `proxy_ssl_verify off` because Proxmox has self-signed cert

### Supabase (Cloud Database)

- **Project ID**: `griexhozxrqtepcilfnu`
- **API URL**: `https://griexhozxrqtepcilfnu.supabase.co`
- **REST API**: `https://griexhozxrqtepcilfnu.supabase.co/rest/v1`
- **Dashboard**: https://supabase.com/dashboard/project/griexhozxrqtepcilfnu
- **Org**: https://supabase.com/dashboard/org/avfuewcumoqpkpynbncb
- **Plan**: Free tier
- **Role**: Основная БД для платформы агрегации цен на запчасти + RAG Memory Bank

**Ограничения Free tier:**
- 500 MB storage, 2 GB bandwidth/month
- **Проект засыпает через 7 дней без запросов** - нужен keepalive

**Таблицы (90+ таблиц):**

| Группа | Таблицы | Назначение |
|--------|---------|------------|
| **Поставщики (staging)** | `moysklad_staging`, `moba_staging`, `greenspark_staging`, `lcdstock_staging`, `orizhka_staging`, `profi_staging`, `05gsm_staging`, `liberti_staging`, `signal23_staging`, `taggsm_staging`, `memstech_staging` | Сырые данные от парсеров |
| **Номенклатура** | `*_nomenclature` (11 поставщиков) | Нормализованная номенклатура по каждому поставщику |
| **Цены** | `*_prices`, `*_current_prices` (11 поставщиков) | История и текущие цены |
| **Мастер-данные (ZIP)** | `zip_nomenclature`, `zip_current_stock`, `zip_price_history`, `zip_shops`, `zip_outlets` | Единый каталог, остатки, история цен |
| **Справочники (ZIP)** | `zip_dict_brands`, `zip_dict_models`, `zip_dict_colors`, `zip_dict_qualities`, `zip_dict_part_types`, `zip_dict_features` | Справочники брендов, моделей, цветов, качеств |
| **GSMArena** | `zip_gsmarena_raw`, `zip_gsmarena_phones` | Данные устройств с GSMArena |
| **Приложение** | `app_users`, `app_subscriptions`, `app_search_history`, `app_notification_subscriptions` | Пользователи и подписки |
| **Парсеры** | `greenspark_parser_*`, `greenspark_shop_*` | Управление парсерами |
| **Unified** | `master_unified_nomenclature`, `v_staging_normalized` | Объединённая номенклатура |

**RPC функции:**

| Функция | Назначение |
|---------|------------|
| `match_or_create_brand` | Сопоставление/создание бренда |
| `match_or_create_model` | Сопоставление/создание модели |
| `match_or_create_color` | Сопоставление/создание цвета |
| `match_and_normalize_v3` | Нормализация номенклатуры |
| `sync_gsmarena_brands/models` | Синхронизация с GSMArena |
| `get_staging_stats` | Статистика загрузки |
| `app_increment_query_counter` | Счётчик запросов приложения |

**Конфигурация:**
- Anon Key: `eyJhbG...gfPM` (хранится в `~/.memory_config.json` или env `SUPABASE_KEY`)
- Memory Bank код: `memory_bank/supabase_store.py`, `memory_bank/cli_supabase.py`

**Keepalive (защита от засыпания):**

Периодический запрос чтобы проект не засыпал:

1. **Cron на VPS** (простейший):
   ```bash
   # /etc/cron.d/supabase-keepalive
   0 */12 * * * root curl -s "https://griexhozxrqtepcilfnu.supabase.co/rest/v1/app_users?select=id&limit=1" \
     -H "apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdyaWV4aG96eHJxdGVwY2lsZm51Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkyMDc4OTMsImV4cCI6MjA4NDc4Mzg5M30.JBaMNCOMev5RuR3Rw6_b0etQ3lKHrMwtXSebDv2gfPM" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdyaWV4aG96eHJxdGVwY2lsZm51Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkyMDc4OTMsImV4cCI6MjA4NDc4Mzg5M30.JBaMNCOMev5RuR3Rw6_b0etQ3lKHrMwtXSebDv2gfPM" > /dev/null
   ```

2. **n8n workflow**: HTTP Request нода раз в 6 часов на Supabase REST API

```
Keepalive flow:

VPS cron (every 12h)
  │
  ▼
curl → https://griexhozxrqtepcilfnu.supabase.co/rest/v1/...
  │
  ▼
Supabase stays awake
```

---

## Inactive/Failed Components

These were attempted but don't work due to ISP limitations:

| Component | Location | Status | Reason |
|-----------|----------|--------|--------|
| cloudflared | Homelab | Installed, not working | ISP blocks port 7844, kills HTTP/2 tunnels |
| WireGuard | Both servers | Configured, not working | ISP kills UDP flows |

Configs remain on servers but services are stopped.

---

## Adding New Services

To expose a new service from Homelab:

1. **Homelab**: Start the service on a port (e.g. `:3000`)
2. **Homelab**: Add port to SSH tunnel in `/etc/systemd/system/ssh-tunnel.service`:
   ```
   -R 127.0.0.1:3000:localhost:3000
   ```
3. **Homelab**: Restart tunnel:
   ```bash
   systemctl daemon-reload && systemctl restart ssh-tunnel
   ```
4. **VPS**: Create Nginx config `/etc/nginx/sites-available/newservice`:
   ```nginx
   server {
       listen 80;
       server_name newservice.newlcd.ru;
       location / {
           proxy_pass http://127.0.0.1:3000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
5. **VPS**: Enable and get SSL:
   ```bash
   ln -s /etc/nginx/sites-available/newservice /etc/nginx/sites-enabled/
   nginx -t && systemctl reload nginx
   certbot --nginx -d newservice.newlcd.ru
   ```
6. **Cloudflare**: Add A record `newservice` → `155.212.221.67` (DNS only)

---

## Access Credentials

| Server | Method | Details |
|--------|--------|---------|
| VPS | SSH | `ssh root@155.212.221.67` |
| Homelab (direct) | SSH | `ssh root@192.168.31.97` (LAN only) |
| Homelab (remote) | SSH | `ssh root@155.212.221.67 -p 2222` |
| Proxmox UI | Browser | https://proxmox.newlcd.ru |
| n8n | Browser | https://n8n.newlcd.ru |

| Supabase Dashboard | Browser | https://supabase.com/dashboard/project/griexhozxrqtepcilfnu |
| Supabase API | REST | `https://griexhozxrqtepcilfnu.supabase.co/rest/v1` + anon key |

SSH authentication: key-based (public key installed on both servers).
Supabase authentication: anon key в `~/.memory_config.json`.
