#!/usr/bin/env python3
"""VolumePPT PC 서버.

휴대폰 앱(안드로이드/iOS) 또는 웹 리모컨이 보내는 신호를 받아
PowerPoint(및 Keynote, Google Slides, PDF 뷰어 등)에 키 입력을 보낸다.

    GET /next  -> 오른쪽 화살표 (다음 슬라이드)
    GET /prev  -> 왼쪽 화살표 (이전 슬라이드)
    GET /ping  -> 연결 확인
    GET /      -> 브라우저용 웹 리모컨 (앱 설치 없이 사용)
"""

import argparse
import json
import os
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DEFAULT_PORT = 8765
HERE = os.path.dirname(os.path.abspath(__file__))


def make_key_sender(dry_run):
    """다음/이전 키를 누르는 함수를 반환한다."""
    if dry_run:
        return lambda action: print(f"[dry-run] {action}")

    try:
        from pynput.keyboard import Controller, Key
    except ImportError:
        sys.exit("pynput 이 필요합니다:  pip install -r requirements.txt")

    keyboard = Controller()
    keys = {"next": Key.right, "prev": Key.left}

    def send(action):
        keyboard.press(keys[action])
        keyboard.release(keys[action])

    return send


def local_ips():
    """같은 Wi-Fi 의 휴대폰이 접속할 수 있는 PC 의 IP 목록."""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # 실제로 패킷을 보내지는 않음
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


class Handler(BaseHTTPRequestHandler):
    send_key = None
    token = None
    debounce = 0.15
    _last = 0.0

    def log_message(self, fmt, *args):
        pass  # 기본 접속 로그는 끔

    def _reply(self, code, body, content_type="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path.rstrip("/") or "/"

        if path in ("/", "/index.html"):
            with open(os.path.join(HERE, "remote.html"), "rb") as f:
                return self._reply(200, f.read(), "text/html; charset=utf-8")

        if path == "/ping":
            return self._reply(200, json.dumps({"ok": True, "app": "VolumePPT"}))

        if path in ("/next", "/prev"):
            if Handler.token:
                given = parse_qs(url.query).get("token", [""])[0]
                if given != Handler.token:
                    return self._reply(403, json.dumps({"ok": False, "error": "bad token"}))
            now = time.monotonic()
            # 버튼이 아주 짧은 간격으로 두 번 들어오면(채터링) 한 번만 처리
            if now - Handler._last < Handler.debounce:
                return self._reply(200, json.dumps({"ok": True, "ignored": True}))
            Handler._last = now
            action = path[1:]
            Handler.send_key(action)
            print(("▶ 다음" if action == "next" else "◀ 이전") + f"  ({self.client_address[0]})")
            return self._reply(200, json.dumps({"ok": True, "action": action}))

        self._reply(404, json.dumps({"ok": False, "error": "not found"}))


def main():
    p = argparse.ArgumentParser(description="VolumePPT PC 서버")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--token", help="설정하면 휴대폰에서도 같은 비밀번호를 입력해야 동작")
    p.add_argument("--dry-run", action="store_true", help="키를 누르지 않고 로그만 출력 (테스트용)")
    args = p.parse_args()

    Handler.send_key = make_key_sender(args.dry_run)
    Handler.token = args.token

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print("=" * 50)
    print(" VolumePPT 서버 실행 중")
    print("=" * 50)
    print(" 휴대폰 앱에 아래 주소를 입력하세요 (같은 Wi-Fi):")
    for ip in local_ips() or ["<PC의 IP 주소>"]:
        print(f"   {ip}:{args.port}")
    print(" 앱 없이 쓰려면 휴대폰 브라우저에서:")
    for ip in local_ips() or ["<PC의 IP 주소>"]:
        print(f"   http://{ip}:{args.port}")
    if args.token:
        print(f" 비밀번호: {args.token}")
    print(" PowerPoint 슬라이드 쇼 창을 클릭해 활성화해 두세요.  종료: Ctrl+C")
    print("=" * 50)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
