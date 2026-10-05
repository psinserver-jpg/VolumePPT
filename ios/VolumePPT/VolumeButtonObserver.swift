import AVFoundation
import MediaPlayer
import SwiftUI

/// iOS 는 볼륨 버튼 이벤트를 앱에 직접 주지 않으므로,
/// 시스템 음량(outputVolume) 변화를 감시해 ▲/▼ 를 알아내고
/// 매번 음량을 중간값(0.5)으로 되돌려서 계속 누를 수 있게 한다.
final class VolumeButtonObserver: ObservableObject {
    var onUp: () -> Void = {}
    var onDown: () -> Void = {}

    /// 화면 밖에 숨겨 둔 MPVolumeView. 이 뷰가 화면에 있으면 시스템 음량 HUD 도 표시되지 않는다.
    let volumeView = MPVolumeView(frame: CGRect(x: -2000, y: -2000, width: 1, height: 1))

    private let baseVolume: Float = 0.5
    private var observation: NSKeyValueObservation?

    func start() {
        let session = AVAudioSession.sharedInstance()
        // 다른 앱의 소리를 끊지 않도록 ambient + mixWithOthers
        try? session.setCategory(.ambient, options: [.mixWithOthers])
        try? session.setActive(true)

        if observation == nil {
            observation = session.observe(\.outputVolume, options: [.old, .new]) { [weak self] _, change in
                guard let self = self, let new = change.newValue, let old = change.oldValue else { return }
                // 우리가 0.5 로 되돌린 변화는 무시
                if abs(new - self.baseVolume) < 0.001 { return }
                DispatchQueue.main.async {
                    if new > old {
                        self.onUp()
                    } else {
                        self.onDown()
                    }
                    self.resetVolume()
                }
            }
        }
        resetVolume()
    }

    func stop() {
        observation?.invalidate()
        observation = nil
    }

    private func resetVolume() {
        // MPVolumeView 내부 슬라이더 값을 바꾸면 시스템 음량이 바뀐다
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            guard let slider = self.volumeView.subviews.compactMap({ $0 as? UISlider }).first else { return }
            if abs(slider.value - self.baseVolume) > 0.001 {
                slider.setValue(self.baseVolume, animated: false)
                slider.sendActions(for: .valueChanged)
            }
        }
    }
}

/// SwiftUI 화면에 MPVolumeView 를 붙이기 위한 래퍼
struct HiddenVolumeView: UIViewRepresentable {
    let volumeView: MPVolumeView

    func makeUIView(context: Context) -> UIView {
        let container = UIView(frame: .zero)
        volumeView.alpha = 0.01
        container.addSubview(volumeView)
        return container
    }

    func updateUIView(_ uiView: UIView, context: Context) {}
}
