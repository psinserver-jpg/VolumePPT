import Foundation

/// PC 서버(pc/server.py)에 /next, /prev, /ping 요청을 보낸다.
enum RemoteClient {
    static let defaultPort = 8765

    static func normalize(_ raw: String) -> String {
        var h = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        for prefix in ["http://", "https://"] where h.lowercased().hasPrefix(prefix) {
            h = String(h.dropFirst(prefix.count))
        }
        while h.hasSuffix("/") { h.removeLast() }
        if !h.isEmpty && !h.contains(":") { h += ":\(defaultPort)" }
        return h
    }

    static func send(_ action: String, host: String, token: String,
                     completion: @escaping (Result<Int, Error>) -> Void) {
        var components = URLComponents()
        components.scheme = "http"
        let parts = host.split(separator: ":", maxSplits: 1).map(String.init)
        components.host = parts.first
        if parts.count == 2 { components.port = Int(parts[1]) }
        components.path = "/" + action
        if !token.isEmpty { components.queryItems = [URLQueryItem(name: "token", value: token)] }

        guard let url = components.url else {
            completion(.failure(URLError(.badURL)))
            return
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 1.5
        URLSession.shared.dataTask(with: request) { _, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    completion(.failure(error))
                } else {
                    completion(.success((response as? HTTPURLResponse)?.statusCode ?? 0))
                }
            }
        }.resume()
    }
}
