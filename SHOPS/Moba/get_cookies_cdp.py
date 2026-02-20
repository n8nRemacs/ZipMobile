"""
Get cookies via Chrome DevTools Protocol
"""
import json
import websocket

WS_URL = "ws://localhost:9222/devtools/page/18"  # moba.ru page
OUTPUT_FILE = "moba_cookies.json"


def get_cookies():
    print(f"[*] Connecting to {WS_URL}...")
    ws = websocket.create_connection(WS_URL)

    # Get all cookies for the domain
    cmd = {
        "id": 1,
        "method": "Network.getCookies",
        "params": {"urls": ["https://moba.ru/"]}
    }

    ws.send(json.dumps(cmd))
    response = json.loads(ws.recv())

    ws.close()

    if "result" in response:
        cookies = response["result"]["cookies"]
        print(f"[+] Got {len(cookies)} cookies:\n")

        cookie_dict = {}
        for c in cookies:
            name = c["name"]
            value = c["value"]
            cookie_dict[name] = value
            print(f"  {name}: {value[:50]}{'...' if len(value) > 50 else ''}")

        return cookie_dict
    else:
        print(f"[!] Error: {response}")
        return {}


if __name__ == "__main__":
    cookies = get_cookies()

    if cookies:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Saved to {OUTPUT_FILE}")

        # Create cookie string
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        print(f"\n[*] Cookie string for requests:\n{cookie_str}")
