#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <curl/curl.h>

constexpr std::size_t limit = 2U * 1024U * 1024U;

struct CurlRuntime {
    CurlRuntime() {
        if (curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK)
            throw std::runtime_error("Could not initialize HTTP client.");
    }
    ~CurlRuntime() { curl_global_cleanup(); }
};

struct Headers {
    curl_slist *value = nullptr;
    void add(const std::string &header) {
        auto next = curl_slist_append(value, header.c_str());
        if (!next) throw std::bad_alloc();
        value = next;
    }
    ~Headers() { curl_slist_free_all(value); }
};

std::string environment(const char *name, const std::string &fallback = "") {
    const auto value = std::getenv(name);
    return value && *value ? value : fallback;
}

std::size_t receive(char *data, std::size_t size, std::size_t count, void *context) noexcept {
    auto &response = *static_cast<std::string *>(context);
    if (size && count > std::numeric_limits<std::size_t>::max() / size) return 0;
    auto length = size * count;
    if (length > limit - response.size()) return 0;
    try { response.append(data, length); }
    catch (...) { return 0; }
    return length;
}

int main(int argc, char **argv) {
    try {
        if (argc != 3) throw std::runtime_error("Usage: example REQUEST_JSON OUTPUT_SAVE");
        auto key = environment("EDITOR_API_KEY", environment("TEMPLATE_API_KEY"));
        if (key.empty() || key.find_first_of("\r\n") != std::string::npos)
            throw std::runtime_error("Set EDITOR_API_KEY or TEMPLATE_API_KEY.");
        if (std::filesystem::exists(argv[2]))
            throw std::runtime_error("Output already exists; choose a new path.");
        auto length = std::filesystem::file_size(argv[1]);
        if (length == 0 || length > limit) throw std::runtime_error("Request must be 1 byte to 2 MiB.");
        std::ifstream input(argv[1], std::ios::binary);
        std::string payload(static_cast<std::size_t>(length), '\0');
        if (!input.read(payload.data(), static_cast<std::streamsize>(payload.size())))
            throw std::runtime_error("Could not read request file.");
        input.close();
        auto url = environment("BCSFE_API_URL", "https://battle-cats-save-file-editor-api.vercel.app");
        while (!url.empty() && url.back() == '/') url.pop_back();
        url += "/v2/save/edit";
        CurlRuntime runtime;
        std::unique_ptr<CURL, decltype(&curl_easy_cleanup)> curl(curl_easy_init(), curl_easy_cleanup);
        if (!curl) throw std::runtime_error("Could not initialize HTTP request.");
        Headers headers;
        headers.add("Content-Type: application/json");
        headers.add("Accept: application/octet-stream");
        headers.add("Authorization: Bearer " + key);
        std::string response;
        curl_easy_setopt(curl.get(), CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl.get(), CURLOPT_HTTPHEADER, headers.value);
        curl_easy_setopt(curl.get(), CURLOPT_POSTFIELDS, payload.data());
        curl_easy_setopt(curl.get(), CURLOPT_POSTFIELDSIZE_LARGE, static_cast<curl_off_t>(payload.size()));
        curl_easy_setopt(curl.get(), CURLOPT_WRITEFUNCTION, receive);
        curl_easy_setopt(curl.get(), CURLOPT_WRITEDATA, &response);
        curl_easy_setopt(curl.get(), CURLOPT_CONNECTTIMEOUT, 15L);
        curl_easy_setopt(curl.get(), CURLOPT_TIMEOUT, 120L);
        curl_easy_setopt(curl.get(), CURLOPT_FOLLOWLOCATION, 0L);
        auto sent = curl_easy_perform(curl.get());
        if (sent != CURLE_OK) throw std::runtime_error(curl_easy_strerror(sent));
        long status = 0;
        char *content_type = nullptr;
        curl_easy_getinfo(curl.get(), CURLINFO_RESPONSE_CODE, &status);
        curl_easy_getinfo(curl.get(), CURLINFO_CONTENT_TYPE, &content_type);
        if (status < 200 || status >= 300)
            throw std::runtime_error("API returned HTTP " + std::to_string(status) + ". No save was written.");
        std::string type = content_type ? content_type : "";
        type = type.substr(0, type.find(';'));
        while (!type.empty() && std::isspace(static_cast<unsigned char>(type.back()))) type.pop_back();
        for (auto &character : type) character = static_cast<char>(std::tolower(static_cast<unsigned char>(character)));
        if (type != "application/octet-stream" || response.empty())
            throw std::runtime_error("Expected a binary save; set output to file in the request JSON.");
        auto output = std::fopen(argv[2], "wbx");
        if (!output) throw std::runtime_error("Cannot create output; it must not already exist.");
        bool written = std::fwrite(response.data(), 1, response.size(), output) == response.size();
        bool closed = std::fclose(output) == 0;
        if (!written || !closed) {
            std::remove(argv[2]);
            throw std::runtime_error("Could not write the complete save.");
        }
        std::cout << "Saved " << response.size() << " bytes to " << argv[2] << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}