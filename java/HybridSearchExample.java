import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;

/**
 * Sends the same Elasticsearch RRF hybrid search used by src/search.py.
 *
 * Requires Java 11+ only. The E5 query vector is prepared by the existing Python
 * pipeline and passed in ES_QUERY_VECTOR, so this small Java example has no libraries.
 */
public final class HybridSearchExample {
    private static final String INDEX = "fictional-bank-help-pages";
    private static final int RESULT_COUNT = 5;
    private static final int RRF_WINDOW = 50;
    private static final int RRF_RANK_CONSTANT = 60;

    private HybridSearchExample() {
        // This class only exposes main; do not create instances.
    }

    public static void main(String[] args) throws Exception {
        // 1. Read the same connection details that the Python application uses.
        String url = environment("ES_URL", "http://localhost:9200").replaceAll("/+$", "");
        String query = args.length == 0 ? "pas kwijt" : String.join(" ", args);
        String queryVector = requiredEnvironment("ES_QUERY_VECTOR");

        // 2. Keep the vector as JSON. Java does not need an embedding dependency to send it.
        if (!queryVector.startsWith("[") || !queryVector.endsWith("]")) {
            throw new IllegalArgumentException("ES_QUERY_VECTOR must be a JSON array of 384 E5 values.");
        }

        // 3. Build one request with a lexical retriever and a kNN retriever, fused by RRF.
        String requestBody = hybridRequest(query, queryVector);

        HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
                .uri(URI.create(url + "/" + INDEX + "/_search"))
                .timeout(Duration.ofSeconds(20))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody, StandardCharsets.UTF_8));

        // 4. Authentication is optional because the Docker demo disables security locally.
        addBasicAuthentication(requestBuilder);

        // 5. Send the request with the JDK client and print Elasticsearch's JSON response.
        HttpClient client = HttpClient.newHttpClient();
        HttpResponse<String> response = client.send(requestBuilder.build(), HttpResponse.BodyHandlers.ofString());
        System.out.println("Query: " + query);
        System.out.println("HTTP " + response.statusCode());
        System.out.println(response.body());

        if (response.statusCode() >= 300) {
            throw new IllegalStateException("Elasticsearch did not accept the hybrid request.");
        }
    }

    private static String hybridRequest(String query, String queryVector) {
        String escapedQuery = jsonString(query);
        return "{"
                + "\"retriever\":{\"rrf\":{"
                + "\"retrievers\":["
                + "{\"standard\":{\"query\":{\"multi_match\":{"
                + "\"query\":" + escapedQuery + ","
                + "\"fields\":[\"title^3\",\"body\",\"summary^1.5\"]"
                + "}}},"
                + "{\"knn\":{"
                + "\"field\":\"embedding\","
                + "\"query_vector\":" + queryVector + ","
                + "\"k\":" + RRF_WINDOW + ","
                + "\"num_candidates\":100"
                + "}}"
                + "],"
                + "\"rank_constant\":" + RRF_RANK_CONSTANT + ","
                + "\"rank_window_size\":" + RRF_WINDOW
                + "}},"
                + "\"size\":" + RESULT_COUNT + ","
                + "\"_source\":{\"excludes\":[\"embedding\"]}"
                + "}";
    }

    private static void addBasicAuthentication(HttpRequest.Builder requestBuilder) {
        String username = environment("ES_USERNAME", "");
        String password = environment("ES_PASSWORD", "");
        if (username.isEmpty() && password.isEmpty()) {
            return;
        }
        if (username.isEmpty() || password.isEmpty()) {
            throw new IllegalArgumentException("Set both ES_USERNAME and ES_PASSWORD, or neither.");
        }
        String credentials = username + ":" + password;
        String encoded = Base64.getEncoder().encodeToString(credentials.getBytes(StandardCharsets.UTF_8));
        requestBuilder.header("Authorization", "Basic " + encoded);
    }

    private static String environment(String name, String defaultValue) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? defaultValue : value;
    }

    private static String requiredEnvironment(String name) {
        String value = environment(name, "");
        if (value.isEmpty()) {
            throw new IllegalArgumentException("Set " + name + ". See java/README.md for the E5 command.");
        }
        return value;
    }

    private static String jsonString(String value) {
        return "\"" + value.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t") + "\"";
    }
}
