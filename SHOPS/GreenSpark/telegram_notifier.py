"""
Telegram уведомления для парсера GreenSpark
"""
import os
import httpx
from datetime import datetime
from typing import Optional, Dict

# Конфигурация (переопределяется через env или напрямую)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8212954323:AAHW3wdM1z76pLC7RhUZbjd4b2OAfXJU7Kc")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "6416413182")

# Эмодзи для статусов
EMOJI = {
    "start": "\U0001F680",      # ракета
    "success": "\u2705",        # зелёная галка
    "warning": "\u26A0\uFE0F",  # предупреждение
    "error": "\u274C",          # красный крест
    "ban": "\U0001F6AB",        # запрет
    "wait": "\u23F3",           # песочные часы
    "switch": "\U0001F504",     # стрелки
    "stats": "\U0001F4CA",      # графики
    "server": "\U0001F5A5\uFE0F", # компьютер
    "city": "\U0001F3D9\uFE0F",  # город
}


class TelegramNotifier:
    """Отправка уведомлений в Telegram"""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            print("[TG] Telegram не настроен (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """Отправить сообщение в Telegram"""
        if not self.enabled:
            print(f"[TG] (disabled) {message[:100]}...")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            response = httpx.post(url, json={
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }, timeout=10)

            if response.status_code == 200:
                return True
            else:
                print(f"[TG] Ошибка: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"[TG] Исключение: {e}")
            return False

    # === Уведомления для парсера ===

    def notify_start(self, server_name: str, ip: str = None, cities_count: int = 0):
        """Уведомление о запуске парсера"""
        msg = f"""{EMOJI['start']} <b>Парсер GreenSpark запущен</b>

{EMOJI['server']} Сервер: <code>{server_name}</code>
{EMOJI['city']} Городов в очереди: {cities_count}
"""
        if ip:
            msg += f"\U0001F310 IP: <code>{ip}</code>\n"
        msg += f"\u23F0 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        self.send(msg)

    def notify_ip_switch(self, server_name: str, old_ip: str, new_ip: str,
                         reason: str, products_parsed: int, total_products: int):
        """Уведомление о смене IP"""
        msg = f"""{EMOJI['switch']} <b>Смена IP</b>

{EMOJI['server']} Сервер: <code>{server_name}</code>
\U0001F6AB Старый IP: <code>{old_ip}</code>
\u2705 Новый IP: <code>{new_ip}</code>
\U0001F4DD Причина: {reason}

{EMOJI['stats']} <b>Статистика:</b>
\u2022 Спарсено за сессию: {products_parsed}
\u2022 Всего спарсено: {total_products}
\u23F0 {datetime.now().strftime('%H:%M:%S')}"""

        self.send(msg)

    def notify_server_switch(self, from_server: str, to_server: str,
                             from_ip: str, to_ip: str,
                             reason: str, products_parsed: int,
                             total_products: int, current_city: str = None):
        """Уведомление о смене сервера"""
        msg = f"""{EMOJI['switch']} <b>Смена сервера</b>

\U0001F6AB Старый: <code>{from_server}</code> ({from_ip})
\u2705 Новый: <code>{to_server}</code> ({to_ip})
\U0001F4DD Причина: {reason}
"""
        if current_city:
            msg += f"{EMOJI['city']} Город: {current_city}\n"

        msg += f"""
{EMOJI['stats']} <b>Статистика:</b>
\u2022 Спарсено за сессию: {products_parsed}
\u2022 Всего спарсено: {total_products}
\u23F0 {datetime.now().strftime('%H:%M:%S')}"""

        self.send(msg)

    def notify_ban(self, server_name: str, ip: str, reason: str,
                   products_session: int, total_products: int,
                   cities_done: int, cities_total: int,
                   current_city: str = None):
        """Уведомление о бане сервера/IP"""
        msg = f"""{EMOJI['ban']} <b>БАН СЕРВЕРА</b>

{EMOJI['server']} Сервер: <code>{server_name}</code>
\U0001F310 IP: <code>{ip}</code>
\U0001F4DD Причина: {reason}
"""
        if current_city:
            msg += f"{EMOJI['city']} Город: {current_city}\n"

        msg += f"""
{EMOJI['stats']} <b>Статистика:</b>
\u2022 Спарсено за сессию: <b>{products_session}</b>
\u2022 Всего товаров: <b>{total_products}</b>
\u2022 Городов: {cities_done}/{cities_total}
\u23F0 {datetime.now().strftime('%H:%M:%S')}"""

        self.send(msg)

    def notify_all_banned(self, servers: list, wait_minutes: int,
                          total_products: int, cities_done: int, cities_total: int):
        """Уведомление о бане всех серверов"""
        servers_list = "\n".join([f"\u2022 {s['name']} ({s['ip']})" for s in servers])

        msg = f"""{EMOJI['error']} <b>ВСЕ СЕРВЕРЫ ЗАБАНЕНЫ</b>

{EMOJI['server']} <b>Серверы:</b>
{servers_list}

{EMOJI['wait']} Ожидание: <b>{wait_minutes} минут</b>
\u23F0 Возобновление: {(datetime.now().replace(second=0, microsecond=0).__class__(datetime.now().year, datetime.now().month, datetime.now().day, datetime.now().hour, datetime.now().minute) + __import__('datetime').timedelta(minutes=wait_minutes)).strftime('%H:%M')}

{EMOJI['stats']} <b>Статистика:</b>
\u2022 Всего товаров: <b>{total_products}</b>
\u2022 Городов: {cities_done}/{cities_total}"""

        self.send(msg)

    def notify_resume(self, server_name: str, ip: str, success: bool,
                      total_products: int, cities_done: int, cities_total: int,
                      wait_time_was: int, next_wait_time: int = None):
        """Уведомление о возобновлении после ожидания"""
        if success:
            msg = f"""{EMOJI['success']} <b>ПАРСИНГ ВОЗОБНОВЛЁН</b>

{EMOJI['server']} Сервер: <code>{server_name}</code>
\U0001F310 IP: <code>{ip}</code>
{EMOJI['wait']} Ожидали: {wait_time_was} мин

{EMOJI['stats']} <b>Статистика:</b>
\u2022 Всего товаров: <b>{total_products}</b>
\u2022 Городов: {cities_done}/{cities_total}
\u23F0 {datetime.now().strftime('%H:%M:%S')}"""
        else:
            msg = f"""{EMOJI['warning']} <b>НЕ УДАЛОСЬ ВОЗОБНОВИТЬ</b>

{EMOJI['server']} Сервер: <code>{server_name}</code>
\U0001F310 IP: <code>{ip}</code>
{EMOJI['wait']} Ожидали: {wait_time_was} мин
\U000023F3 Следующее ожидание: {next_wait_time} мин

{EMOJI['stats']} <b>Статистика:</b>
\u2022 Всего товаров: <b>{total_products}</b>
\u2022 Городов: {cities_done}/{cities_total}"""

        self.send(msg)

    def notify_city_complete(self, city_name: str, products: int,
                             cities_done: int, cities_total: int):
        """Уведомление о завершении города"""
        msg = f"""{EMOJI['success']} <b>Город завершён</b>

{EMOJI['city']} {city_name}: <b>{products}</b> товаров
\U0001F4CA Прогресс: {cities_done}/{cities_total} городов"""

        self.send(msg)

    def notify_complete(self, total_products: int, cities_done: int,
                        duration_minutes: int, errors: int = 0):
        """Уведомление о завершении всего парсинга"""
        hours = duration_minutes // 60
        mins = duration_minutes % 60

        msg = f"""{EMOJI['success']} <b>ПАРСИНГ ЗАВЕРШЁН</b>

{EMOJI['stats']} <b>Итого:</b>
\u2022 Товаров: <b>{total_products}</b>
\u2022 Городов: <b>{cities_done}</b>
\u2022 Ошибок: {errors}
\u23F1 Время: {hours}ч {mins}м

\u23F0 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

        self.send(msg)

    def notify_error(self, error: str, server_name: str = None,
                     total_products: int = 0):
        """Уведомление о критической ошибке"""
        msg = f"""{EMOJI['error']} <b>КРИТИЧЕСКАЯ ОШИБКА</b>

\U0001F4DD {error[:500]}
"""
        if server_name:
            msg += f"{EMOJI['server']} Сервер: <code>{server_name}</code>\n"
        if total_products:
            msg += f"{EMOJI['stats']} Спарсено: {total_products}\n"
        msg += f"\u23F0 {datetime.now().strftime('%H:%M:%S')}"

        self.send(msg)


# Глобальный экземпляр
_notifier = None

def get_notifier() -> TelegramNotifier:
    """Получить глобальный экземпляр нотификатора"""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier


# === CLI для тестирования ===
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Использование: python telegram_notifier.py <test_message>")
        print("Или: python telegram_notifier.py --test")
        sys.exit(1)

    notifier = TelegramNotifier()

    if sys.argv[1] == "--test":
        notifier.notify_start("test-server", "1.2.3.4", 60)
        print("Тестовое сообщение отправлено")
    else:
        message = " ".join(sys.argv[1:])
        notifier.send(message)
        print("Сообщение отправлено")
