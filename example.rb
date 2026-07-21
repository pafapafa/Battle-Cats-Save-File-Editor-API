require 'net/http'
require 'json'
require 'uri'

uri = URI.parse("https://battle-cats-save-file-editor-api.vercel.app/edit")
request = Net::HTTP::Post.new(uri)
request.content_type = "application/json"
request.body = JSON.dump({
  "transfer_code" => "1a2b3c4d5",
  "confirmation_code" => "1234",
  "country_code" => "kr",
  "catfood" => 45000,
  "unlock_cats" => true
})

response = Net::HTTP.start(uri.hostname, uri.port, use_ssl: true) do |http|
  http.request(request)
end

puts "Status: #{response.code}"
puts "Response: #{response.body}"
