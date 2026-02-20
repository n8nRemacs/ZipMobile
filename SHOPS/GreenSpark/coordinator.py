"""
Координатор парсеров GreenSpark
PostgreSQL в режиме Redis (LISTEN/NOTIFY)

Логика эстафеты:
1. Сервер берёт город из очереди
2. Парсит, сохраняет прогресс после каждой страницы
3. При бане — уведомляет другой сервер через NOTIFY
4. Другой сервер продолжает с того же места
"""

import os
import json
import select
import subprocess
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple


# Конфигурация БД
DB_HOST = os.environ.get("DB_HOST", "85.198.98.104")
DB_PORT = int(os.environ.get("DB_PORT", 5433))
DB_NAME = os.environ.get("DB_NAME", "db_greenspark")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "Mi31415926pSss!")

# Имя текущего сервера (задаётся через env или аргумент)
SERVER_NAME = os.environ.get("PARSER_SERVER_NAME", "server-a")

NOTIFY_CHANNEL = "parser_events"


def get_db():
    """Подключение к БД"""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode="require"
    )


def get_listen_connection():
    """Подключение для LISTEN (нужен autocommit)"""
    conn = get_db()
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


class ParserCoordinator:
    """Координатор парсеров через PostgreSQL LISTEN/NOTIFY"""

    def __init__(self, server_name: str = SERVER_NAME):
        self.server_name = server_name
        self.conn = get_db()
        self.listen_conn = None

    def register_server(self, ssh_command: str = None):
        """Регистрация сервера в БД"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO parser_servers (name, ssh_command, status, last_heartbeat)
                VALUES (%s, %s, 'idle', NOW())
                ON CONFLICT (name) DO UPDATE SET
                    ssh_command = COALESCE(EXCLUDED.ssh_command, parser_servers.ssh_command),
                    last_heartbeat = NOW()
            """, (self.server_name, ssh_command))
            self.conn.commit()
        print(f"[COORD] Сервер '{self.server_name}' зарегистрирован")

    def take_city(self) -> Optional[Tuple[str, int]]:
        """Взять город из очереди (атомарно)"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM take_city_from_queue(%s)", (self.server_name,))
            row = cur.fetchone()
            self.conn.commit()
            if row and row[0]:
                print(f"[COORD] Взят город: {row[0]} (id={row[1]})")
                return row[0], row[1]
            return None

    def on_banned(self, ban_minutes: int = 18):
        """Вызывается при бане — уведомляет другие серверы"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT on_server_banned(%s, %s)", (self.server_name, ban_minutes))
            self.conn.commit()
        print(f"[COORD] Сервер забанен на {ban_minutes} мин, уведомление отправлено")

    def complete_city(self, city: str):
        """Пометить город как завершённый"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE parser_queue
                SET status = 'done', completed_at = NOW()
                WHERE city = %s AND assigned_to = %s
            """, (city, self.server_name))
            cur.execute("""
                UPDATE parser_servers
                SET status = 'idle', current_city = NULL, last_heartbeat = NOW()
                WHERE name = %s
            """, (self.server_name,))
            self.conn.commit()
        print(f"[COORD] Город {city} завершён")

    def save_progress(self, city: str, category: str, page: int, total_pages: int, products: int):
        """Сохранить прогресс парсинга категории"""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT save_category_progress(%s, %s, %s, %s, %s, %s)",
                (city, category, page, total_pages, products, self.server_name)
            )
            self.conn.commit()

    def get_progress(self, city: str) -> Dict[str, Dict]:
        """Получить прогресс для города (какие категории уже спарсены)"""
        with self.conn.cursor() as cur:
            cur.execute("SELECT * FROM get_city_progress(%s)", (city,))
            rows = cur.fetchall()
            return {
                row[0]: {  # category_slug
                    "current_page": row[1],
                    "total_pages": row[2],
                    "status": row[3]
                }
                for row in rows
            }

    def mark_category_done(self, city: str, category: str):
        """Пометить категорию как завершённую"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE parser_progress
                SET status = 'done', updated_at = NOW()
                WHERE city = %s AND category_slug = %s
            """, (city, category))
            self.conn.commit()

    def heartbeat(self):
        """Обновить heartbeat сервера"""
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE parser_servers
                SET last_heartbeat = NOW()
                WHERE name = %s
            """, (self.server_name,))
            self.conn.commit()

    def get_other_server(self) -> Optional[Dict]:
        """Получить информацию о другом сервере"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT name, ssh_command, status, banned_until
                FROM parser_servers
                WHERE name != %s
                LIMIT 1
            """, (self.server_name,))
            row = cur.fetchone()
            if row:
                return {
                    "name": row[0],
                    "ssh_command": row[1],
                    "status": row[2],
                    "banned_until": row[3]
                }
            return None

    def trigger_other_server(self):
        """Запустить парсер на другом сервере через SSH"""
        other = self.get_other_server()
        if not other:
            print("[COORD] Другой сервер не найден")
            return False

        if other["status"] == "banned" and other["banned_until"]:
            if other["banned_until"] > datetime.now():
                print(f"[COORD] Сервер {other['name']} ещё забанен до {other['banned_until']}")
                return False

        if not other["ssh_command"]:
            print(f"[COORD] SSH команда для {other['name']} не настроена")
            return False

        print(f"[COORD] Запуск парсера на {other['name']}...")
        try:
            # Запускаем асинхронно (не ждём завершения)
            subprocess.Popen(
                other["ssh_command"],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"[COORD] Команда отправлена: {other['ssh_command']}")
            return True
        except Exception as e:
            print(f"[COORD] Ошибка запуска: {e}")
            return False

    def listen_for_events(self, callback):
        """Слушать события через LISTEN/NOTIFY"""
        self.listen_conn = get_listen_connection()
        with self.listen_conn.cursor() as cur:
            cur.execute(f"LISTEN {NOTIFY_CHANNEL}")

        print(f"[COORD] Слушаем канал {NOTIFY_CHANNEL}...")

        while True:
            if select.select([self.listen_conn], [], [], 5.0) == ([], [], []):
                # Таймаут — отправляем heartbeat
                self.heartbeat()
                continue

            self.listen_conn.poll()
            while self.listen_conn.notifies:
                notify = self.listen_conn.notifies.pop(0)
                try:
                    payload = json.loads(notify.payload)
                    print(f"[COORD] Событие: {payload}")
                    callback(payload)
                except json.JSONDecodeError:
                    print(f"[COORD] Неверный payload: {notify.payload}")

    def add_cities_to_queue(self, cities: List[Dict]):
        """Добавить города в очередь парсинга"""
        with self.conn.cursor() as cur:
            for city in cities:
                cur.execute("""
                    INSERT INTO parser_queue (city, city_id, priority, status)
                    VALUES (%s, %s, %s, 'pending')
                    ON CONFLICT DO NOTHING
                """, (city["name"], city.get("id"), city.get("priority", 0)))
            self.conn.commit()
        print(f"[COORD] Добавлено {len(cities)} городов в очередь")

    def get_queue_status(self) -> Dict:
        """Статус очереди"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT status, COUNT(*)
                FROM parser_queue
                GROUP BY status
            """)
            status = dict(cur.fetchall())

            cur.execute("""
                SELECT name, status, current_city, banned_until
                FROM parser_servers
            """)
            servers = [
                {"name": r[0], "status": r[1], "city": r[2], "banned_until": str(r[3]) if r[3] else None}
                for r in cur.fetchall()
            ]

            return {
                "queue": status,
                "servers": servers
            }

    def close(self):
        """Закрыть соединения"""
        if self.conn:
            self.conn.close()
        if self.listen_conn:
            self.listen_conn.close()


# === CLI ===
if __name__ == "__main__":
    import argparse

    arg_parser = argparse.ArgumentParser(description="Координатор парсеров GreenSpark")
    arg_parser.add_argument("--server", default=SERVER_NAME, help="Имя сервера")
    arg_parser.add_argument("--register", action="store_true", help="Зарегистрировать сервер")
    arg_parser.add_argument("--ssh-command", help="SSH команда для запуска парсера")
    arg_parser.add_argument("--status", action="store_true", help="Показать статус очереди")
    arg_parser.add_argument("--add-cities", action="store_true", help="Добавить все города в очередь")
    arg_parser.add_argument("--listen", action="store_true", help="Слушать события и запускать парсер")

    args = arg_parser.parse_args()

    coord = ParserCoordinator(args.server)

    if args.register:
        coord.register_server(args.ssh_command)

    elif args.status:
        status = coord.get_queue_status()
        print("\n=== Статус очереди ===")
        for k, v in status["queue"].items():
            print(f"  {k}: {v}")
        print("\n=== Серверы ===")
        for s in status["servers"]:
            print(f"  {s['name']}: {s['status']} | город: {s['city']} | бан до: {s['banned_until']}")

    elif args.add_cities:
        # Загружаем города из файла
        import json
        with open("data/greenspark_cities.json", "r", encoding="utf-8") as f:
            cities_data = json.load(f)
        cities = [{"name": c["name"], "id": c["set_city"]} for c in cities_data]
        coord.add_cities_to_queue(cities)

    elif args.listen:
        def on_event(payload):
            if payload.get("event") == "server_banned":
                banned_server = payload.get("server")
                if banned_server != args.server:
                    print(f"[COORD] Сервер {banned_server} забанен, берём эстафету...")
                    # Здесь запускаем парсер
                    subprocess.Popen(
                        f"python parser.py --server {args.server} --resume",
                        shell=True
                    )

        coord.listen_for_events(on_event)

    coord.close()
