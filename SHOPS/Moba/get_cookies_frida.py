"""
Get moba.ru cookies from Chrome via Frida
"""
import frida
import sys
import json
import time

OUTPUT_FILE = "moba_cookies.json"
cookies_result = None

SCRIPT = """
setTimeout(function() {
    Java.perform(function() {
        console.log("[*] Getting cookies...");

        try {
            var CookieManager = Java.use("android.webkit.CookieManager");
            var instance = CookieManager.getInstance();

            var urls = [
                "https://moba.ru/",
                "https://moba.ru",
                "http://moba.ru/",
                ".moba.ru"
            ];

            for (var i = 0; i < urls.length; i++) {
                var cookies = instance.getCookie(urls[i]);
                if (cookies) {
                    send({type: "cookies", url: urls[i], data: cookies});
                    break;
                }
            }

            send({type: "done"});

        } catch(e) {
            send({type: "error", message: e.toString()});
        }
    });
}, 1000);
"""


def on_message(message, data):
    global cookies_result

    if message['type'] == 'send':
        payload = message['payload']

        if payload.get('type') == 'cookies':
            print(f"[+] Got cookies for {payload['url']}:")
            print(payload['data'])
            cookies_result = payload['data']

        elif payload.get('type') == 'error':
            print(f"[!] Error: {payload['message']}")

        elif payload.get('type') == 'done':
            print("[*] Done")

    elif message['type'] == 'error':
        print(f"[ERROR] {message['stack']}")


def main():
    global cookies_result

    print("[*] Connecting to device...")
    device = frida.get_usb_device()

    print("[*] Looking for Chrome...")

    # Find Chrome process
    chrome_pid = None
    for proc in device.enumerate_processes():
        if "chrome" in proc.name.lower():
            print(f"[*] Found: {proc.name} (PID: {proc.pid})")
            if "com.android.chrome" in proc.name or proc.name == "Chrome":
                chrome_pid = proc.pid
                break

    if not chrome_pid:
        # Try to attach by package name
        try:
            session = device.attach("com.android.chrome")
            print("[+] Attached to com.android.chrome")
        except Exception as e:
            print(f"[!] Cannot attach: {e}")
            print("[*] Make sure Chrome is open on the phone")
            return
    else:
        session = device.attach(chrome_pid)
        print(f"[+] Attached to PID {chrome_pid}")

    script = session.create_script(SCRIPT)
    script.on('message', on_message)
    script.load()

    print("[*] Waiting for cookies...")
    time.sleep(5)

    session.detach()

    # Parse and save cookies
    if cookies_result:
        cookies_dict = {}
        for part in cookies_result.split(";"):
            if "=" in part:
                name, value = part.strip().split("=", 1)
                cookies_dict[name.strip()] = value.strip()

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies_dict, f, indent=2, ensure_ascii=False)

        print(f"\n[+] Saved {len(cookies_dict)} cookies to {OUTPUT_FILE}")

        # Print cookie string
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
        print(f"\n[*] Cookie string:\n{cookie_str[:300]}...")
    else:
        print("\n[!] No cookies captured")


if __name__ == "__main__":
    main()
