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
import ipaddress
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
    cfg = {"port": DEFAULT_PORT, "use_pin": True, "pin": f"{random.randint(0, 9999):04d}", "host": ""}
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


TAILSCALE_NET = ipaddress.ip_network("100.64.0.0/10")


def is_tailscale(ip):
    try:
        return ipaddress.ip_address(ip) in TAILSCALE_NET
    except ValueError:
        return False


def tailscale_ip():
    """이 PC 의 Tailscale IPv4 주소 (100.x.y.z). Tailscale 이 꺼져 있으면 None."""
    # 1) Tailscale 이 켜져 있으면 100.100.100.100(Tailscale DNS) 로 가는 경로의 출발 주소가 곧 Tailscale IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("100.100.100.100", 53))  # 실제로 패킷을 보내지는 않음
        ip = s.getsockname()[0]
        s.close()
        if is_tailscale(ip):
            return ip
    except OSError:
        pass
    # 2) tailscale 명령으로 확인
    candidates = ["tailscale",
                  r"C:\Program Files\Tailscale\tailscale.exe",
                  "/Applications/Tailscale.app/Contents/MacOS/Tailscale"]
    flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW: 검은 창 안 띄움
    for exe in candidates:
        try:
            out = subprocess.run([exe, "ip", "-4"], capture_output=True, text=True,
                                 timeout=3, creationflags=flags).stdout.split()
        except (OSError, subprocess.SubprocessError):
            continue
        for ip in out:
            if is_tailscale(ip):
                return ip
    return None


def local_ips():
    """휴대폰이 접속할 수 있는 PC 의 IP 목록. Tailscale IP 가 있으면 맨 앞, 그다음 Wi-Fi/LAN IP."""
    found = []
    ts = tailscale_ip()
    if ts:
        found.append(ts)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # 실제로 패킷을 보내지는 않음
        found.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass
    ips = []
    for ip in found:
        if ip not in ips and not ip.startswith("127."):
            ips.append(ip)
    return ips


def ip_label(ip):
    return f"{ip}  (Tailscale)" if is_tailscale(ip) else ip


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
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<meta name="theme-color" content="#111317">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="VolumePPT">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon.png">
<title>VolumePPT 리모컨</title>
<style>
  :root { --bg:#111317; --card:#1f232b; --fg:#f2f3f5; --muted:#8b919c; --accent:#4f8cff; --ok:#3ecf8e; --err:#ff6b6b; }
  * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; -webkit-user-select:none; user-select:none; }
  html,body { margin:0; height:100%; background:var(--bg); color:var(--fg); overscroll-behavior:none;
              font-family:system-ui,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif; }
  body { display:flex; flex-direction:column; gap:10px; touch-action:manipulation;
         padding:max(12px, env(safe-area-inset-top)) 16px max(12px, env(safe-area-inset-bottom)); }
  .top { display:flex; align-items:center; gap:8px; font-size:14px; }
  .dot { width:10px; height:10px; border-radius:50%; background:var(--muted); flex:none; }
  .dot.ok { background:var(--ok); } .dot.err { background:var(--err); }
  .top .count { margin-left:auto; color:var(--muted); }
  .pad { flex:1; border:0; border-radius:22px; background:var(--card); color:var(--fg);
         font:inherit; font-size:30px; font-weight:700; display:flex; flex-direction:column;
         align-items:center; justify-content:center; gap:6px; transition:background .08s; }
  .pad small { font-size:13px; font-weight:400; color:var(--muted); }
  .pad.hit { background:var(--accent); } .pad.hit small { color:#fff; }
  #next { flex:2.2; }
  .tools { display:flex; gap:8px; }
  .tool { flex:1; border:0; border-radius:14px; background:var(--card); color:var(--fg); font:inherit;
          font-size:14px; padding:12px 8px; text-align:center; text-decoration:none; }
  .tool.on { background:var(--accent); }
  .hint { font-size:12px; color:var(--muted); text-align:center; line-height:1.5; min-height:1.5em; }
  /* 아이폰 단축어 설치 패널 */
  #ios { position:fixed; inset:0; background:var(--bg); overflow-y:auto; z-index:10;
         padding:max(16px, env(safe-area-inset-top)) 20px max(20px, env(safe-area-inset-bottom)); }
  #ios h2 { font-size:20px; margin:4px 0 6px; }
  #ios p { color:var(--muted); font-size:14px; line-height:1.55; margin:0 0 14px; }
  #ios ol { list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:12px; }
  #ios li { background:var(--card); border-radius:16px; padding:14px; }
  #ios li > b { display:block; font-size:15px; margin-bottom:4px; }
  #ios li span { display:block; color:var(--muted); font-size:13px; line-height:1.5; }
  #ios .go { display:block; margin-top:10px; padding:12px; border-radius:12px; background:var(--accent);
             color:#fff; text-align:center; text-decoration:none; font-weight:600; font-size:15px; }
  #ios .go.sub { background:#2c313b; }
  #ios .close { width:100%; margin-top:16px; padding:14px; border:0; border-radius:14px; background:#2c313b;
                color:var(--fg); font:inherit; font-size:15px; }
</style>
</head>
<body>
  <div class="top">
    <span class="dot" id="dot"></span><span id="state">연결 확인 중…</span>
    <span class="count" id="count"></span>
  </div>

  <button class="pad" id="next">다음 ▶<small>탭 · 왼쪽으로 밀기</small></button>
  <button class="pad" id="prev">◀ 이전<small>탭 · 오른쪽으로 밀기</small></button>

  <div class="tools">
    <button class="tool" id="media">🔒 잠금화면 · 이어폰 버튼 켜기</button>
    <a class="tool" id="apk" href="/app.apk" hidden>볼륨버튼 앱(선택)</a>
    <button class="tool" id="ios-open" hidden>⚡ 동작 버튼 설정</button>
  </div>
  <div class="hint" id="hint">화면을 탭하거나 밀어서 슬라이드를 넘기세요</div>

  <div id="ios" hidden>
    <h2>⚡ 아이폰 버튼으로 넘기기</h2>
    <p>단축어 2개를 설치하면 <b>동작 버튼</b>이나 <b>뒷면 탭</b>으로 슬라이드를 넘길 수 있습니다. 처음 한 번만 하면 됩니다.</p>
    <ol>
      <li><b>① 단축어 2개 설치</b>
        <span>버튼을 누르고 <b>다운로드</b> → 위쪽 ⬇︎ 에서 파일 열기 → <b>단축어 추가</b>. 이름은 바꾸지 마세요.</span>
        <a class="go" href="__SC_NEXT__">VolumePPT-Next (다음) 설치</a>
        <a class="go" href="__SC_PREV__">VolumePPT-Prev (이전) 설치</a>
      </li>
      <li><b>② 이 PC 로 설정</b>
        <span>단축어 앱이 열리며 이 PC 의 주소와 PIN 이 저장됩니다. "설정 완료" 알림이 뜨면 성공입니다. 파일 접근을 물으면 <b>허용</b>하세요.</span>
        <a class="go" id="sc-setup" href="#">이 PC 로 설정하기</a>
      </li>
      <li><b>③ 버튼에 연결</b>
        <span><b>설정 → 동작 버튼 → 단축어</b> → VolumePPT-Next<br>
              <b>설정 → 손쉬운 사용 → 터치 → 뒷면 탭 → 이중 탭</b> → VolumePPT-Prev<br>
              (Apple 정책상 이 단계는 직접 해야 합니다)</span>
        <a class="go sub" href="App-prefs:">설정 앱 열기</a>
      </li>
    </ol>
    <p style="margin-top:14px">PC 주소나 PIN 이 바뀌면 ② 만 다시 누르면 됩니다.</p>
    <button class="close" id="ios-close">닫기</button>
  </div>

<script>
  // ── 설정 ──────────────────────────────────────────────
  const qs = new URLSearchParams(location.search);
  let token = qs.get("token") || "";
  try { if (token) localStorage.setItem("token", token); else token = localStorage.getItem("token") || ""; } catch (e) {}
  if (qs.has("token")) history.replaceState(null, "", location.pathname);   // 주소창에서 PIN 숨기기
  const $ = (id) => document.getElementById(id);
  const tq = () => (token ? "?token=" + encodeURIComponent(token) : "");
  if (/Android/i.test(navigator.userAgent) && __HAS_APK__) $("apk").hidden = false;

  // ── 연결 상태 ──────────────────────────────────────────
  let count = 0;
  function setState(ok, text) {
    $("dot").className = "dot " + (ok ? "ok" : "err");
    $("state").textContent = text;
  }
  async function ping() {
    try {
      const r = await fetch("/ping" + tq(), { cache: "no-store" });
      if (r.ok) setState(true, "PC 연결됨");
      else if (r.status === 403) setState(false, "PIN 이 맞지 않습니다 — PC 의 QR 을 다시 찍어 주세요");
      else setState(false, "오류 " + r.status);
    } catch (e) { setState(false, "PC 에 연결할 수 없습니다"); }
  }
  ping(); setInterval(ping, 3000);

  // ── 슬라이드 넘기기 ────────────────────────────────────
  async function send(action) {
    const pad = $(action);
    pad.classList.add("hit"); setTimeout(() => pad.classList.remove("hit"), 150);
    if (navigator.vibrate) navigator.vibrate(25);
    try {
      const r = await fetch("/" + action + tq(), { cache: "no-store" });
      if (r.ok) { setState(true, action === "next" ? "다음 ▶" : "◀ 이전"); $("count").textContent = "넘긴 횟수 " + (++count); }
      else if (r.status === 403) setState(false, "PIN 이 맞지 않습니다 — PC 의 QR 을 다시 찍어 주세요");
      else setState(false, "오류 " + r.status);
    } catch (e) { setState(false, "PC 에 연결할 수 없습니다"); }
  }

  // 탭
  let swiped = false;
  $("next").addEventListener("click", () => { if (!swiped) send("next"); });
  $("prev").addEventListener("click", () => { if (!swiped) send("prev"); });

  // 스와이프 (화면 어디서나): 왼쪽으로 밀기 = 다음, 오른쪽으로 밀기 = 이전
  let sx = 0, sy = 0;
  document.addEventListener("touchstart", (e) => { sx = e.touches[0].clientX; sy = e.touches[0].clientY; swiped = false; }, { passive: true });
  document.addEventListener("touchend", (e) => {
    const dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) {
      swiped = true; setTimeout(() => (swiped = false), 400);
      send(dx < 0 ? "next" : "prev");
    }
  }, { passive: true });

  // 키보드 / 블루투스 셔터·프레젠터 (일부 기기는 볼륨키도 여기로 들어옴)
  document.addEventListener("keydown", (e) => {
    if (["AudioVolumeUp", "VolumeUp", "ArrowRight", "ArrowDown", "PageDown", " ", "Enter"].includes(e.key)) { e.preventDefault(); send("next"); }
    else if (["AudioVolumeDown", "VolumeDown", "ArrowLeft", "ArrowUp", "PageUp"].includes(e.key)) { e.preventDefault(); send("prev"); }
  });

  // ── 잠금화면 · 이어폰 버튼 (Media Session) ─────────────
  // 소리 없는 오디오를 재생해 두면 잠금화면/알림창의 ⏭ ⏮ 와 이어폰 버튼이 슬라이드를 넘긴다.
  let audio = null;
  function silentWav(seconds) {
    const rate = 8000, n = rate * seconds, buf = new ArrayBuffer(44 + n), v = new DataView(buf);
    const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    w(0, "RIFF"); v.setUint32(4, 36 + n, true); w(8, "WAVE"); w(12, "fmt ");
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, rate, true); v.setUint32(28, rate, true); v.setUint16(32, 1, true); v.setUint16(34, 8, true);
    w(36, "data"); v.setUint32(40, n, true);
    for (let i = 0; i < n; i++) v.setUint8(44 + i, 128);
    return URL.createObjectURL(new Blob([buf], { type: "audio/wav" }));
  }
  async function toggleMedia() {
    const btn = $("media");
    if (audio) {
      audio.pause(); audio = null;
      btn.classList.remove("on"); btn.textContent = "🔒 잠금화면 · 이어폰 버튼 켜기";
      $("hint").textContent = "화면을 탭하거나 밀어서 슬라이드를 넘기세요";
      return;
    }
    if (!("mediaSession" in navigator)) { $("hint").textContent = "이 브라우저는 잠금화면 버튼을 지원하지 않습니다"; return; }
    audio = new Audio(silentWav(30));
    audio.loop = true;
    try { await audio.play(); } catch (e) { audio = null; $("hint").textContent = "오디오를 시작할 수 없습니다: " + e.message; return; }
    navigator.mediaSession.metadata = new MediaMetadata({ title: "VolumePPT 리모컨", artist: "⏭ 다음 슬라이드 · ⏮ 이전 슬라이드" });
    navigator.mediaSession.setActionHandler("nexttrack", () => send("next"));
    navigator.mediaSession.setActionHandler("previoustrack", () => send("prev"));
    navigator.mediaSession.setActionHandler("play", () => audio && audio.play());
    navigator.mediaSession.setActionHandler("pause", () => audio && audio.play());   // 멈추지 않게 유지
    navigator.mediaSession.playbackState = "playing";
    btn.classList.add("on"); btn.textContent = "🔒 잠금화면 버튼 사용 중";
    $("hint").textContent = "화면을 꺼도 잠금화면의 ⏭ ⏮ 또는 이어폰 버튼으로 넘길 수 있습니다";
  }
  $("media").addEventListener("click", toggleMedia);

  // ── 아이폰 단축어 (동작 버튼 · 뒷면 탭) ─────────────────
  // 단축어는 "http://PC주소:포트/ACTION?token=PIN" 을 저장해 두고 ACTION 을 next/prev 로 바꿔 호출한다.
  const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent) ||
                (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  if (isIOS) {
    $("ios-open").hidden = false;
    const template = location.protocol + "//" + location.host + "/ACTION" + tq();
    $("sc-setup").href = "shortcuts://run-shortcut?name=" + encodeURIComponent("VolumePPT-Next") +
                         "&input=text&text=" + encodeURIComponent(template);
    $("ios-open").addEventListener("click", () => { $("ios").hidden = false; });
    $("ios-close").addEventListener("click", () => { $("ios").hidden = true; });
  }
</script>
</body>
</html>
"""


# 아이폰 단축어 (Apple 서명본, GitHub Releases 에 빌드마다 올라감)
SHORTCUT_URL = "https://github.com/psinserver-jpg/VolumePPT/releases/latest/download/VolumePPT-{}.shortcut"

MANIFEST = json.dumps({
    "name": "VolumePPT 리모컨",
    "short_name": "VolumePPT",
    "start_url": "/",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": "#111317",
    "theme_color": "#111317",
    "icons": [{"src": "/icon.png", "sizes": "180x180", "type": "image/png"}],
}, ensure_ascii=False)


def make_icon_png(size=180):
    """홈 화면 아이콘 (파란 배경에 흰 ▶). 외부 라이브러리 없이 PNG 를 만든다."""
    import struct
    import zlib
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            # 가운데 삼각형: x 는 35%~70%, y 는 x 에 비례해 좁아짐
            cx, cy = x / size, abs(y / size - 0.5)
            inside = 0.36 <= cx <= 0.70 and cy <= (0.70 - cx) * 0.75
            row += bytes((255, 255, 255) if inside else (0x4F, 0x8C, 0xFF))
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


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
        self._seen = {}                 # 휴대폰별 마지막 접속 시각 (연결 알림 중복 방지)
        self._icon = make_icon_png()
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
            html = (REMOTE_HTML.replace("__HAS_APK__", "true" if self.apk_path else "false")
                    .replace("__SC_NEXT__", SHORTCUT_URL.format("Next"))
                    .replace("__SC_PREV__", SHORTCUT_URL.format("Prev")))
            return req._reply(200, html, "text/html; charset=utf-8")

        if path == "/manifest.json":
            return req._reply(200, MANIFEST, "application/manifest+json; charset=utf-8")

        if path == "/icon.png":
            return req._reply(200, self._icon, "image/png")

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
                # 웹 리모컨은 3초마다 ping 하므로, 새로 연결됐을 때만 알린다
                now = time.monotonic()
                if now - self._seen.get(client, -1e9) > 15:
                    self.events.put(("connect", f"{client} 휴대폰 연결됨"))
                self._seen[client] = now
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


def action_url(ip, port, pin, action):
    """아이폰 단축어 'URL 내용 가져오기' 에 넣을 주소."""
    url = f"http://{ip}:{port}/{action}"
    return url + (f"?token={quote(pin)}" if pin else "")


def pick_ip(cfg):
    ips = local_ips() or ["127.0.0.1"]
    return cfg["host"] if cfg.get("host") in ips else ips[0]


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
        self.ips = []

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
        label(pad, "휴대폰으로 PowerPoint 슬라이드를 넘기는 무선 리모컨", 10, self.MUTED).pack(anchor="w", pady=(0, 12))

        card = tk.Frame(pad, bg=self.CARD, padx=16, pady=16)
        card.pack(fill="x")

        self.qr = tk.Canvas(card, width=220, height=220, bg="white", highlightthickness=0)
        self.qr.grid(row=0, column=0, rowspan=6, padx=(0, 16))

        label(card, "① 휴대폰 카메라로 QR 을 찍으세요", 11, bold=True).grid(row=0, column=1, sticky="w")
        self.net_hint = label(card, "", 9, self.MUTED, justify="left")
        self.net_hint.grid(row=1, column=1, sticky="w")
        label(card, "② 열린 화면을 탭하거나 밀어서 넘기세요", 11, bold=True).grid(row=2, column=1, sticky="w", pady=(10, 0))
        label(card, "앱 설치 없이 브라우저에서 바로 동작합니다", 9, self.MUTED).grid(row=3, column=1, sticky="w")

        info = tk.Frame(card, bg=self.CARD)
        info.grid(row=4, column=1, sticky="w", pady=(14, 0))
        label(info, "주소", 9, self.MUTED).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.ip_var = tk.StringVar()
        self.ip_menu = tk.OptionMenu(info, self.ip_var, "")
        self.ip_menu.configure(bg=self.CARD, fg=self.FG, activebackground=self.CARD, activeforeground=self.FG,
                               highlightthickness=0, bd=0, font=(font, 13, "bold"))
        self.ip_menu.grid(row=0, column=1, sticky="w")
        self.port_label = label(info, "", 13, bold=True)
        self.port_label.grid(row=0, column=2, sticky="w")
        tk.Button(info, text="↻", command=self.reload_ips, font=(font, 10), relief="flat", bg=self.BG,
                  fg=self.FG, activebackground=self.ACCENT, padx=6).grid(row=0, column=3, padx=(8, 0))
        label(info, "PIN", 9, self.MUTED).grid(row=1, column=0, sticky="w", padx=(0, 10))
        self.pin_label = label(info, "", 13, bold=True)
        self.pin_label.grid(row=1, column=1, sticky="w", columnspan=3)

        opts = tk.Frame(card, bg=self.CARD)
        opts.grid(row=5, column=1, sticky="w", pady=(10, 0))
        self.pin_on = tk.BooleanVar(value=cfg["use_pin"])
        tk.Checkbutton(opts, text="PIN 사용 (다른 사람이 넘기지 못하게)", variable=self.pin_on,
                       command=self.toggle_pin, bg=self.CARD, fg=self.FG, selectcolor=self.BG,
                       activebackground=self.CARD, activeforeground=self.FG, font=(font, 9)).pack(side="left")
        tk.Button(opts, text="새 PIN", command=self.new_pin, font=(font, 9), relief="flat",
                  bg=self.BG, fg=self.FG, activebackground=self.ACCENT, padx=8).pack(side="left", padx=(6, 0))

        sc = tk.Frame(pad, bg=self.CARD, padx=16, pady=10)
        sc.pack(fill="x", pady=(10, 0))
        label(sc, "아이폰 단축어 · 동작 버튼용 주소", 10, bold=True).grid(row=0, column=0, columnspan=3, sticky="w")
        self.sc_urls = {}
        for i, (action, name) in enumerate((("next", "다음"), ("prev", "이전")), start=1):
            label(sc, name, 9, self.MUTED).grid(row=i, column=0, sticky="w", padx=(0, 10))
            self.sc_urls[action] = label(sc, "", 10)
            self.sc_urls[action].grid(row=i, column=1, sticky="w")
            tk.Button(sc, text="복사", command=lambda a=action: self.copy_url(a), font=(font, 9), relief="flat",
                      bg=self.BG, fg=self.FG, activebackground=self.ACCENT, padx=8).grid(row=i, column=2, padx=(10, 0), pady=1)
        sc.grid_columnconfigure(1, weight=1)

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
        self.reload_ips(redraw=False)
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

    def current_ip(self):
        return self.ip_var.get().split()[0]

    def reload_ips(self, redraw=True):
        """IP 목록을 다시 찾는다. Tailscale 을 실행기보다 늦게 켰을 때 ↻ 로 갱신."""
        self.ips = local_ips() or ["127.0.0.1"]
        saved = self.cfg.get("host")
        chosen = saved if saved in self.ips else self.ips[0]
        menu = self.ip_menu["menu"]
        menu.delete(0, "end")
        for ip in self.ips:
            menu.add_command(label=ip_label(ip), command=lambda ip=ip: self.choose_ip(ip))
        self.ip_var.set(ip_label(chosen))
        if redraw:
            self.refresh()

    def choose_ip(self, ip):
        self.ip_var.set(ip_label(ip))
        self.cfg["host"] = ip
        save_config(self.cfg)
        self.refresh()

    def refresh(self):
        ip = self.current_ip()
        url = phone_url(ip, self.cfg["port"], self.pin)
        self.port_label.configure(text=f":{self.cfg['port']}")
        self.pin_label.configure(text=self.pin or "사용 안 함")
        if is_tailscale(ip):
            self.net_hint.configure(text="Tailscale 주소 — 휴대폰에서 Tailscale 을 켜 두면\nWi-Fi 가 달라도 연결됩니다")
        else:
            self.net_hint.configure(text="휴대폰과 이 PC 가 같은 Wi-Fi 여야 합니다")
        for action, lbl in self.sc_urls.items():
            lbl.configure(text=action_url(ip, self.cfg["port"], self.pin, action))
        self.draw_qr(url)

    def copy_url(self, action):
        self.root.clipboard_clear()
        self.root.clipboard_append(action_url(self.current_ip(), self.cfg["port"], self.pin, action))
        self.set_status(("다음" if action == "next" else "이전") + " 주소를 복사했습니다", self.OK)

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
    ip = pick_ip(cfg)
    print("=" * 60)
    print(" VolumePPT 실행 중   (종료: Ctrl+C)")
    print("=" * 60)
    print(f" 주소: {ip_label(ip)}:{cfg['port']}   PIN: {pin or '없음'}")
    print(" 휴대폰 카메라로 아래 QR 을 찍으세요" +
          (" (휴대폰에서 Tailscale 켜기)" if is_tailscale(ip) else " (같은 Wi-Fi)"))
    try:
        import qrcode
        q = qrcode.QRCode(border=1)
        q.add_data(phone_url(ip, cfg["port"], pin))
        q.print_ascii(invert=True)
    except Exception:
        print(f" {phone_url(ip, cfg['port'], pin)}")
    print(" 아이폰 단축어 · 동작 버튼용 주소:")
    print(f"   다음  {action_url(ip, cfg['port'], pin, 'next')}")
    print(f"   이전  {action_url(ip, cfg['port'], pin, 'prev')}")
    others = [i for i in local_ips() if i != ip]
    if others:
        print(" 다른 주소: " + ", ".join(ip_label(i) for i in others) + "   (--host 로 선택)")
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
    p.add_argument("--host", help="QR 에 넣을 PC 주소 (기본: Tailscale IP, 없으면 Wi-Fi IP)")
    p.add_argument("--nogui", action="store_true", help="창 없이 콘솔에서 실행")
    p.add_argument("--dry-run", action="store_true", help="키를 누르지 않음 (테스트용)")
    args = p.parse_args()

    cfg = load_config()
    if args.port:
        cfg["port"] = args.port
    if args.no_pin:
        cfg["use_pin"] = False
    if args.host:
        cfg["host"] = args.host
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
