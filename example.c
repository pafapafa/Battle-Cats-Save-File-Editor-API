#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <curl/curl.h>

#define LIMIT (2U * 1024U * 1024U)

struct buffer { unsigned char *data; size_t size; };

static size_t receive(void *data, size_t size, size_t count, void *context) {
    struct buffer *buffer = context;
    if (size && count > SIZE_MAX / size) return 0;
    size_t length = size * count;
    if (length > LIMIT - buffer->size) return 0;
    unsigned char *next = realloc(buffer->data, buffer->size + length + 1);
    if (!next) return 0;
    buffer->data = next;
    memcpy(buffer->data + buffer->size, data, length);
    buffer->size += length;
    return length;
}

static int binary_type(const char *type) {
    const char *expected = "application/octet-stream";
    if (!type) return 0;
    while (*expected) {
        if (tolower((unsigned char)*type++) != *expected++) return 0;
    }
    while (*type == ' ' || *type == '\t') ++type;
    return *type == '\0' || *type == ';';
}

int main(int argc, char **argv) {
    int result = 1;
    FILE *input = NULL, *output = NULL;
    CURL *curl = NULL;
    struct curl_slist *headers = NULL;
    struct buffer response = {NULL, 0};
    unsigned char *payload = NULL;
    char *url = NULL, *authorization = NULL;
    const char *key = getenv("EDITOR_API_KEY");
    const char *base = getenv("BCSFE_API_URL");
    struct stat info;
    if (argc != 3) {
        fprintf(stderr, "Usage: %s REQUEST_JSON OUTPUT_SAVE\n", argv[0]);
        return 1;
    }
    if (!key || !*key) key = getenv("TEMPLATE_API_KEY");
    if (!key || !*key || strpbrk(key, "\r\n")) {
        fprintf(stderr, "Set EDITOR_API_KEY or TEMPLATE_API_KEY.\n");
        return 1;
    }
    if (stat(argv[2], &info) == 0) {
        fprintf(stderr, "Output already exists; choose a new path.\n");
        return 1;
    }
    if (!base || !*base) base = "https://battle-cats-save-file-editor-api.vercel.app";
    if (curl_global_init(CURL_GLOBAL_DEFAULT) != CURLE_OK) return 1;
    input = fopen(argv[1], "rb");
    if (!input || fseek(input, 0, SEEK_END) != 0) goto failure;
    long length = ftell(input);
    if (length <= 0 || length > LIMIT || fseek(input, 0, SEEK_SET) != 0) goto failure;
    payload = malloc((size_t)length);
    if (!payload || fread(payload, 1, (size_t)length, input) != (size_t)length) goto failure;
    fclose(input);
    input = NULL;
    size_t base_length = strlen(base);
    while (base_length && base[base_length - 1] == '/') --base_length;
    url = malloc(base_length + sizeof("/v2/save/edit"));
    authorization = malloc(strlen(key) + sizeof("Authorization: Bearer "));
    if (!url || !authorization) goto failure;
    memcpy(url, base, base_length);
    strcpy(url + base_length, "/v2/save/edit");
    sprintf(authorization, "Authorization: Bearer %s", key);
    const char *values[] = {"Content-Type: application/json", "Accept: application/octet-stream", authorization};
    for (size_t index = 0; index < sizeof(values) / sizeof(values[0]); ++index) {
        struct curl_slist *next = curl_slist_append(headers, values[index]);
        if (!next) goto failure;
        headers = next;
    }
    curl = curl_easy_init();
    if (!curl) goto failure;
    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE_LARGE, (curl_off_t)length);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, receive);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 15L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 120L);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 0L);
    CURLcode sent = curl_easy_perform(curl);
    if (sent != CURLE_OK) {
        fprintf(stderr, "Request failed: %s\n", curl_easy_strerror(sent));
        goto cleanup;
    }
    long status = 0;
    char *type = NULL;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);
    curl_easy_getinfo(curl, CURLINFO_CONTENT_TYPE, &type);
    if (status < 200 || status >= 300) {
        fprintf(stderr, "API returned HTTP %ld. No save was written.\n", status);
        goto cleanup;
    }
    if (!binary_type(type) || response.size == 0) {
        fprintf(stderr, "Expected a binary save; set output to file in the request JSON.\n");
        goto cleanup;
    }
    output = fopen(argv[2], "wbx");
    if (!output) goto failure;
    int written = fwrite(response.data, 1, response.size, output) == response.size;
    int closed = fclose(output) == 0;
    output = NULL;
    if (!written || !closed) {
        remove(argv[2]);
        goto failure;
    }
    printf("Saved %zu bytes to %s\n", response.size, argv[2]);
    result = 0;
    goto cleanup;
failure:
    fprintf(stderr, "Could not read the request or create the output. Request must be 1 byte to 2 MiB; output must not exist.\n");
cleanup:
    if (input) fclose(input);
    if (output) fclose(output);
    curl_easy_cleanup(curl);
    curl_slist_free_all(headers);
    free(response.data);
    free(payload);
    free(url);
    free(authorization);
    curl_global_cleanup();
    return result;
}