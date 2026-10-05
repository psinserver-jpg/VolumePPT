import SwiftUI
import UIKit

struct ContentView: View {
    @AppStorage("host") private var host = ""
    @AppStorage("token") private var token = ""
    @State private var status = "볼륨 ▲ = 다음 슬라이드   /   볼륨 ▼ = 이전 슬라이드"
    @StateObject private var volume = VolumeButtonObserver()
    @Environment(\.scenePhase) private var scenePhase
    @FocusState private var editing: Bool

    var body: some View {
        VStack(spacing: 12) {
            HiddenVolumeView(volumeView: volume.volumeView)
                .frame(width: 1, height: 1)

            VStack(alignment: .leading, spacing: 8) {
                Text("PC 주소 (예: 192.168.0.10:8765)")
                    .font(.footnote).foregroundColor(.gray)
                TextField("192.168.0.10:8765", text: $host)
                    .keyboardType(.URL)
                    .textInputAutocapitalization(.never)
                    .disableAutocorrection(true)
                    .textFieldStyle(.roundedBorder)
                    .focused($editing)
                SecureField("비밀번호 (서버에 --token 을 설정한 경우만)", text: $token)
                    .textFieldStyle(.roundedBorder)
                    .focused($editing)
                Button("연결 테스트") {
                    editing = false
                    send("ping")
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 6)
            }

            Text(status)
                .multilineTextAlignment(.center)
                .foregroundColor(.white)
                .padding(.vertical, 8)

            bigButton("다음 ▶") { send("next") }
                .frame(maxHeight: .infinity)
                .layoutPriority(2)
            bigButton("◀ 이전") { send("prev") }
                .frame(maxHeight: .infinity)
                .layoutPriority(1)
        }
        .padding(16)
        .background(Color(white: 0.07).ignoresSafeArea())
        .preferredColorScheme(.dark)
        .onAppear {
            volume.onUp = { send("next") }
            volume.onDown = { send("prev") }
            volume.start()
            UIApplication.shared.isIdleTimerDisabled = true  // 발표 중 화면 꺼짐 방지
        }
        .onChange(of: scenePhase) { phase in
            if phase == .active { volume.start() }
        }
    }

    private func bigButton(_ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 28, weight: .bold))
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .foregroundColor(.white)
                .background(Color(white: 0.16))
                .cornerRadius(20)
        }
    }

    private func send(_ action: String) {
        let target = RemoteClient.normalize(host)
        guard !target.isEmpty else {
            status = "먼저 PC 주소를 입력하세요"
            return
        }
        if action != "ping" {
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        }
        RemoteClient.send(action, host: target, token: token) { result in
            switch result {
            case .success(200):
                status = action == "ping" ? "✅ 연결됨: \(target)" : (action == "next" ? "다음 ▶" : "◀ 이전")
            case .success(403):
                status = "❌ 비밀번호가 틀렸습니다"
            case .success(let code):
                status = "❌ 오류 \(code)"
            case .failure:
                status = "❌ PC에 연결할 수 없습니다\n같은 Wi-Fi 인지, 서버가 실행 중인지 확인하세요"
            }
        }
    }
}
