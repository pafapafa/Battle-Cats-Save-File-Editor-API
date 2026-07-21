import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

public class example {
    public static void main(String[] args) throws Exception {
        String url = "https://battle-cats-save-file-editor-api.vercel.app/edit";
        String jsonPayload = """
            {
                "transfer_code": "1a2b3c4d5",
                "confirmation_code": "1234",
                "country_code": "kr",
                "catfood": 45000,
                "unlock_cats": true
            }
            """;

        HttpClient client = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(jsonPayload))
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        System.out.println("Response Status: " + response.statusCode());
        System.out.println("Response Body:\n" + response.body());
    }
}
