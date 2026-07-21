using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;

class Program
{
    private static readonly HttpClient client = new HttpClient();

    static async Task Main(string[] args)
    {
        string url = "https://battle-cats-save-file-editor-api.vercel.app/edit";
        string json = @"{
            ""transfer_code"": ""1a2b3c4d5"",
            ""confirmation_code"": ""1234"",
            ""country_code"": ""kr"",
            ""catfood"": 45000,
            ""unlock_cats"": true,
            ""max_treasures"": true
        }";

        var content = new StringContent(json, Encoding.UTF8, "application/json");
        HttpResponseMessage response = await client.PostAsync(url, content);
        string result = await response.Content.ReadAsStringAsync();

        Console.WriteLine("Response Status: " + response.StatusCode);
        Console.WriteLine("Response Body:\n" + result);
    }
}
