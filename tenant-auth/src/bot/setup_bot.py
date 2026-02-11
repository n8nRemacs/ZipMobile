"""
Одноразовый скрипт для настройки Telegram бота ZipMobile.

Использование:
  python -m src.bot.setup_bot <MINIAPP_HTTPS_URL>

Пример:
  python -m src.bot.setup_bot https://xxxx.ngrok-free.app
"""
import sys
import httpx

BOT_TOKEN = "8060922295:AAFRg3g8JqN98rvX50LFvFOpUHPyrqd2sBs"
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def setup(miniapp_url: str):
    print(f"Setting up bot with Mini App URL: {miniapp_url}")

    # Set menu button → Mini App
    r1 = httpx.post(f"{API_BASE}/setChatMenuButton", json={
        "menu_button": {
            "type": "web_app",
            "text": "ZipMobile",
            "web_app": {"url": miniapp_url},
        }
    })
    print(f"setChatMenuButton: {r1.json()}")

    # Set bot commands
    r2 = httpx.post(f"{API_BASE}/setMyCommands", json={
        "commands": [
            {"command": "start", "description": "Открыть ZipMobile"},
        ]
    })
    print(f"setMyCommands: {r2.json()}")

    # Set bot description
    r3 = httpx.post(f"{API_BASE}/setMyDescription", json={
        "description": "ZipMobile — платформа для сервисных центров мобильных устройств. Нажмите кнопку меню чтобы начать.",
    })
    print(f"setMyDescription: {r3.json()}")

    print("\nDone! Open @zipmobile_bot in Telegram and tap the menu button.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.bot.setup_bot <MINIAPP_HTTPS_URL>")
        print("Example: python -m src.bot.setup_bot https://xxxx.ngrok-free.app")
        sys.exit(1)
    setup(sys.argv[1])
