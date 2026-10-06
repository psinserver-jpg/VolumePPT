#!/usr/bin/env python3
"""VolumePPT 통합 실행기.

더블클릭 한 번으로:
  * 휴대폰 신호를 받는 서버를 켜고
  * 휴대폰으로 찍을 QR 코드를 보여 주고
  * 받은 신호를 → / ← 키 입력으로 바꿔 PowerPoint 를 넘긴다.

휴대폰 쪽 경로 (모두 같은 서버 사용):
    GET /           웹 리모컨 (+ 앱 연결 / 안드로이드 앱 받기)
    GET /next       다음 슬라이드
    GET /prev       이전 슬라이드
    GET /ping       연결 확인
    GET /app.apk    안드로이드 앱 (실행기에 포함된 경우)

명령줄 옵션: --nogui (창 없이 실행), --dry-run (키를 누르지 않음), --port, --no-pin
"""

import argparse
import json
import os
import queue
import random
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

APP_NAME = "VolumePPT"
DEFAULT_PORT = 8765
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".volumeppt.json")


# ---------------------------------------------------------------------------
# 설정 / 경로
# ---------------------------------------------------------------------------

def resource_path(name):
    """PyInstaller 로 묶인 실행 파일 안의 파일, 또는 이 스크립트 옆의 파일."""
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, name))
    exe_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
    candidates.append(os.path.join(exe_dir, name))
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def load_config():
    cfg = {"port": DEFAULT_PORT, "use_pin": True, "pin": f"{random.randint(0, 9999):04d}"}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except OSError:
        pass


def local_ips():
    """같은 Wi-Fi 의 휴대폰이 접속할 수 있는 PC 의 IP 목록 (가장 유력한 것이 맨 앞)."""
    primary = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # 실제로 패킷을 보내지는 않음
        primary = s.getsockname()[0]
        s.close()
    except OSError:
        pass
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    ips = sorted(ip for ip in ips if not ip.startswith("127.") and ip != primary)
    return ([primary] if primary else []) + ips


# ---------------------------------------------------------------------------
# 키 입력
# ---------------------------------------------------------------------------

def make_key_sender(dry_run=False):
    """'next' / 'prev' 를 받아 → / ← 키를 누르는 함수를 반환한다."""
    if dry_run:
        return lambda action: None

    if sys.platform == "win32":
        # 외부 라이브러리 없이 Windows API 로 직접 키 입력
        import ctypes
        user32 = ctypes.windll.user32
        vk = {"next": 0x27, "prev": 0x25}  # VK_RIGHT, VK_LEFT
        extended, keyup = 0x0001, 0x0002

        def send(action):
            user32.keybd_event(vk[action], 0, extended, 0)
            user32.keybd_event(vk[action], 0, extended | keyup, 0)
        return send

    try:
        from pynput.keyboard import Controller, Key
        keyboard = Controller()
        keys = {"next": Key.right, "prev": Key.left}

        def send(action):
            keyboard.press(keys[action])
            keyboard.release(keys[action])
        return send
    except Exception:
        pass

    if sys.platform == "darwin":
        codes = {"next": 124, "prev": 123}  # 오른쪽 / 왼쪽 화살표

        def send(action):
            subprocess.Popen(["osascript", "-e",
                              f'tell application "System Events" to key code {codes[action]}'])
        return send

    keys = {"next": "Right", "prev": "Left"}

    def send(action):
        subprocess.Popen(["xdotool", "key", keys[action]])
    return send


# ---------------------------------------------------------------------------
# 웹 리모컨 페이지 (실행기 하나에 모두 담기 위해 코드 안에 포함)
# ---------------------------------------------------------------------------

REMOTE_HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>VolumePPT 리모컨</title>
<style>
  * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; user-select:none; }
  html,body { margin:0; height:100%; background:#111; color:#eee;
              font-family:system-ui,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif; }
  body { display:flex; flex-direction:column; padding:16px; gap:12px; }
  .bar { display:flex; gap:8px; }
  .bar a { flex:1; text-align:center; padding:12px 8px; border-radius:12px; background:#4f8cff;
           color:#fff; text-decoration:none; font-size:15px; font-weight:600; }
  .bar a.sub { background:#2a2a2a; }
  .hint { text-align:center; font-size:13px; opacity:.65; line-height:1.5; }
  button { flex:1; border:0; border-radius:20px; background:#2a2a2a; color:#eee; font-size:28px; font-weight:700; }
  button:active { background:#4f8cff; }
  #next { flex:2; }
  #status { text-align:center; font-size:14px; min-height:1.3em; }
</style>
</head>
<body>
  <div class="bar">
    <a id="open-app" href="#">📱 앱으로 연결 (볼륨키 사용)</a>
    <a id="get-apk" class="sub" href="/app.apk" hidden>안드로이드 앱 받기</a>
  </div>
  <div class="hint">앱이 있으면 위 버튼을 누르세요. 앱 없이 아래 버튼으로도 넘길 수 있습니다.</div>
  <div id="status"></div>
  <button id="next">다음 ▶</button>
  <button id="prev">◀ 이전</button>
<script>
  const qs = new URLSearchParams(location.search);
  let token = qs.get("token") || "";
  try { if (token) localStorage.setItem("token", token); else token = localStorage.getItem("token") || ""; } catch (e) {}
  const status = document.getElementById("status");
  const isAndroid = /Android/i.test(navigator.userAgent);
  const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);

  document.getElementById("open-app").href =
    "volumeppt://connect?host=" + encodeURIComponent(location.host) + "&token=" + encodeURIComponent(token);
  if (isAndroid && __HAS_APK__) document.getElementById("get-apk").hidden = false;
  if (!isAndroid && !isIOS) document.querySelector(".bar").hidden = true;

  async function send(action) {
    if (navigator.vibrate) navigator.vibrate(30);
    try {
      const r = await fetch("/" + action + (token ? "?token=" + encodeURIComponent(token) : ""));
      status.textContent = r.ok ? (action === "next" ? "다음 ▶" : "◀ 이전")
                         : r.status === 403 ? "PIN 이 맞지 않습니다. PC 화면의 QR 을 다시 찍어 주세요" : "오류: " + r.status;
    } catch (e) {
      status.textContent = "PC에 연결할 수 없습니다";
    }
  }
  document.getElementById("next").onclick = () => send("next");
  document.getElementById("prev").onclick = () => send("prev");

  // 일부 안드로이드 브라우저 / 블루투스 셔터 리모컨은 볼륨키를 키 이벤트로 전달함
  document.addEventListener("keydown", (e) => {
    if (["AudioVolumeUp", "VolumeUp", "ArrowRight", "PageDown", " "].includes(e.key)) { e.preventDefault(); send("next"); }
    else if (["AudioVolumeDown", "VolumeDown", "ArrowLeft", "PageUp"].includes(e.key)) { e.preventDefault(); send("prev"); }
  });
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 서버
# ---------------------------------------------------------------------------

class RemoteServer:
    """휴대폰 요청을 받아 키를 누르는 HTTP 서버. 이벤트는 events 큐로 알린다."""

    def __init__(self, port, pin, send_key):
        self.port = port
        self.pin = pin                  # None 이면 PIN 검사 안 함
        self.send_key = send_key
        self.events = queue.Queue()     # (종류, 메시지)
        self.apk_path = resource_path("app.apk")
        self._last = 0.0
        self._httpd = None

    def start(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def _reply(self, code, body, ctype="application/json; charset=utf-8", extra=None):
                data = body.encode("utf-8") if isinstance(body, str) else body
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-store")
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                server.handle(self)

        self._httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()

    def handle(self, req):
        url = urlparse(req.path)
        path = url.path.rstrip("/") or "/"
        client = req.client_address[0]

        if path in ("/", "/index.html"):
            html = REMOTE_HTML.replace("__HAS_APK__", "true" if self.apk_path else "false")
            self.events.put(("connect", f"{client} 웹 리모컨 접속"))
            return req._reply(200, html, "text/html; charset=utf-8")

        if path == "/app.apk":
            if not self.apk_path:
                return req._reply(404, json.dumps({"ok": False, "error": "apk not bundled"}))
            with open(self.apk_path, "rb") as f:
                data = f.read()
            self.events.put(("connect", f"{client} 안드로이드 앱 다운로드"))
            return req._reply(200, data, "application/vnd.android.package-archive",
                              {"Content-Disposition": 'attachment; filename="VolumePPT.apk"'})

        if path in ("/ping", "/next", "/prev"):
            if self.pin and parse_qs(url.query).get("token", [""])[0] != self.pin:
                self.events.put(("error", f"{client} PIN 불일치"))
                return req._reply(403, json.dumps({"ok": False, "error": "bad token"}))

            if path == "/ping":
                self.events.put(("connect", f"{client} 연결됨"))
                return req._reply(200, json.dumps({"ok": True, "app": APP_NAME}))

            now = time.monotonic()
            # 아주 짧은 간격으로 두 번 들어오면(버튼 채터링) 한 번만 처리
            if now - self._last < 0.15:
                return req._reply(200, json.dumps({"ok": True, "ignored": True}))
            self._last = now
            action = path[1:]
            self.send_key(action)
            self.events.put((action, f"{'▶ 다음' if action == 'next' else '◀ 이전'}   ({client})"))
            return req._reply(200, json.dumps({"ok": True, "action": action}))

        req._reply(404, json.dumps({"ok": False, "error": "not found"}))


def phone_url(ip, port, pin):
    url = f"http://{ip}:{port}/"
    return url + (f"?token={quote(pin)}" if pin else "")


# ---------------------------------------------------------------------------
# 창 (tkinter)
# ---------------------------------------------------------------------------

class App:
    BG, CARD, FG, MUTED, ACCENT, OK, ERR = "#15171c", "#20232b", "#f2f2f2", "#9aa0aa", "#4f8cff", "#3ecf8e", "#ff6b6b"

    def __init__(self, cfg, dry_run):
        import tkinter as tk
        self.tk = tk
        self.cfg = cfg
        self.send_key = make_key_sender(dry_run)
        self.server = None
        self.ips = local_ips() or ["127.0.0.1"]

        self.root = root = tk.Tk()
        root.title(APP_NAME)
        root.configure(bg=self.BG)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.quit)

        font = "Malgun Gothic" if sys.platform == "win32" else ("Apple SD Gothic Neo" if sys.platform == "darwin" else "")

        def label(parent, text="", size=11, color=None, bold=False, **kw):
            return tk.Label(parent, text=text, bg=parent["bg"], fg=color or self.FG,
                            font=(font, size, "bold" if bold else "normal"), **kw)

        pad = tk.Frame(root, bg=self.BG, padx=20, pady=16)
        pad.pack()

        label(pad, "VolumePPT", 18, bold=True).pack(anchor="w")
        label(pad, "휴대폰 볼륨 ▲ 다음 슬라이드  ·  볼륨 ▼ 이전 슬라이드", 10, self.MUTED).pack(anchor="w", pady=(0, 12))

        card = tk.Frame(pad, bg=self.CARD, padx=16, pady=16)
        card.pack(fill="x")

        self.qr = tk.Canvas(card, width=220, height=220, bg="white", highlightthickness=0)
        self.qr.grid(row=0, column=0, rowspan=6, padx=(0, 16))

        label(card, "① 휴대폰 카메라로 QR 을 찍으세요", 11, bold=True).grid(row=0, column=1, sticky="w")
        label(card, "같은 Wi-Fi 에 연결되어 있어야 합니다", 9, self.MUTED).grid(row=1, column=1, sticky="w")
        label(card, "② 열린 화면에서 [앱으로 연결] 을 누르세요", 11, bold=True).grid(row=2, column=1, sticky="w", pady=(10, 0))
        label(card, "앱이 없으면 화면 버튼으로 넘길 수 있습니다", 9, self.MUTED).grid(row=3, column=1, sticky="w")

        info = tk.Frame(card, bg=self.CARD)
        info.grid(row=4, column=1, sticky="w", pady=(14, 0))
        label(info, "주소", 9, self.MUTED).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.addr_var = tk.StringVar()
        if len(self.ips) > 1:
            self.ip_var = tk.StringVar(value=self.ips[0])
            menu = tk.OptionMenu(info, self.ip_var, *self.ips, command=lambda _: self.refresh())
            menu.configure(bg=self.CARD, fg=self.FG, activebackground=self.CARD, highlightthickness=0,
                           bd=0, font=(font, 13, "bold"))
            menu.grid(row=0, column=1, sticky="w")
            self.port_label = label(info, "", 13, bold=True)
            self.port_label.grid(row=0, column=2, sticky="w")
        else:
            self.ip_var = tk.StringVar(value=self.ips[0])
            self.port_label = label(info, "", 13, bold=True)
            self.port_label.grid(row=0, column=1, sticky="w")
        label(info, "PIN", 9, self.MUTED).grid(row=1, column=0, sticky="w", padx=(0, 10))
        self.pin_label = label(info, "", 13, bold=True)
        self.pin_label.grid(row=1, column=1, sticky="w", columnspan=2)

        opts = tk.Frame(card, bg=self.CARD)
        opts.grid(row=5, column=1, sticky="w", pady=(10, 0))
        self.pin_on = tk.BooleanVar(value=cfg["use_pin"])
        tk.Checkbutton(opts, text="PIN 사용 (다른 사람이 넘기지 못하게)", variable=self.pin_on,
                       command=self.toggle_pin, bg=self.CARD, fg=self.FG, selectcolor=self.BG,
                       activebackground=self.CARD, activeforeground=self.FG, font=(font, 9)).pack(side="left")
        tk.Button(opts, text="새 PIN", command=self.new_pin, font=(font, 9), relief="flat",
                  bg=self.BG, fg=self.FG, activebackground=self.ACCENT, padx=8).pack(side="left", padx=(6, 0))

        status_row = tk.Frame(pad, bg=self.BG)
        status_row.pack(fill="x", pady=(14, 6))
        self.dot = label(status_row, "●", 12, self.OK)
        self.dot.pack(side="left")
        self.status = label(status_row, "", 11)
        self.status.pack(side="left", padx=(6, 0))
        self.count = label(status_row, "", 10, self.MUTED)
        self.count.pack(side="right")

        self.log = tk.Listbox(pad, height=6, bg=self.CARD, fg=self.FG, bd=0, highlightthickness=0,
                              font=(font, 10), activestyle="none", selectbackground=self.CARD)
        self.log.pack(fill="x")

        label(pad, "③ PowerPoint 슬라이드 쇼 창을 한 번 클릭해 두세요. 이 창은 최소화해도 됩니다.",
              9, self.MUTED).pack(anchor="w", pady=(10, 0))

        self.slides = 0
        self.start_server()
        self.root.after(100, self.poll)

    # -- 서버 / 화면 갱신 ----------------------------------------------------

    @property
    def pin(self):
        return self.cfg["pin"] if self.pin_on.get() else None

    def start_server(self):
        if self.server:
            self.server.stop()
        try:
            self.server = RemoteServer(self.cfg["port"], self.pin, self.send_key)
            self.server.start()
        except OSError:
            self.server = None
            self.set_status(f"포트 {self.cfg['port']} 을(를) 사용할 수 없습니다. VolumePPT 가 이미 켜져 있는지 확인하세요.", self.ERR)
            return
        self.set_status("실행 중 — 휴대폰 연결을 기다리는 중", self.OK)
        self.refresh()

    def refresh(self):
        url = phone_url(self.ip_var.get(), self.cfg["port"], self.pin)
        self.port_label.configure(text=("" if len(self.ips) > 1 else self.ip_var.get()) + f":{self.cfg['port']}")
        self.pin_label.configure(text=self.pin or "사용 안 함")
        self.draw_qr(url)

    def draw_qr(self, text):
        c = self.qr
        c.delete("all")
        try:
            import qrcode
        except ImportError:
            c.create_text(110, 110, text="QR 을 표시하려면\npip install qrcode", justify="center")
            return
        q = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
        q.add_data(text)
        q.make(fit=True)
        m = q.get_matrix()
        size = int(c["width"])
        cell = size // len(m)
        off = (size - cell * len(m)) // 2
        for y, row in enumerate(m):
            for x, on in enumerate(row):
                if on:
                    c.create_rectangle(off + x * cell, off + y * cell,
                                       off + (x + 1) * cell, off + (y + 1) * cell,
                                       fill="black", outline="")

    def set_status(self, text, color):
        self.status.configure(text=text)
        self.dot.configure(fg=color)

    def poll(self):
        if self.server:
            while True:
                try:
                    kind, msg = self.server.events.get_nowait()
                except queue.Empty:
                    break
                if kind in ("next", "prev"):
                    self.slides += 1
                    self.count.configure(text=f"넘긴 횟수 {self.slides}")
                    self.set_status("연결됨", self.OK)
                elif kind == "connect":
                    self.set_status("휴대폰 연결됨", self.OK)
                elif kind == "error":
                    self.set_status("PIN 이 맞지 않는 요청이 있었습니다", self.ERR)
                self.log.insert(0, time.strftime("%H:%M:%S  ") + msg)
                self.log.delete(50, "end")
        self.root.after(100, self.poll)

    # -- 버튼 ---------------------------------------------------------------

    def toggle_pin(self):
        self.cfg["use_pin"] = self.pin_on.get()
        save_config(self.cfg)
        if self.server:
            self.server.pin = self.pin
        self.refresh()

    def new_pin(self):
        self.cfg["pin"] = f"{random.randint(0, 9999):04d}"
        save_config(self.cfg)
        if self.server:
            self.server.pin = self.pin
        self.refresh()

    def quit(self):
        if self.server:
            self.server.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# 창 없이 실행 (--nogui)
# ---------------------------------------------------------------------------

def run_console(cfg, dry_run):
    pin = cfg["pin"] if cfg["use_pin"] else None
    send = make_key_sender(dry_run)
    server = RemoteServer(cfg["port"], pin, send)
    server.start()
    print("=" * 52)
    print(" VolumePPT 실행 중   (종료: Ctrl+C)")
    print("=" * 52)
    for ip in local_ips() or ["<PC의 IP 주소>"]:
        print(f" 휴대폰 브라우저/카메라로:  {phone_url(ip, cfg['port'], pin)}")
    print(f" 앱에 직접 입력:  주소 {(local_ips() or ['?'])[0]}:{cfg['port']}   PIN {pin or '없음'}")
    try:
        import qrcode
        q = qrcode.QRCode(border=1)
        q.add_data(phone_url((local_ips() or ["127.0.0.1"])[0], cfg["port"], pin))
        q.print_ascii(invert=True)
    except Exception:
        pass
    try:
        while True:
            kind, msg = server.events.get()
            print(time.strftime("%H:%M:%S  ") + msg)
    except KeyboardInterrupt:
        server.stop()
        print("\n종료합니다.")


def main():
    p = argparse.ArgumentParser(description="VolumePPT 통합 실행기")
    p.add_argument("--port", type=int, help=f"포트 (기본 {DEFAULT_PORT})")
    p.add_argument("--no-pin", action="store_true", help="PIN 없이 실행")
    p.add_argument("--nogui", action="store_true", help="창 없이 콘솔에서 실행")
    p.add_argument("--dry-run", action="store_true", help="키를 누르지 않음 (테스트용)")
    args = p.parse_args()

    cfg = load_config()
    if args.port:
        cfg["port"] = args.port
    if args.no_pin:
        cfg["use_pin"] = False
    save_config(cfg)

    if not args.nogui:
        try:
            App(cfg, args.dry_run).run()
            return
        except Exception as e:  # tkinter 가 없거나 화면이 없는 환경
            print(f"창을 열 수 없어 콘솔 모드로 실행합니다 ({e})")
    run_console(cfg, args.dry_run)


if __name__ == "__main__":
    main()
