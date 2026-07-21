import Foundation

let url = URL(string: "https://battle-cats-save-file-editor-api.vercel.app/edit")!
var request = URLRequest(url: url)
request.httpMethod = "POST"
request.setValue("application/json", forHTTPHeaderField: "Content-Type")

let json: [String: Any] = [
    "transfer_code": "1a2b3c4d5",
    "confirmation_code": "1234",
    "country_code": "kr",
    "catfood": 45000,
    "unlock_cats": true
]

request.httpBody = try? JSONSerialization.data(withJSONObject: json)

let task = URLSession.shared.dataTask(with: request) { data, response, error in
    if let data = data, let responseString = String(data: data, encoding: .utf8) {
        print("Response:\n\(responseString)")
    }
}
task.resume()
RunLoop.main.run(until: Date(timeIntervalSinceNow: 5))
