import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

final class NoRedirects: NSObject, URLSessionTaskDelegate {
    func urlSession(
        _ session: URLSession,
        task: URLSessionTask,
        willPerformHTTPRedirection response: HTTPURLResponse,
        newRequest request: URLRequest,
        completionHandler: @escaping (URLRequest?) -> Void
    ) {
        completionHandler(nil)
    }
}

struct ClientError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

func setting(_ name: String, fallback: String = "") -> String {
    let value = ProcessInfo.processInfo.environment[name] ?? ""
    return value.isEmpty ? fallback : value
}

func run() async throws {
    let args = Array(CommandLine.arguments.dropFirst())
    guard args.count == 2 else {
        throw ClientError(message: "Usage: swift example.swift REQUEST_JSON OUTPUT_SAVE")
    }
    guard !FileManager.default.fileExists(atPath: args[1]) else {
        throw ClientError(message: "Output already exists; choose a new path.")
    }
    let limit = 2 * 1024 * 1024
    let attributes = try FileManager.default.attributesOfItem(atPath: args[0])
    guard let length = attributes[.size] as? NSNumber,
          length.intValue > 0, length.intValue <= limit else {
        throw ClientError(message: "Request must be 1 byte to 2 MiB.")
    }
    let payload = try Data(contentsOf: URL(fileURLWithPath: args[0]))
    let base = setting("BCSFE_API_URL", fallback: "https://battle-cats-save-file-editor-api.vercel.app")
        .replacingOccurrences(of: "/+$", with: "", options: .regularExpression)
    guard let url = URL(string: base + "/v2/save/edit"),
          let scheme = url.scheme, ["https", "http"].contains(scheme.lowercased()) else {
        throw ClientError(message: "BCSFE_API_URL must be an HTTP or HTTPS URL.")
    }
    var request = URLRequest(url: url, timeoutInterval: 120)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.setValue("application/octet-stream", forHTTPHeaderField: "Accept")
    request.httpBody = payload
    let configuration = URLSessionConfiguration.ephemeral
    configuration.timeoutIntervalForRequest = 120
    configuration.timeoutIntervalForResource = 120
    let session = URLSession(configuration: configuration, delegate: NoRedirects(), delegateQueue: nil)
    defer { session.invalidateAndCancel() }
    let (save, rawResponse) = try await session.data(for: request)
    guard let response = rawResponse as? HTTPURLResponse else {
        throw ClientError(message: "Expected an HTTP response.")
    }
    guard (200..<300).contains(response.statusCode) else {
        throw ClientError(message: "API returned HTTP \(response.statusCode). No save was written.")
    }
    let contentType = (response.value(forHTTPHeaderField: "Content-Type") ?? "")
        .split(separator: ";", maxSplits: 1).first.map(String.init)?
        .trimmingCharacters(in: .whitespacesAndNewlines).lowercased() ?? ""
    guard contentType == "application/octet-stream" else {
        throw ClientError(message: "Expected a binary save; set output to file in the request JSON.")
    }
    guard !save.isEmpty, save.count <= limit else {
        throw ClientError(message: "Response is empty or exceeds 2 MiB.")
    }
    try save.write(to: URL(fileURLWithPath: args[1]), options: .withoutOverwriting)
    print("Saved \(save.count) bytes to \(args[1])")
}

do {
    try await run()
} catch {
    FileHandle.standardError.write(Data((error.localizedDescription + "\n").utf8))
    exit(1)
}