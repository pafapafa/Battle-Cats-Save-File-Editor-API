import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Duration;

public class example {
    static String setting(String name, String fallback) {
        String value = System.getenv(name);
        return value == null || value.isEmpty() ? fallback : value;
    }

    public static void main(String[] args) {
        try {
            if (args.length != 2)
                throw new IllegalArgumentException("Usage: java example.java REQUEST_JSON OUTPUT_SAVE");
            Path source = Path.of(args[0]);
            Path destination = Path.of(args[1]);
            if (Files.exists(destination))
                throw new IOException("Output already exists; choose a new path.");
            final int limit = 2 * 1024 * 1024;
            long length = Files.size(source);
            if (length == 0 || length > limit)
                throw new IOException("Request must be 1 byte to 2 MiB.");
            byte[] payload = Files.readAllBytes(source);
            String url = setting("BCSFE_API_URL", "https://battle-cats-save-file-editor-api.vercel.app").replaceAll("/+$", "") + "/v2/save/edit";
            HttpClient client = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(15))
                    .followRedirects(HttpClient.Redirect.NEVER)
                    .build();
            HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(120))
                    .header("Content-Type", "application/json")
                    .header("Accept", "application/octet-stream")
                    .POST(HttpRequest.BodyPublishers.ofByteArray(payload))
                    .build();
            HttpResponse<byte[]> response = client.send(request, HttpResponse.BodyHandlers.ofByteArray());
            if (response.statusCode() < 200 || response.statusCode() >= 300)
                throw new IOException("API returned HTTP " + response.statusCode() + ". No save was written.");
            String type = response.headers().firstValue("Content-Type").orElse("").split(";", 2)[0].trim();
            if (!type.equalsIgnoreCase("application/octet-stream"))
                throw new IOException("Expected a binary save; set output to file in the request JSON.");
            byte[] save = response.body();
            if (save.length == 0 || save.length > limit)
                throw new IOException("Response is empty or exceeds 2 MiB.");
            try (var output = Files.newOutputStream(destination, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
                try {
                    output.write(save);
                    output.flush();
                } catch (IOException error) {
                    output.close();
                    Files.deleteIfExists(destination);
                    throw error;
                }
            }
            System.out.println("Saved " + save.length + " bytes to " + destination);
        } catch (Exception error) {
            System.err.println(error.getMessage());
            System.exit(1);
        }
    }
}