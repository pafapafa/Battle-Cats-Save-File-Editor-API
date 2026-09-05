import java.io.IOException
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardOpenOption
import java.time.Duration
import kotlin.system.exitProcess

fun setting(name: String, fallback: String = ""): String =
    System.getenv(name)?.takeIf { it.isNotEmpty() } ?: fallback

fun main(args: Array<String>) {
    try {
        require(args.size == 2) { "Usage: java -jar example-kotlin.jar REQUEST_JSON OUTPUT_SAVE" }
        val source = Path.of(args[0])
        val destination = Path.of(args[1])
        if (Files.exists(destination)) throw IOException("Output already exists; choose a new path.")
        val limit = 2 * 1024 * 1024
        val length = Files.size(source)
        require(length in 1..limit.toLong()) { "Request must be 1 byte to 2 MiB." }
        val payload = Files.readAllBytes(source)
        val url = setting("BCSFE_API_URL", "https://battle-cats-save-file-editor-api.vercel.app").trimEnd('/') + "/v2/save/edit"
        val client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(15))
            .followRedirects(HttpClient.Redirect.NEVER)
            .build()
        val request = HttpRequest.newBuilder(URI.create(url))
            .timeout(Duration.ofSeconds(120))
            .header("Content-Type", "application/json")
            .header("Accept", "application/octet-stream")
            .POST(HttpRequest.BodyPublishers.ofByteArray(payload))
            .build()
        val response = client.send(request, HttpResponse.BodyHandlers.ofByteArray())
        if (response.statusCode() !in 200..299)
            throw IOException("API returned HTTP ${response.statusCode()}. No save was written.")
        val type = response.headers().firstValue("Content-Type").orElse("").substringBefore(';').trim()
        if (!type.equals("application/octet-stream", ignoreCase = true))
            throw IOException("Expected a binary save; set output to file in the request JSON.")
        val save = response.body()
        require(save.size in 1..limit) { "Response is empty or exceeds 2 MiB." }
        Files.newOutputStream(destination, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE).use { output ->
            try {
                output.write(save)
                output.flush()
            } catch (error: IOException) {
                output.close()
                Files.deleteIfExists(destination)
                throw error
            }
        }
        println("Saved ${save.size} bytes to $destination")
    } catch (error: Exception) {
        System.err.println(error.message)
        exitProcess(1)
    }
}