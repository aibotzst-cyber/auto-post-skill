#!/usr/bin/env python3
"""
Chrome CDP Tweet Poster - Publish tweets via Chrome DevTools Protocol.

Uses an existing Chrome/Chromium instance with remote debugging enabled.
Start Chrome with: chrome --remote-debugging-port=9222

Supports:
  - Posting text tweets
  - Posting tweet threads (multiple tweets in sequence)
"""

import json
import time
import urllib.request
import urllib.error
from typing import Optional


CDP_PORT = 9222
CDP_HOST = "127.0.0.1"


def _cdp_get(path: str, port: int = CDP_PORT) -> dict:
    """GET request to CDP HTTP endpoint."""
    url = f"http://{CDP_HOST}:{port}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _ws_send(ws_url: str, method: str, params: dict = None, timeout: int = 30) -> dict:
    """Send a CDP command via WebSocket and return the result.

    Uses a simple HTTP-based approach: navigates and executes JS via CDP HTTP endpoints.
    For full WebSocket support, use the websocket-client library.
    """
    # We'll use a simpler approach - direct HTTP endpoint for evaluate
    import http.client
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(ws_url.replace("ws://", "http://"))
    host = parsed.hostname
    port = parsed.port

    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    payload = json.dumps({
        "id": 1,
        "method": method,
        "params": params or {},
    })
    conn.request("POST", "/json/protocol", body=payload)
    resp = conn.getresponse()
    return json.loads(resp.read().decode())


def get_browser_tabs(port: int = CDP_PORT) -> list:
    """List all open browser tabs."""
    return _cdp_get("/json/list", port)


def find_twitter_tab(port: int = CDP_PORT) -> Optional[dict]:
    """Find an existing X/Twitter tab."""
    tabs = get_browser_tabs(port)
    for tab in tabs:
        url = tab.get("url", "")
        if "x.com" in url or "twitter.com" in url:
            return tab
    return None


def execute_js(tab_ws_url: str, expression: str, port: int = CDP_PORT) -> Optional[str]:
    """Execute JavaScript in a browser tab via CDP WebSocket.

    Uses a lightweight WebSocket implementation to avoid external dependencies.
    """
    import socket
    import struct
    import hashlib
    import base64
    import os
    from urllib.parse import urlparse

    parsed = urlparse(tab_ws_url.replace("ws://", "http://"))
    host = parsed.hostname or CDP_HOST
    ws_port = parsed.port or port
    path = parsed.path or "/"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30)
    sock.connect((host, ws_port))

    # WebSocket handshake
    key = base64.b64encode(os.urandom(16)).decode()
    handshake = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{ws_port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    sock.sendall(handshake.encode())

    # Read handshake response
    response = b""
    while b"\r\n\r\n" not in response:
        response += sock.recv(4096)

    def ws_send_frame(data: bytes):
        mask_key = os.urandom(4)
        length = len(data)
        header = bytearray()
        header.append(0x81)  # FIN + text frame
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack(">H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack(">Q", length))
        header.extend(mask_key)
        masked = bytearray(b ^ mask_key[i % 4] for i, b in enumerate(data))
        sock.sendall(bytes(header) + bytes(masked))

    def ws_recv_frame() -> str:
        header = sock.recv(2)
        if len(header) < 2:
            return ""
        payload_len = header[1] & 0x7F
        if payload_len == 126:
            payload_len = struct.unpack(">H", sock.recv(2))[0]
        elif payload_len == 127:
            payload_len = struct.unpack(">Q", sock.recv(8))[0]
        data = b""
        while len(data) < payload_len:
            chunk = sock.recv(payload_len - len(data))
            if not chunk:
                break
            data += chunk
        return data.decode("utf-8", errors="replace")

    # Send CDP command
    cmd = json.dumps({
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
        },
    })
    ws_send_frame(cmd.encode())

    # Read response (may need multiple frames)
    result = None
    for _ in range(50):
        frame_data = ws_recv_frame()
        if not frame_data:
            break
        try:
            msg = json.loads(frame_data)
            if msg.get("id") == 1:
                result = msg
                break
        except json.JSONDecodeError:
            continue

    sock.close()
    if result and "result" in result:
        inner = result["result"].get("result", {})
        return inner.get("value", str(inner))
    return None


def navigate_to_compose(tab_ws_url: str, port: int = CDP_PORT) -> bool:
    """Navigate to X.com compose tweet page."""
    execute_js(tab_ws_url, "window.location.href = 'https://x.com/compose/post'")
    time.sleep(3)
    return True


def type_tweet_text(tab_ws_url: str, text: str, port: int = CDP_PORT) -> bool:
    """Type tweet text into the compose box using CDP."""
    # Escape text for JavaScript
    escaped = json.dumps(text)

    js_code = f"""
    (async () => {{
        // Wait for the compose box to appear
        const waitForElement = (selector, maxWait = 10000) => {{
            return new Promise((resolve, reject) => {{
                const el = document.querySelector(selector);
                if (el) return resolve(el);
                const observer = new MutationObserver(() => {{
                    const el = document.querySelector(selector);
                    if (el) {{
                        observer.disconnect();
                        resolve(el);
                    }}
                }});
                observer.observe(document.body, {{ childList: true, subtree: true }});
                setTimeout(() => {{ observer.disconnect(); reject('timeout'); }}, maxWait);
            }});
        }};

        // Find the tweet compose box
        const editor = await waitForElement('[data-testid="tweetTextarea_0"]');
        editor.focus();

        // Use insertText command for reliable text input
        const text = {escaped};
        document.execCommand('insertText', false, text);

        return 'ok';
    }})()
    """
    result = execute_js(tab_ws_url, js_code)
    return result == "ok"


def click_post_button(tab_ws_url: str, port: int = CDP_PORT) -> bool:
    """Click the Post/Tweet button."""
    js_code = """
    (async () => {
        // Find the post button
        const btn = document.querySelector('[data-testid="tweetButton"], [data-testid="tweetButtonInline"]');
        if (!btn) return 'button_not_found';
        btn.click();
        return 'ok';
    })()
    """
    result = execute_js(tab_ws_url, js_code)
    return result == "ok"


def post_tweet(text: str, port: int = CDP_PORT) -> dict:
    """Post a single tweet via Chrome CDP.

    Requires Chrome running with --remote-debugging-port=9222
    and logged into x.com.

    Returns:
        {"success": True/False, "message": str}
    """
    try:
        # Find or create a Twitter tab
        tab = find_twitter_tab(port)
        if not tab:
            # Open a new tab with Twitter
            tabs = get_browser_tabs(port)
            if not tabs:
                return {"success": False, "message": "No browser tabs found. Is Chrome running with --remote-debugging-port?"}
            tab = tabs[0]

        ws_url = tab.get("webSocketDebuggerUrl", "")
        if not ws_url:
            return {"success": False, "message": "No WebSocket URL for tab"}

        # Navigate to compose
        navigate_to_compose(ws_url, port)
        time.sleep(2)

        # Type the tweet
        if not type_tweet_text(ws_url, text, port):
            return {"success": False, "message": "Failed to type tweet text"}
        time.sleep(1)

        # Click post
        if not click_post_button(ws_url, port):
            return {"success": False, "message": "Failed to click Post button"}

        time.sleep(3)
        return {"success": True, "message": "Tweet posted successfully"}

    except Exception as e:
        return {"success": False, "message": f"CDP error: {e}"}


def post_thread(tweets: list, port: int = CDP_PORT) -> list:
    """Post a thread of tweets.

    Args:
        tweets: List of tweet text strings.

    Returns:
        List of results for each tweet.
    """
    results = []
    for i, text in enumerate(tweets):
        print(f"[cdp_poster] Posting tweet {i+1}/{len(tweets)}...")
        result = post_tweet(text, port)
        results.append(result)
        if not result["success"]:
            print(f"[cdp_poster] Failed at tweet {i+1}: {result['message']}")
            break
        if i < len(tweets) - 1:
            time.sleep(5)  # Wait between tweets in a thread
    return results


def check_chrome_cdp(port: int = CDP_PORT) -> bool:
    """Check if Chrome CDP is reachable."""
    try:
        _cdp_get("/json/version", port)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 cdp_poster.py <tweet_text>")
        print("       Requires Chrome with --remote-debugging-port=9222")
        sys.exit(1)

    text = " ".join(sys.argv[1:])
    print(f"Posting tweet: {text[:50]}...")
    result = post_tweet(text)
    print(json.dumps(result, indent=2))
