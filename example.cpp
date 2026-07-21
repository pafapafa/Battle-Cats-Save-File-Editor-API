#include <iostream>
#include <string>
#include <curl/curl.h>

static size_t WriteCallback(void* contents, size_t size, size_t nmemb, void* userp) {
    ((std::string*)userp)->append((char*)contents, size * nmemb);
    return size * nmemb;
}

int main() {
    CURL* curl = curl_easy_init();
    if (!curl) return 1;

    std::string readBuffer;
    const char* json_data = "{\"transfer_code\":\"1a2b3c4d5\",\"confirmation_code\":\"1234\",\"country_code\":\"kr\",\"catfood\":45000,\"unlock_cats\":true}";

    struct curl_slist* headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, "https://battle-cats-save-file-editor-api.vercel.app/edit");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, json_data);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &readBuffer);

    CURLcode res = curl_easy_perform(curl);
    if (res == CURLE_OK) {
        std::cout << "Response:\n" << readBuffer << std::endl;
    } else {
        std::cerr << "Request failed: " << curl_easy_strerror(res) << std::endl;
    }

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    return 0;
}
