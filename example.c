#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>

struct MemoryStruct {
    char *memory;
    size_t size;
};

static size_t WriteMemoryCallback(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t realsize = size * nmemb;
    struct MemoryStruct *mem = (struct MemoryStruct *)userp;
    char *ptr = realloc(mem->memory, mem->size + realsize + 1);
    if(!ptr) return 0;
    mem->memory = ptr;
    memcpy(&(mem->memory[mem->size]), contents, realsize);
    mem->size += realsize;
    mem->memory[mem->size] = 0;
    return realsize;
}

int main(void) {
    CURL *curl_handle;
    CURLcode res;
    struct MemoryStruct chunk = { malloc(1), 0 };

    const char *json_payload = "{\"transfer_code\":\"1a2b3c4d5\",\"confirmation_code\":\"1234\",\"country_code\":\"kr\",\"catfood\":45000}";

    curl_global_init(CURL_GLOBAL_ALL);
    curl_handle = curl_easy_init();

    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl_handle, CURLOPT_URL, "https://battle-cats-save-file-editor-api.vercel.app/edit");
    curl_easy_setopt(curl_handle, CURLOPT_POSTFIELDS, json_payload);
    curl_easy_setopt(curl_handle, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl_handle, CURLOPT_WRITEFUNCTION, WriteMemoryCallback);
    curl_easy_setopt(curl_handle, CURLOPT_WRITEDATA, (void *)&chunk);

    res = curl_easy_perform(curl_handle);

    if(res == CURLE_OK) {
        printf("Response:\n%s\n", chunk.memory);
    } else {
        fprintf(stderr, "curl_easy_perform() failed: %s\n", curl_easy_strerror(res));
    }

    curl_easy_cleanup(curl_handle);
    curl_slist_free_all(headers);
    free(chunk.memory);
    curl_global_cleanup();
    return 0;
}
