# VolumePPT

스마트폰의 **볼륨 버튼**을 무선 프레젠테이션 리모컨으로 바꿔 줍니다.

| 휴대폰 버튼 | PPT 동작 |
|---|---|
| 볼륨 ▲ (업) | 다음 슬라이드 |
| 볼륨 ▼ (다운) | 이전 슬라이드 |

PowerPoint 외에 Keynote, Google Slides, PDF 뷰어처럼 방향키로 넘어가는 프로그램이면 모두 동작합니다.

## 간단 사용법 (3단계)

1. **PC 에서 `VolumePPT` 실행** — 설치할 것 없이 더블클릭만 하면 됩니다.
2. **휴대폰 카메라로 PC 화면의 QR 코드를 찍기** → 열린 화면에서 **[앱으로 연결]**
   - 안드로이드에 앱이 없으면 같은 화면의 **[안드로이드 앱 받기]** 로 바로 설치할 수 있습니다 (앱이 실행기 안에 들어 있음).
   - 앱 없이도 그 화면의 큰 버튼으로 넘길 수 있습니다.
3. **PowerPoint 슬라이드 쇼 창을 한 번 클릭**해 두고 볼륨 ▲ / ▼ 로 넘기세요.

주소와 PIN 은 QR 에 들어 있어서 직접 입력할 필요가 없습니다. PIN 은 같은 Wi-Fi 의 다른 사람이 슬라이드를 넘기지 못하게 막아 줍니다 (실행기 창에서 끄거나 새로 만들 수 있음).

![실행기 화면](docs/launcher.png)

## 다운로드

GitHub 의 **Actions → Build VolumePPT** 에서 가장 최근 실행을 열면 아래 파일을 받을 수 있습니다.

| 파일 | 대상 |
|---|---|
| `VolumePPT-Windows` → `VolumePPT.exe` | Windows PC (안드로이드 앱 포함) |
| `VolumePPT-Mac` → `VolumePPT.app` | Mac (안드로이드 앱 포함) |
| `VolumePPT-Android` → `VolumePPT.apk` | 안드로이드 앱만 따로 |

`v1.0` 같은 태그를 올리면 같은 파일이 **Releases** 에도 자동으로 올라갑니다.

### 처음 한 번만
- **Windows**: "Windows의 PC 보호" 창이 뜨면 *추가 정보 → 실행*. 방화벽 알림이 뜨면 **개인 네트워크 허용**.
- **Mac**: 앱을 우클릭 → *열기*. *시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용* 에서 VolumePPT 허용 (키 입력에 필요).
- **안드로이드**: 출처를 알 수 없는 앱 설치 허용.
- **아이폰**: 앱스토어 배포가 없어서 Mac + Xcode 로 직접 설치해야 합니다.
  ```bash
  brew install xcodegen
  cd ios && xcodegen generate && open VolumePPT.xcodeproj
  ```
  앱 없이 QR → 웹 리모컨의 화면 버튼으로는 바로 쓸 수 있습니다.

## 구성

| 폴더 | 내용 |
|---|---|
| `pc/VolumePPT.py` | PC 통합 실행기 (서버 + QR 화면 + 웹 리모컨 + 키 입력). 실행 파일로 묶어서 배포 |
| `android/` | 안드로이드 앱 (Android 5.0 이상) |
| `ios/` | 아이폰 앱 (iOS 15 이상) |

소스에서 직접 실행하려면:
```bash
cd pc
pip install -r requirements.txt
python VolumePPT.py            # 창으로 실행
python VolumePPT.py --nogui    # 콘솔에서 실행 (터미널에 QR 표시)
```

## 알아 두기

- 휴대폰 앱이 **화면에 떠 있을 때만** 볼륨 버튼이 리모컨으로 동작합니다. 앱이 켜져 있는 동안은 화면이 꺼지지 않습니다.
- 앱이 켜져 있는 동안 볼륨 버튼은 휴대폰 음량을 바꾸지 않습니다.
- 휴대폰과 PC 가 **같은 Wi-Fi** 에 있어야 합니다. 회사/공용 Wi-Fi 에서 기기 간 통신이 막혀 있으면 휴대폰 핫스팟에 PC 를 연결해서 쓰세요.
- 블루투스 프레젠터나 셔터 리모컨을 휴대폰에 연결해도 같이 동작합니다.
