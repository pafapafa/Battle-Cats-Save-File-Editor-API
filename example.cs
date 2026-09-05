using System;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Threading.Tasks;

class Program
{
    static string Setting(string name, string fallback = "")
    {
        string? value = Environment.GetEnvironmentVariable(name);
        return string.IsNullOrEmpty(value) ? fallback : value;
    }

    static async Task<int> Main(string[] args)
    {
        try
        {
            if (args.Length != 2)
                throw new ArgumentException("Usage: example REQUEST_JSON OUTPUT_SAVE");
            if (File.Exists(args[1]) || Directory.Exists(args[1]))
                throw new IOException("Output already exists; choose a new path.");
            const int limit = 2 * 1024 * 1024;
            long length = new FileInfo(args[0]).Length;
            if (length == 0 || length > limit)
                throw new IOException("Request must be 1 byte to 2 MiB.");
            byte[] payload = await File.ReadAllBytesAsync(args[0]);
            string url = Setting("BCSFE_API_URL", "https://battle-cats-save-file-editor-api.vercel.app").TrimEnd('/') + "/v2/save/edit";
            using var handler = new SocketsHttpHandler
            {
                AllowAutoRedirect = false,
                ConnectTimeout = TimeSpan.FromSeconds(15)
            };
            using var client = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(120) };
            using var request = new HttpRequestMessage(HttpMethod.Post, url);
            request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/octet-stream"));
            request.Content = new ByteArrayContent(payload);
            request.Content.Headers.ContentType = new MediaTypeHeaderValue("application/json");
            using var response = await client.SendAsync(request);
            if (!response.IsSuccessStatusCode)
                throw new HttpRequestException($"API returned HTTP {(int)response.StatusCode}. No save was written.");
            if (!string.Equals(response.Content.Headers.ContentType?.MediaType, "application/octet-stream", StringComparison.OrdinalIgnoreCase))
                throw new IOException("Expected a binary save; set output to file in the request JSON.");
            byte[] save = await response.Content.ReadAsByteArrayAsync();
            if (save.Length == 0 || save.Length > limit)
                throw new IOException("Response is empty or exceeds 2 MiB.");
            await using (var output = new FileStream(args[1], FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                try
                {
                    await output.WriteAsync(save);
                    await output.FlushAsync();
                }
                catch
                {
                    await output.DisposeAsync();
                    File.Delete(args[1]);
                    throw;
                }
            }
            Console.WriteLine($"Saved {save.Length} bytes to {args[1]}");
            return 0;
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error.Message);
            return 1;
        }
    }
}