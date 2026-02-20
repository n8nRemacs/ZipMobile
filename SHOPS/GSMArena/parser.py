#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GSMArena Parser - парсер моделей телефонов с характеристиками
https://www.gsmarena.com/

Сохраняет в PostgreSQL: zip_gsmarena_raw
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import json
import re
import os
import sys
import argparse
from datetime import datetime

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

try:
    import psycopg2
    from psycopg2.extras import Json
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    print("Warning: psycopg2 not installed, database features disabled")

# ============================================================================
# Configuration
# ============================================================================

BASE_URL = "https://www.gsmarena.com"
DELAY_MIN = 1.5
DELAY_MAX = 3.0
OUTPUT_DIR = "output"
PROXIES_FILE = "proxies.txt"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

# Database config (Supabase)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_config import get_db_config
DB_CONFIG = get_db_config()

# Target brands
TARGET_BRANDS = [
    'apple', 'samsung', 'xiaomi', 'huawei', 'honor',
    'oppo', 'vivo', 'realme', 'oneplus', 'google',
    'motorola', 'nokia', 'sony', 'lg', 'asus',
    'nothing', 'zte', 'meizu', 'lenovo', 'poco'
]


# ============================================================================
# Helper functions
# ============================================================================

def extract_number(text, pattern=r'(\d+(?:\.\d+)?)'):
    """Extract first number from text"""
    if not text:
        return None
    match = re.search(pattern, text.replace(',', ''))
    return float(match.group(1)) if match else None


def extract_year(text):
    """Extract year from announcement text"""
    if not text:
        return None
    match = re.search(r'20\d{2}', text)
    return int(match.group()) if match else None


def extract_weight_grams(text):
    """Extract weight in grams"""
    if not text:
        return None
    # "227 g" or "227g"
    match = re.search(r'(\d+(?:\.\d+)?)\s*g\b', text.lower())
    return int(float(match.group(1))) if match else None


def extract_battery_mah(text):
    """Extract battery capacity in mAh"""
    if not text:
        return None
    match = re.search(r'(\d+)\s*mah', text.lower())
    return int(match.group(1)) if match else None


def extract_price_eur(text):
    """Extract price in EUR"""
    if not text:
        return None
    match = re.search(r'(\d+(?:\.\d+)?)\s*eur', text.lower())
    return float(match.group(1)) if match else None


def extract_display_inches(text):
    """Extract display size in inches"""
    if not text:
        return None
    match = re.search(r'(\d+(?:\.\d+)?)\s*inch', text.lower())
    return float(match.group(1)) if match else None


def extract_camera_mp(text):
    """Extract main camera megapixels"""
    if not text:
        return None
    match = re.search(r'(\d+)\s*mp', text.lower())
    return match.group(1) + " MP" if match else None


# ============================================================================
# Parser Class
# ============================================================================

class GSMArenaParser:
    def __init__(self, use_db=True, cookies_file=None, use_proxy=False):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.use_db = use_db and HAS_PSYCOPG2
        self.conn = None
        self.use_proxy = use_proxy
        self.current_proxy = None
        self.proxy_switch_count = 0
        self.resume_mode = False
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Load cookies if available
        self._load_cookies(cookies_file)

        # Load proxies if requested
        if use_proxy:
            self._load_proxies()

        if self.use_db:
            self._connect_db()

    def _load_proxies(self):
        """Load working proxies from database"""
        if not HAS_PSYCOPG2:
            print("Warning: psycopg2 not installed, proxy from DB disabled")
            self.use_proxy = False
            return

        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) FROM zip_proxies WHERE status = 'working'
            """)
            count = cur.fetchone()[0]
            conn.close()

            if count > 0:
                print(f"[PROXY] Found {count} working proxies in database")
                self.current_proxy = None
                self.proxy_switch_count = 0
            else:
                print("[PROXY] No working proxies in database! Run proxy_checker.py first")
                self.use_proxy = False
        except Exception as e:
            print(f"[PROXY] Error connecting to proxy DB: {e}")
            self.use_proxy = False

    def _get_working_proxy_from_db(self):
        """Get one working proxy from database and mark it as 'used'"""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.autocommit = True
            cur = conn.cursor()

            # Get working proxy NOT banned for gsmarena, prefer least recently used
            cur.execute("""
                UPDATE zip_proxies
                SET status = 'used', last_used_at = NOW()
                WHERE proxy = (
                    SELECT proxy FROM zip_proxies
                    WHERE status = 'working'
                      AND NOT ('gsmarena' = ANY(banned_sites))
                    ORDER BY last_used_at NULLS FIRST, success_count DESC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING proxy
            """)

            row = cur.fetchone()
            conn.close()

            if row:
                return row[0]
            return None
        except Exception as e:
            print(f"[PROXY] Error getting proxy from DB: {e}")
            return None

    def _return_proxy_to_pool(self, proxy, success=True, banned=False):
        """Return proxy to pool after use"""
        if not proxy:
            return
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            conn.autocommit = True
            cur = conn.cursor()

            if success:
                # Return to working pool
                cur.execute("""
                    UPDATE zip_proxies
                    SET status = 'working', success_count = success_count + 1
                    WHERE proxy = %s
                """, (proxy,))
            elif banned:
                # Banned by this site (429) - add to banned_sites, but keep working for others
                cur.execute("""
                    UPDATE zip_proxies
                    SET banned_sites = array_append(banned_sites, %s),
                        status = CASE
                            WHEN array_length(array_append(banned_sites, %s), 1) >= 5 THEN 'banned'
                            ELSE 'working'
                        END
                    WHERE proxy = %s AND NOT (%s = ANY(banned_sites))
                """, ('gsmarena', 'gsmarena', proxy, 'gsmarena'))
                print(f"[PROXY] Marked as banned for gsmarena: {proxy}")
            else:
                # Connection error - mark as dead
                cur.execute("""
                    UPDATE zip_proxies
                    SET status = 'dead', fail_count = fail_count + 1
                    WHERE proxy = %s
                """, (proxy,))

            conn.close()
        except Exception as e:
            print(f"[PROXY] Error returning proxy: {e}")

    def _get_current_proxy(self):
        """Get current proxy dict for requests"""
        if not self.use_proxy:
            return None

        if not self.current_proxy:
            self.current_proxy = self._get_working_proxy_from_db()
            if self.current_proxy:
                print(f"[PROXY] Using: {self.current_proxy}")

        if self.current_proxy:
            return {"http": f"http://{self.current_proxy}", "https": f"http://{self.current_proxy}"}
        return None

    def _switch_proxy(self):
        """Switch to next working proxy from database"""
        # Return current proxy as failed
        if self.current_proxy:
            self._return_proxy_to_pool(self.current_proxy, success=False)

        # Get new proxy
        self.current_proxy = self._get_working_proxy_from_db()
        self.proxy_switch_count += 1

        if self.current_proxy:
            print(f"[PROXY] Switched to: {self.current_proxy}")
            # Refresh cookies every 10 switches
            if self.proxy_switch_count % 10 == 0:
                self._refresh_cookies_for_proxy()
            return True
        else:
            print("[PROXY] No more working proxies available!")
            return False

    def _refresh_cookies_for_proxy(self):
        """Refresh cookies after switching proxy - get fresh session/fingerprint"""
        try:
            from stealth_cookies import get_cookies_sync
            print(f"[COOKIES] Refreshing cookies (new fingerprint)...")
            # Get cookies directly for new fingerprint
            # The IP change comes from proxy rotation
            cookies = get_cookies_sync(headless=True, save=True)
            if cookies:
                # Clear old cookies and set new ones
                self.session.cookies.clear()
                for name, value in cookies.items():
                    if not name.startswith("__"):
                        self.session.cookies.set(name, value, domain=".gsmarena.com")
                # Update user agent if present
                user_agent = cookies.get("__user_agent__")
                if user_agent:
                    self.session.headers["User-Agent"] = user_agent
                print(f"[COOKIES] Refreshed {len(cookies)} cookies with new fingerprint")
            else:
                print("[COOKIES] Warning: Could not refresh cookies")
        except ImportError:
            print("[COOKIES] stealth_cookies not available, skipping refresh")
        except Exception as e:
            print(f"[COOKIES] Error refreshing: {e}")

    def _load_cookies(self, cookies_file=None):
        """Load cookies from file"""
        cookies_file = cookies_file or "cookies.json"
        if os.path.exists(cookies_file):
            try:
                with open(cookies_file, "r", encoding="utf-8") as f:
                    cookies = json.load(f)

                # Extract user agent if present
                user_agent = cookies.pop("__user_agent__", None)
                cookies.pop("__meta__", None)

                # Update session with cookies
                for name, value in cookies.items():
                    self.session.cookies.set(name, value, domain=".gsmarena.com")

                # Update user agent if we have one from cookies
                if user_agent:
                    self.session.headers["User-Agent"] = user_agent

                print(f"Loaded {len(cookies)} cookies from {cookies_file}")
            except Exception as e:
                print(f"Warning: Could not load cookies: {e}")

    def _connect_db(self):
        """Connect to PostgreSQL"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = False
            print(f"Connected to database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
        except Exception as e:
            print(f"Database connection failed: {e}")
            self.use_db = False

    def get_existing_models(self, brand_name):
        """Get list of already parsed models for a brand"""
        if not self.conn:
            return set()
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT model_name FROM zip_gsmarena_raw WHERE brand = %s", (brand_name,))
            return {row[0] for row in cur.fetchall()}
        except Exception as e:
            print(f"Error getting existing models: {e}")
            return set()

    def _delay(self):
        """Random delay between requests"""
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        if self.use_proxy:
            delay = delay / 2  # Shorter delay with proxies
        time.sleep(delay)

    def _get(self, url, retry_on_429=True):
        """GET request with delay and proxy support"""
        self._delay()

        max_retries = 50 if self.use_proxy else 1  # Try up to 50 proxies

        for attempt in range(max_retries):
            try:
                proxy = self._get_current_proxy() if self.use_proxy else None
                response = self.session.get(url, timeout=30, proxies=proxy)

                if response.status_code == 429:
                    print(f"429 Too Many Requests for {url}")
                    if self.use_proxy and retry_on_429:
                        # Mark as banned for gsmarena (not dead!)
                        self._return_proxy_to_pool(self.current_proxy, success=False, banned=True)
                        self.current_proxy = None
                        # Get new proxy
                        self.current_proxy = self._get_working_proxy_from_db()
                        if self.current_proxy:
                            print(f"[PROXY] Switched to: {self.current_proxy}")
                            continue  # Retry with new proxy
                    return None

                response.raise_for_status()

                # Success! Keep using this proxy (don't return to pool yet)
                # Proxy stays in 'used' status while parser is working

                return response.text

            except requests.exceptions.ProxyError as e:
                print(f"Proxy error: {e}")
                if self.use_proxy:
                    if self._switch_proxy():
                        continue
                return None

            except requests.exceptions.Timeout as e:
                print(f"Timeout: {e}")
                if self.use_proxy:
                    if self._switch_proxy():
                        continue
                return None

            except Exception as e:
                print(f"Error fetching {url}: {e}")
                if self.use_proxy:
                    if self._switch_proxy():
                        continue
                return None

        return None

    def get_brands(self):
        """Get list of all brands"""
        print("Fetching brands list...")
        html = self._get(f"{BASE_URL}/makers.php3")
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        brands = []

        for link in soup.select('div.st-text a'):
            href = link.get('href', '')
            text = link.get_text(strip=True)

            match = re.match(r'(.+?)\s*(\d+)\s*devices?', text)
            if match and '-phones-' in href:
                brand_name = match.group(1).strip()
                device_count = int(match.group(2))
                brand_code = href.replace('-phones-', '_').replace('.php', '')

                brands.append({
                    'name': brand_name,
                    'code': brand_code.split('_')[0],
                    'url': f"{BASE_URL}/{href}",
                    'device_count': device_count
                })

        print(f"Found {len(brands)} brands")
        return brands

    def get_brand_models(self, brand_url, brand_name, max_pages=50):
        """Get all models for a brand"""
        print(f"Fetching models for {brand_name}...")
        models = []
        page = 1

        brand_id_match = re.search(r'-(\d+)\.php', brand_url)
        brand_id = brand_id_match.group(1) if brand_id_match else None
        brand_slug = brand_url.split('/')[-1].replace(f'-{brand_id}.php', '') if brand_id else None

        while page <= max_pages:
            if page == 1:
                url = brand_url
            else:
                if brand_slug and brand_id:
                    url = f"{BASE_URL}/{brand_slug}-f-{brand_id}-0-p{page}.php"
                else:
                    break

            html = self._get(url)
            if not html:
                break

            soup = BeautifulSoup(html, 'html.parser')

            found_on_page = 0
            for item in soup.select('div.makers ul li'):
                link = item.select_one('a')
                if not link:
                    continue

                href = link.get('href', '')
                name_elem = link.select_one('span')
                img_elem = link.select_one('img')

                if name_elem and href:
                    model_name = name_elem.get_text(strip=True)
                    brief_specs = ''
                    if img_elem:
                        brief_specs = img_elem.get('title', '') or img_elem.get('alt', '')

                    # Extract GSMArena ID from URL
                    gsm_id_match = re.search(r'-(\d+)\.php', href)
                    gsm_id = gsm_id_match.group(1) if gsm_id_match else None

                    models.append({
                        'brand': brand_name,
                        'name': model_name,
                        'url': f"{BASE_URL}/{href}",
                        'brief_specs': brief_specs,
                        'gsmarena_id': gsm_id
                    })
                    found_on_page += 1

            print(f"  Page {page}: {found_on_page} models")

            if found_on_page == 0:
                break

            nav_pages = soup.select('div.nav-pages a')
            has_next = any(f'p{page+1}' in a.get('href', '') for a in nav_pages)
            if not has_next:
                break

            page += 1

        print(f"Total models for {brand_name}: {len(models)}")
        return models

    def get_model_specs(self, model_url, model_name):
        """Get detailed specifications for a model"""
        html = self._get(model_url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')
        specs = {
            'name': model_name,
            'url': model_url,
            'parsed_at': datetime.now().isoformat()
        }

        # Parse specs table
        for table in soup.select('table[cellspacing="0"]'):
            category = None

            for row in table.select('tr'):
                th = row.select_one('th')
                if th and th.get('rowspan'):
                    category = th.get_text(strip=True).lower().replace(' ', '_')
                    if category not in specs:
                        specs[category] = {}

                tds = row.select('td')
                if len(tds) >= 2 and category:
                    param_name = tds[0].get_text(strip=True).lower().replace(' ', '_')
                    param_value = tds[1].get_text(strip=True)
                    param_value = re.sub(r'\s+', ' ', param_value)

                    if param_name and param_value:
                        specs[category][param_name] = param_value

        # Image
        img = soup.select_one('div.specs-photo-main img')
        if img:
            specs['image_url'] = img.get('src', '')

        # Price
        price_elem = soup.select_one('td[data-spec="price"]')
        if price_elem:
            specs['price'] = price_elem.get_text(strip=True)

        return specs

    def specs_to_db_row(self, specs, brand, gsmarena_id=None):
        """Convert parsed specs to database row"""
        row = {
            'brand': brand,
            'model_name': specs.get('name', ''),
            'model_url': specs.get('url', ''),
            'image_url': specs.get('image_url', ''),
            'gsmarena_id': gsmarena_id,
            'specs_json': specs,
        }

        # Launch
        launch = specs.get('launch', {})
        row['announced'] = launch.get('announced', '')
        row['release_status'] = launch.get('status', '')
        row['release_year'] = extract_year(launch.get('announced', ''))

        # Body
        body = specs.get('body', {})
        row['dimensions'] = body.get('dimensions', '')
        row['weight'] = body.get('weight', '')
        row['weight_grams'] = extract_weight_grams(body.get('weight', ''))
        row['build'] = body.get('build', '')
        row['sim'] = body.get('sim', '')
        # IP rating might be in body
        ip_match = re.search(r'IP\d+', str(body))
        row['ip_rating'] = ip_match.group() if ip_match else None

        # Display
        display = specs.get('display', {})
        row['display_type'] = display.get('type', '')
        row['display_size'] = display.get('size', '')
        row['display_size_inches'] = extract_display_inches(display.get('size', ''))
        row['display_resolution'] = display.get('resolution', '')
        row['display_protection'] = display.get('protection', '')
        # Extract refresh rate from type
        hz_match = re.search(r'(\d+)\s*Hz', display.get('type', ''))
        row['refresh_rate'] = f"{hz_match.group(1)}Hz" if hz_match else None

        # Platform
        platform = specs.get('platform', {})
        row['os'] = platform.get('os', '')
        row['chipset'] = platform.get('chipset', '')
        row['cpu'] = platform.get('cpu', '')
        row['gpu'] = platform.get('gpu', '')

        # Memory
        memory = specs.get('memory', {})
        row['card_slot'] = memory.get('card_slot', '')
        internal = memory.get('internal', '')
        row['storage'] = internal
        # Extract RAM
        ram_match = re.search(r'(\d+)\s*GB\s*RAM', internal)
        row['ram'] = f"{ram_match.group(1)} GB" if ram_match else None

        # Camera
        main_cam = specs.get('main_camera', {})
        row['main_camera_setup'] = main_cam.get('single', main_cam.get('dual', main_cam.get('triple', main_cam.get('quad', ''))))
        row['main_camera_mp'] = extract_camera_mp(row['main_camera_setup'])
        row['main_camera_features'] = main_cam.get('features', '')
        row['main_camera_video'] = main_cam.get('video', '')

        selfie = specs.get('selfie_camera', {})
        row['selfie_camera_setup'] = selfie.get('single', selfie.get('dual', ''))
        row['selfie_camera_mp'] = extract_camera_mp(row['selfie_camera_setup'])
        row['selfie_camera_video'] = selfie.get('video', '')

        # Battery
        battery = specs.get('battery', {})
        row['battery_type'] = battery.get('type', '')
        row['battery_capacity'] = battery.get('type', '')
        row['battery_capacity_mah'] = extract_battery_mah(battery.get('type', ''))
        charging = battery.get('charging', '')
        row['charging_wired'] = charging
        # Extract wireless
        if 'wireless' in charging.lower():
            wireless_match = re.search(r'(\d+W)\s*wireless', charging.lower())
            row['charging_wireless'] = wireless_match.group(1) if wireless_match else 'Yes'
        else:
            row['charging_wireless'] = None

        # Network
        network = specs.get('network', {})
        row['network_technology'] = network.get('technology', '')
        row['network_2g'] = network.get('2g_bands', '')
        row['network_3g'] = network.get('3g_bands', '')
        row['network_4g'] = network.get('4g_bands', '')
        row['network_5g'] = network.get('5g_bands', '')

        # Comms
        comms = specs.get('comms', {})
        row['wlan'] = comms.get('wlan', '')
        row['bluetooth'] = comms.get('bluetooth', '')
        row['nfc'] = comms.get('nfc', '')
        row['gps'] = comms.get('positioning', '')
        row['usb'] = comms.get('usb', '')
        row['radio'] = comms.get('radio', '')

        # Sound
        sound = specs.get('sound', {})
        row['loudspeaker'] = sound.get('loudspeaker', '')
        row['audio_jack'] = sound.get('3.5mm_jack', '')

        # Features
        features = specs.get('features', {})
        row['sensors'] = features.get('sensors', '')

        # Misc
        misc = specs.get('misc', {})
        row['colors'] = misc.get('colors', '')
        row['models_list'] = misc.get('models', '')
        row['price'] = misc.get('price', specs.get('price', ''))
        row['price_eur'] = extract_price_eur(row['price'])

        # EU Label
        eu = specs.get('eu_label', {})
        row['eu_energy_class'] = eu.get('energy', '')
        row['eu_battery_endurance'] = eu.get('battery', '')
        row['eu_repairability'] = eu.get('repairability', '')

        return row

    def save_to_db(self, row):
        """Save row to database"""
        if not self.use_db or not self.conn:
            return False

        cur = self.conn.cursor()

        # Upsert query
        sql = """
            INSERT INTO zip_gsmarena_raw (
                brand, model_name, model_url, image_url, gsmarena_id,
                announced, release_status, release_year,
                dimensions, weight, weight_grams, build, sim, ip_rating,
                display_type, display_size, display_size_inches, display_resolution, display_protection, refresh_rate,
                os, chipset, cpu, gpu,
                ram, storage, card_slot,
                main_camera_mp, main_camera_setup, main_camera_features, main_camera_video,
                selfie_camera_mp, selfie_camera_setup, selfie_camera_video,
                battery_capacity, battery_capacity_mah, battery_type, charging_wired, charging_wireless,
                network_technology, network_2g, network_3g, network_4g, network_5g,
                wlan, bluetooth, nfc, gps, usb, radio,
                loudspeaker, audio_jack, sensors,
                colors, models_list, price, price_eur,
                eu_energy_class, eu_battery_endurance, eu_repairability,
                specs_json, parsed_at, updated_at
            ) VALUES (
                %(brand)s, %(model_name)s, %(model_url)s, %(image_url)s, %(gsmarena_id)s,
                %(announced)s, %(release_status)s, %(release_year)s,
                %(dimensions)s, %(weight)s, %(weight_grams)s, %(build)s, %(sim)s, %(ip_rating)s,
                %(display_type)s, %(display_size)s, %(display_size_inches)s, %(display_resolution)s, %(display_protection)s, %(refresh_rate)s,
                %(os)s, %(chipset)s, %(cpu)s, %(gpu)s,
                %(ram)s, %(storage)s, %(card_slot)s,
                %(main_camera_mp)s, %(main_camera_setup)s, %(main_camera_features)s, %(main_camera_video)s,
                %(selfie_camera_mp)s, %(selfie_camera_setup)s, %(selfie_camera_video)s,
                %(battery_capacity)s, %(battery_capacity_mah)s, %(battery_type)s, %(charging_wired)s, %(charging_wireless)s,
                %(network_technology)s, %(network_2g)s, %(network_3g)s, %(network_4g)s, %(network_5g)s,
                %(wlan)s, %(bluetooth)s, %(nfc)s, %(gps)s, %(usb)s, %(radio)s,
                %(loudspeaker)s, %(audio_jack)s, %(sensors)s,
                %(colors)s, %(models_list)s, %(price)s, %(price_eur)s,
                %(eu_energy_class)s, %(eu_battery_endurance)s, %(eu_repairability)s,
                %(specs_json)s, NOW(), NOW()
            )
            ON CONFLICT (brand, model_name) DO UPDATE SET
                model_url = EXCLUDED.model_url,
                image_url = EXCLUDED.image_url,
                announced = EXCLUDED.announced,
                release_status = EXCLUDED.release_status,
                release_year = EXCLUDED.release_year,
                dimensions = EXCLUDED.dimensions,
                weight = EXCLUDED.weight,
                weight_grams = EXCLUDED.weight_grams,
                display_type = EXCLUDED.display_type,
                display_size = EXCLUDED.display_size,
                display_size_inches = EXCLUDED.display_size_inches,
                chipset = EXCLUDED.chipset,
                battery_capacity_mah = EXCLUDED.battery_capacity_mah,
                colors = EXCLUDED.colors,
                price = EXCLUDED.price,
                price_eur = EXCLUDED.price_eur,
                specs_json = EXCLUDED.specs_json,
                updated_at = NOW()
        """

        try:
            # Convert specs_json to Json type
            row['specs_json'] = Json(row['specs_json'])
            cur.execute(sql, row)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Database error: {e}")
            self.conn.rollback()
            return False

    def parse_brand(self, brand_code, max_models=None, save_json=True):
        """Parse all models for a brand"""
        brands = self.get_brands()

        brand = next((b for b in brands if b['code'].lower() == brand_code.lower()), None)
        if not brand:
            print(f"Brand '{brand_code}' not found")
            return []

        models = self.get_brand_models(brand['url'], brand['name'])

        # Resume mode: filter out already parsed models
        if self.resume_mode and self.use_db:
            existing = self.get_existing_models(brand['name'])
            original_count = len(models)
            models = [m for m in models if m['name'] not in existing]
            skipped = original_count - len(models)
            if skipped > 0:
                print(f"Resume mode: skipping {skipped} already parsed models, {len(models)} remaining")

        if max_models:
            models = models[:max_models]

        results = []
        saved_count = 0

        for i, model in enumerate(models):
            print(f"[{i+1}/{len(models)}] Parsing {model['name']}...")

            specs = self.get_model_specs(model['url'], model['name'])
            if not specs:
                continue

            specs['brand'] = brand['name']
            results.append(specs)

            # Save to database
            if self.use_db:
                row = self.specs_to_db_row(specs, brand['name'], model.get('gsmarena_id'))
                if self.save_to_db(row):
                    saved_count += 1

            # Save intermediate results
            if save_json and (i + 1) % 20 == 0:
                self._save_json(results, f"{brand_code}_partial")
                print(f"  Saved {saved_count} to DB, {len(results)} to JSON")

        # Save final results
        if save_json:
            self._save_json(results, brand_code)

        print(f"\nCompleted {brand['name']}: {len(results)} models parsed, {saved_count} saved to DB")
        return results

    def _save_json(self, results, name):
        """Save results to JSON file"""
        filepath = os.path.join(OUTPUT_DIR, f"{name}_{datetime.now().strftime('%Y%m%d')}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(results)} models to {filepath}")

    def parse_all_brands(self, max_models_per_brand=None):
        """Parse all target brands"""
        total = 0
        for brand_code in TARGET_BRANDS:
            print(f"\n{'='*60}")
            print(f"PARSING: {brand_code.upper()}")
            print('='*60)

            results = self.parse_brand(brand_code, max_models_per_brand)
            total += len(results)

        print(f"\n{'='*60}")
        print(f"TOTAL: {total} models parsed")
        print('='*60)

    def close(self):
        """Close database connection and release proxy"""
        # Release proxy back to pool
        if self.use_proxy and self.current_proxy:
            self._return_proxy_to_pool(self.current_proxy, success=True)
            print(f"[PROXY] Released: {self.current_proxy}")
            self.current_proxy = None

        if self.conn:
            self.conn.close()
            print("Database connection closed")


# ============================================================================
# Main
# ============================================================================

def main():
    parser_args = argparse.ArgumentParser(description='GSMArena Parser')
    parser_args.add_argument('--brand', '-b', help='Parse specific brand (e.g., apple, samsung)')
    parser_args.add_argument('--all', '-a', action='store_true', help='Parse all target brands')
    parser_args.add_argument('--max', '-m', type=int, help='Max models per brand')
    parser_args.add_argument('--no-db', action='store_true', help='Disable database saving')
    parser_args.add_argument('--list-brands', '-l', action='store_true', help='List all available brands')
    parser_args.add_argument('--proxy', '-p', action='store_true', help='Use proxy rotation (requires proxies.txt)')
    parser_args.add_argument('--resume', '-r', action='store_true', help='Resume: skip already parsed models')

    args = parser_args.parse_args()

    gsm_parser = GSMArenaParser(use_db=not args.no_db, use_proxy=args.proxy)
    gsm_parser.resume_mode = args.resume

    try:
        if args.list_brands:
            brands = gsm_parser.get_brands()
            print("\nAvailable brands:")
            for b in sorted(brands, key=lambda x: x['device_count'], reverse=True)[:30]:
                print(f"  {b['code']:15} {b['name']:20} ({b['device_count']} devices)")

        elif args.all:
            gsm_parser.parse_all_brands(args.max)

        elif args.brand:
            gsm_parser.parse_brand(args.brand, args.max)

        else:
            # Default: test with Apple, 5 models
            print("GSMArena Parser - Test Mode")
            print("="*60)
            print("Use --help for options")
            print("Running test: Apple, 5 models\n")
            gsm_parser.parse_brand('apple', max_models=5)

    finally:
        gsm_parser.close()


if __name__ == '__main__':
    main()
