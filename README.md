# VolumePPT

**휴대폰으로 PowerPoint 슬라이드를 넘기는 무선 리모컨**

PPT 를 띄운 컴퓨터에서 실행기를 켜고, 화면의 QR 코드를 휴대폰 카메라로 찍으면 끝.
휴대폰에는 **아무것도 설치하지 않아도** 됩니다.

<p align="center">
  <img src="docs/launcher.png" width="520" alt="PC 실행기">
  &nbsp;&nbsp;
  <img src="docs/webapp.png" width="200" alt="휴대폰 웹 리모컨">
</p>

## ⬇️ 다운로드

PPT 를 띄울 **컴퓨터**에 받아서 바로 실행하세요. 설치 과정은 없습니다.

| 컴퓨터 | 다운로드 |
|:---:|:---:|
| 🪟 **Windows** | [**VolumePPT.exe**](https://github.com/psinserver-jpg/VolumePPT/releases/latest/download/VolumePPT.exe) |
| 🍎 **Mac** | [**VolumePPT-mac.zip**](https://github.com/psinserver-jpg/VolumePPT/releases/latest/download/VolumePPT-mac.zip) |

---

## 🚀 3단계 사용법

1. **컴퓨터에서 VolumePPT 실행** → QR 코드가 뜹니다.
2. **휴대폰 기본 카메라로 QR 찍기** → 리모컨 화면이 열리고 🟢 **PC 연결됨** 표시.
3. **PowerPoint 슬라이드 쇼를 시작**하고 슬라이드 화면을 한 번 클릭 → 휴대폰으로 넘기기.

> 휴대폰과 컴퓨터는 **같은 Wi-Fi** 에 있어야 합니다. [Tailscale](#-tailscale-로-어디서나-연결-추천) 을 쓰면 Wi-Fi 가 달라도 됩니다.
> PIN 은 QR 에 들어 있어서 직접 입력할 필요가 없습니다.

---

## 🎮 넘기는 방법

| 방법 | 다음 | 이전 | 비고 |
|---|---|---|---|
| 화면 버튼 | **[다음 ▶]** 탭 | **[◀ 이전]** 탭 | 기본 |
| 스와이프 | 왼쪽으로 밀기 | 오른쪽으로 밀기 | 화면 어디서나 |
| 잠금화면 · 알림창 | ⏭ | ⏮ | 화면을 꺼도 됨 ¹ |
| 이어폰 · 에어팟 · 애플워치 | 다음 곡 | 이전 곡 | ¹ |
| 아이폰 동작 버튼 · 뒷면 탭 | 동작 버튼 | 뒷면 두 번 탭 | [설정 방법](#-아이폰-동작-버튼--뒷면-탭) |
| 블루투스 프레젠터 · 키보드 | → / PageDown | ← / PageUp | 휴대폰에 연결 |
| 안드로이드 볼륨 버튼 | 볼륨 ▲ | 볼륨 ▼ | [전용 앱 필요](#-안드로이드-볼륨-버튼-선택) |

¹ 리모컨 화면 아래 **[🔒 잠금화면 · 이어폰 버튼 켜기]** 를 먼저 누르세요. 브라우저·기종에 따라 지원되지 않을 수 있습니다.

> 휴대폰 브라우저는 보안상 웹 페이지에 **볼륨 버튼을 전달하지 않습니다.** 그래서 볼륨 버튼은 안드로이드 전용 앱에서만 됩니다.

**홈 화면에 추가:** 리모컨 화면에서 브라우저 메뉴 → **홈 화면에 추가** 하면 앱처럼 아이콘으로 열 수 있습니다.

---

## 🌐 Tailscale 로 어디서나 연결 (추천)

[Tailscale](https://tailscale.com) 을 컴퓨터와 휴대폰에 설치하고 같은 계정으로 로그인해 두면:

- **Wi-Fi 가 달라도 연결** — 휴대폰은 LTE, 컴퓨터는 회사 Wi-Fi 여도 OK. 기기 간 통신을 막는 Wi-Fi 에서도 동작.
- **주소가 바뀌지 않음** — Tailscale 주소(`100.x.y.z`)는 고정이라 아이폰 단축어를 한 번만 만들면 됩니다.

실행기는 Tailscale 이 켜져 있으면 **자동으로 Tailscale 주소를 QR 에 넣습니다** (주소 옆에 `(Tailscale)` 표시).
Tailscale 을 나중에 켰다면 주소 옆 **↻** 를 누르세요. 휴대폰에서도 Tailscale 이 **켜진 상태**여야 합니다.

> 주소 목록에서 Wi-Fi 주소(`192.168.x.x`)를 고르면 그 선택이 저장됩니다.

---

## 🍎 아이폰 동작 버튼 · 뒷면 탭

아이폰 **단축어** 2개를 만들어 실제 버튼에 연결합니다. 처음 한 번, 단축어당 30초면 됩니다.

**1. 단축어 만들기** — 아이폰 리모컨 화면 아래 **[⚡ 동작 버튼 설정]** 을 누르면 안내가 나옵니다.

1. **[다음 주소 복사]** → **[단축어 앱 열기]**
2. **동작 추가** → `URL` 검색 → **URL 내용 가져오기**
3. 파란 **URL** 글자를 지우고 **붙여넣기**
4. 이름을 **PPT 다음** 으로 저장
5. 같은 방법으로 **[이전 주소 복사]** → **PPT 이전**

**2. 버튼에 연결**

| 버튼 | 설정 위치 | 단축어 |
|---|---|---|
| 동작 버튼 (iPhone 15 Pro 이상) | 설정 → 동작 버튼 → 단축어 | PPT 다음 |
| 뒷면 이중 탭 (iPhone 8 이상) | 설정 → 손쉬운 사용 → 터치 → 뒷면 탭 → 이중 탭 | PPT 이전 |
| 잠금화면 · 제어 센터 (iOS 18 이상) | 잠금화면/제어 센터 편집 → 단축어 추가 | 원하는 것 |

> - 처음 실행할 때 "로컬 네트워크" 접근을 물으면 **허용**하세요.
> - PIN 을 바꾸거나 Wi-Fi 주소가 바뀌면 단축어의 URL 도 고쳐야 합니다 (Tailscale 주소는 고정).
> - 단축어 파일을 자동으로 설치해 줄 수는 없습니다. iOS 는 iCloud 계정으로 서명된 단축어만 가져올 수 있기 때문입니다.

---

## 🤖 안드로이드 볼륨 버튼 (선택)

볼륨 버튼으로 넘기고 싶다면 전용 앱을 설치하세요. 앱에서는 **볼륨 ▲ = 다음, 볼륨 ▼ = 이전** 입니다.

- [**VolumePPT.apk 다운로드**](https://github.com/psinserver-jpg/VolumePPT/releases/latest/download/VolumePPT.apk) (출처를 알 수 없는 앱 허용 필요)
- 또는 리모컨 화면 아래 **[볼륨버튼 앱(선택)]** 으로 컴퓨터에서 바로 받기

---

## 🔧 처음 한 번만

| 상황 | 할 일 |
|---|---|
| Windows "Windows의 PC 보호" 창 | **추가 정보 → 실행** (서명되지 않은 프로그램 경고) |
| Windows 방화벽 알림 | **개인 네트워크 허용** (Tailscale 로 안 되면 **공용 네트워크**도) |
| Mac "확인되지 않은 개발자" | 앱 **우클릭 → 열기 → 열기** |
| Mac 에서 슬라이드가 안 넘어감 | 시스템 설정 → 개인정보 보호 및 보안 → **손쉬운 사용** 에서 VolumePPT 허용 |

## ❓ 문제 해결

| 증상 | 해결 |
|---|---|
| 🔴 **PC 에 연결할 수 없습니다** | Wi-Fi 주소면 같은 Wi-Fi 인지, Tailscale 주소면 휴대폰 Tailscale 이 켜져 있는지 확인. 회사·학교 Wi-Fi 에서 안 되면 Tailscale 을 쓰거나 휴대폰 핫스팟에 컴퓨터를 연결하세요. |
| 🟢 연결됨인데 안 넘어감 | PowerPoint **슬라이드 쇼 화면을 한 번 클릭**하세요. Mac 은 손쉬운 사용 권한 확인. |
| 🔴 **PIN 이 맞지 않습니다** | 컴퓨터 화면의 QR 을 다시 찍으세요. |
| Tailscale 주소가 안 나옴 | 컴퓨터 Tailscale 연결 상태 확인 후 주소 옆 **↻** |
| 단축어 실행 시 오류 | 실행기 창의 "단축어 · 동작 버튼용 주소" 와 단축어 URL 이 같은지 확인 (PIN 포함) |
| "포트를 사용할 수 없습니다" | VolumePPT 가 이미 켜져 있습니다. 기존 창을 닫고 다시 실행. |

## 💡 알아 두기

- PowerPoint 외에도 **Keynote, Google Slides, PDF 뷰어** 등 방향키(→ ←)로 넘어가는 프로그램이면 모두 됩니다.
- 같은 Wi-Fi 로 쓸 때는 인터넷이 필요 없습니다. Tailscale 은 인터넷 연결이 필요합니다.
- **PIN** 은 같은 네트워크의 다른 사람이 슬라이드를 넘기지 못하게 막습니다. 실행기에서 끄거나 [새 PIN] 으로 바꿀 수 있고, 다음 실행 때도 유지됩니다.
- 실행기 창은 최소화해도 계속 동작합니다.

---

## 👩‍💻 개발자용

<details>
<summary>작동 원리 · API</summary>

```
휴대폰 브라우저 ──(HTTP: /next, /prev)──▶ PC 실행기 ──(→ / ← 키 입력)──▶ PowerPoint
```

- PC 실행기가 작은 웹 서버를 켜고 요청에 따라 방향키를 누릅니다. 휴대폰 리모컨 화면도 이 서버가 제공합니다.
- QR 에는 `http://PC주소:8765/?token=PIN` 이 들어 있습니다 (PC주소 = Tailscale 주소, 없으면 Wi-Fi 주소).
- 잠금화면·이어폰 버튼은 브라우저의 Media Session 기능을 씁니다.

| 요청 | 동작 |
|---|---|
| `GET /` | 웹 리모컨 화면 |
| `GET /next?token=PIN` | 다음 슬라이드 (→) |
| `GET /prev?token=PIN` | 이전 슬라이드 (←) |
| `GET /ping?token=PIN` | 연결 확인 |
| `GET /app.apk` | 안드로이드 볼륨버튼 앱 |

PIN 이 틀리면 `403`, PIN 을 끄면 `token` 은 필요 없습니다.
</details>

<details>
<summary>프로젝트 구조</summary>

```
VolumePPT/
├── pc/VolumePPT.py             # PC 실행기 (창 + QR + 서버 + 웹 리모컨 + 키 입력, 파일 하나)
├── android/                    # (선택) 안드로이드 볼륨버튼 앱
├── ios/                        # (선택) 아이폰 볼륨버튼 앱 — XcodeGen 프로젝트
├── docs/                       # README 이미지
└── .github/workflows/build.yml # exe · app · apk 빌드 및 릴리스
```
</details>

<details>
<summary>소스에서 실행</summary>

Python 3.8 이상:

```bash
cd pc
pip install -r requirements.txt
python VolumePPT.py              # 창으로 실행
python VolumePPT.py --nogui      # 콘솔 모드 (터미널에 QR 표시)
```

| 옵션 | 설명 |
|---|---|
| `--port 9000` | 포트 변경 (기본 8765) |
| `--host 100.x.y.z` | QR 에 넣을 주소 지정 |
| `--no-pin` | PIN 없이 실행 |
| `--nogui` | 창 없이 실행 |
| `--dry-run` | 키를 누르지 않고 기록만 (테스트용) |

설정(포트, PIN, 선택한 주소)은 `~/.volumeppt.json` 에 저장됩니다.
</details>

<details>
<summary>빌드 · 배포</summary>

`android/`, `pc/` 를 바꿔 푸시하면 GitHub Actions 가 APK → (APK 를 포함한) Windows exe · Mac app 순서로 빌드합니다.
**`main` 에 반영되면** 자동으로 Releases 에 새 버전(`v1.0.N`)이 올라가고, 위 다운로드 링크가 새 버전을 가리킵니다.
Actions 탭의 *Run workflow* 나 `v*` 태그로도 릴리스할 수 있습니다.

아이폰 볼륨버튼 앱 (Mac + Xcode 필요):

```bash
brew install xcodegen
cd ios && xcodegen generate && open VolumePPT.xcodeproj
```
</details>
