"""
Get cookies via CDP WebSocket - browser endpoint
"""
import json
import socket

CDP_HOST = "localhost"
CDP_PORT = 9222
OUTPUT_FILE = "moba_cookies.json"


def send_cdp_command(sock, cmd_id, method, params=None):
    """Send CDP command via raw socket"""
    cmd = {"id": cmd_id, "method": method}
    if params:
        cmd["params"] = params

    payload = json.dumps(cmd)

    # WebSocket frame
    frame = bytearray()
    frame.append(0x81)  # text frame, FIN

    payload_bytes = payload.encode('utf-8')
    length = len(payload_bytes)

    if length < 126:
        frame.append(0x80 | length)  # mask bit set
    elif length < 65536:
        frame.append(0x80 | 126)
        frame.extend(length.to_bytes(2, 'big'))
    else:
        frame.append(0x80 | 127)
        frame.extend(length.to_bytes(8, 'big'))

    # Mask key (required for client -> server)
    mask = b'\x00\x00\x00\x00'
    frame.extend(mask)
    frame.extend(payload_bytes)  # no actual masking with zero mask

    sock.send(frame)


def recv_ws_message(sock):
    """Receive WebSocket message"""
    data = sock.recv(2)
    if len(data) < 2:
        return None

    opcode = data[0] & 0x0F
    length = data[1] & 0x7F

    if length == 126:
        length = int.from_bytes(sock.recv(2), 'big')
    elif length == 127:
        length = int.from_bytes(sock.recv(8), 'big')

    payload = b''
    while len(payload) < length:
        payload += sock.recv(length - len(payload))

    return payload.decode('utf-8')


def get_cookies():
    """Get cookies from moba.ru via CDP"""
    import requests

    # Get pages
    resp = requests.get(f"http://{CDP_HOST}:{CDP_PORT}/json")
    pages = resp.json()

    moba_page = None
    for p in pages:
        if "moba.ru" in p.get("url", ""):
            moba_page = p
            break

    if not moba_page:
        print("[!] moba.ru page not found")
        return {}

    ws_url = moba_page["webSocketDebuggerUrl"]
    print(f"[*] Page: {moba_page['title']}")
    print(f"[*] WS: {ws_url}")

    # Extract host/port/path from ws://localhost:9222/devtools/page/18
    # Use raw socket with proper HTTP upgrade

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((CDP_HOST, CDP_PORT))

    # WebSocket handshake
    path = ws_url.split(f":{CDP_PORT}")[1]
    handshake = f"GET {path} HTTP/1.1\r\n"
    handshake += f"Host: {CDP_HOST}:{CDP_PORT}\r\n"
    handshake += "Upgrade: websocket\r\n"
    handshake += "Connection: Upgrade\r\n"
    handshake += "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
    handshake += "Sec-WebSocket-Version: 13\r\n"
    handshake += "Origin: http://localhost\r\n"
    handshake += "\r\n"

    sock.send(handshake.encode())

    # Receive response
    response = b''
    while b'\r\n\r\n' not in response:
        response += sock.recv(1024)

    if b'101' not in response:
        print(f"[!] Handshake failed: {response[:200]}")
        sock.close()
        return {}

    print("[+] WebSocket connected")

    # Get cookies
    send_cdp_command(sock, 1, "Network.getCookies", {"urls": ["https://moba.ru/"]})

    result = recv_ws_message(sock)
    sock.close()

    if result:
        data = json.loads(result)
        if "result" in data:
            cookies = data["result"]["cookies"]
            return {c["name"]: c["value"] for c in cookies}

    return {}


if __name__ == "__main__":
    cookies = get_cookies()

    if cookies:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        print(f"\n[+] Got {len(cookies)} cookies:")
        for name, value in cookies.items():
            print(f"  {name}: {value[:50]}...")

        print(f"\n[+] Saved to {OUTPUT_FILE}")
    else:
        print("[!] Failed to get cookies")
