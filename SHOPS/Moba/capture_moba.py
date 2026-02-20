"""
Capture moba.ru cookies from Chrome via Frida
"""
import frida
import sys
import json
import re
from pathlib import Path

COOKIES_FILE = "moba_cookies.json"
captured_cookies = {}

def on_message(message, data):
    global captured_cookies

    if message['type'] == 'send':
        payload = message['payload']
        print(payload)

        # Parse cookies from output
        if "[COOKIES]" in payload:
            cookie_str = payload.replace("[COOKIES]", "").strip()
            if cookie_str:
                for part in cookie_str.split(";"):
                    if "=" in part:
                        name, value = part.strip().split("=", 1)
                        captured_cookies[name.strip()] = value.strip()
                print(f"\n[+] Captured {len(captured_cookies)} cookies")

        elif "[COOKIE SET]" in payload or "[VALUE]" in payload:
            if "[VALUE]" in payload:
                cookie_part = payload.replace("[VALUE]", "").strip()
                if "=" in cookie_part:
                    # Format: "name=value; path=/; ..."
                    first_part = cookie_part.split(";")[0]
                    if "=" in first_part:
                        name, value = first_part.split("=", 1)
                        captured_cookies[name.strip()] = value.strip()

    elif message['type'] == 'error':
        print(f"[ERROR] {message['stack']}")


def main():
    global captured_cookies

    script_path = Path(__file__).parent / "capture_cookies.js"
    script_code = script_path.read_text(encoding="utf-8")

    print("[*] Looking for Chrome process...")

    device = frida.get_usb_device()

    # Try to attach to existing Chrome or spawn new
    try:
        # Check if Chrome is running
        for proc in device.enumerate_processes():
            if "chrome" in proc.name.lower():
                print(f"[*] Found Chrome: {proc.name} (PID: {proc.pid})")

        session = device.attach("com.android.chrome")
        print("[+] Attached to Chrome")
    except:
        print("[*] Spawning Chrome...")
        pid = device.spawn(["com.android.chrome"])
        session = device.attach(pid)
        device.resume(pid)
        print("[+] Chrome spawned")

    script = session.create_script(script_code)
    script.on('message', on_message)
    script.load()

    print("\n" + "="*50)
    print("[*] Open moba.ru in Chrome browser on phone")
    print("[*] Pass captcha if needed")
    print("[*] Press Ctrl+C when done to save cookies")
    print("="*50 + "\n")

    try:
        sys.stdin.read()
    except KeyboardInterrupt:
        pass

    # Save cookies
    if captured_cookies:
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(captured_cookies, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Saved {len(captured_cookies)} cookies to {COOKIES_FILE}")
        print("\nCookies:")
        for name, value in captured_cookies.items():
            print(f"  {name}: {value[:50]}...")
    else:
        print("\n[!] No cookies captured")


if __name__ == "__main__":
    main()
