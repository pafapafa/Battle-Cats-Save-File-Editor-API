import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse

fun main() {
    val url = "https://battle-cats-save-file-editor-api.vercel.app/edit"
    val json = """
        {
            "transfer_code": "1a2b3c4d5",
            "confirmation_code": "1234",
            "country_code": "kr",
            "catfood": 45000
        }
    """.trimIndent()

    val client = HttpClient.newHttpClient()
    val request = HttpRequest.newBuilder()
        .uri(URI.create(url))
        .header("Content-Type", "application/json")
        .POST(HttpRequest.BodyPublishers.ofString(json))
        .build()

    val response = client.send(request, HttpResponse.BodyHandlers.ofString())
    println("Response Code: ${response.statusCode()}")
    println("Response Body: ${response.body()}")
}
