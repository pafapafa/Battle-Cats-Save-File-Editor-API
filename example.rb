require 'net/http'
require 'json'
require 'uri'
require 'timeout'

MAX_BYTES = 2 * 1024 * 1024

def main
  raise 'Usage: ruby example.rb REQUEST_JSON OUTPUT_SAVE' unless ARGV.length == 2
  input, output = ARGV
  raise 'Output already exists' if File.exist?(output) || File.symlink?(output)
  base = ENV.fetch('BCSFE_API_URL', 'https://battle-cats-save-file-editor-api.vercel.app').sub(%r{/+\z}, '')
  url = URI.parse("#{base}/v2/save/edit")
  unless %w[http https].include?(url.scheme) && url.host && !url.userinfo && !url.query && !url.fragment
    raise 'BCSFE_API_URL must be an HTTP(S) base URL without credentials, query, or fragment'
  end
  raise 'Request exceeds 2 MiB' if File.size(input) > MAX_BYTES
  body = File.binread(input)
  raise 'Request exceeds 2 MiB' if body.bytesize > MAX_BYTES
  begin
    payload = JSON.parse(body)
  rescue JSON::ParserError
    raise 'Request must be valid UTF-8 JSON'
  end
  unless payload.is_a?(Hash) && payload['output'] == 'file' && payload['country_code'].is_a?(String) &&
         payload['save_base64'].is_a?(String) && payload['operations'].is_a?(Array)
    raise 'Request needs country_code, save_base64, operations, and output:"file"'
  end
  request = Net::HTTP::Post.new(url.request_uri)
  request['Content-Type'] = 'application/json'
  request['Accept'] = 'application/octet-stream'
  request.body = body
  client = Net::HTTP.new(url.host, url.port)
  client.use_ssl = url.scheme == 'https'
  client.open_timeout = 15
  client.read_timeout = 120
  client.write_timeout = 120
  data = String.new(encoding: Encoding::BINARY)
  Timeout.timeout(120) do
    client.start do |connection|
      connection.request(request) do |response|
        status = response.code.to_i
        content_type = response['content-type'].to_s.split(';').first.to_s.strip.downcase
        unless status.between?(200, 299) && content_type == 'application/octet-stream'
          raise "Expected a binary success response; HTTP #{status}"
        end
        expected_length = response['content-length']&.to_i
        response.read_body do |chunk|
          raise 'Response exceeds 2 MiB' if data.bytesize + chunk.bytesize > MAX_BYTES
          data << chunk
        end
        raise 'Incomplete binary response' if expected_length && data.bytesize != expected_length
      end
    end
  end
  created = false
  begin
    File.open(output, File::WRONLY | File::CREAT | File::EXCL, 0o600) do |file|
      created = true
      file.binmode
      file.write(data)
      file.flush
    end
  rescue StandardError
    File.delete(output) if created
    raise
  end
  puts "Saved #{data.bytesize} bytes to #{output}"
end

begin
  main
rescue StandardError => error
  warn error.message
  exit 1
end
