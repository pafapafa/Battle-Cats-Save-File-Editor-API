import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

const maxBytes = 2 * 1024 * 1024;

Future<Uint8List> download(Uri uri, String token, Uint8List body) async {
  final client = HttpClient()..connectionTimeout = const Duration(seconds: 15);
  try {
    return await (() async {
      final request = await client.postUrl(uri);
      request.followRedirects = false;
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.acceptHeader, 'application/octet-stream');
      request.contentLength = body.length;
      request.add(body);
      final response = await request.close();
      if (response.statusCode < 200 || response.statusCode >= 300 ||
          response.headers.contentType?.mimeType.toLowerCase() != 'application/octet-stream') {
        throw HttpException('Expected a binary success response; HTTP ${response.statusCode}');
      }
      if (response.contentLength > maxBytes) throw const HttpException('Response exceeds 2 MiB');
      final data = BytesBuilder(copy: false);
      await for (final chunk in response) {
        if (data.length + chunk.length > maxBytes) throw const HttpException('Response exceeds 2 MiB');
        data.add(chunk);
      }
      return data.takeBytes();
    })().timeout(const Duration(seconds: 120));
  } finally {
    client.close(force: true);
  }
}

Future<void> main(List<String> arguments) async {
  var created = false;
  File? output;
  try {
    if (arguments.length != 2) throw const FormatException('Usage: dart run example.dart REQUEST_JSON OUTPUT_SAVE');
    final input = File(arguments[0]);
    output = File(arguments[1]);
    if (await FileSystemEntity.type(output.path, followLinks: false) != FileSystemEntityType.notFound) {
      throw const FileSystemException('Output already exists');
    }
    var token = (Platform.environment['EDITOR_API_KEY'] ?? '').trim();
    if (token.isEmpty) token = (Platform.environment['TEMPLATE_API_KEY'] ?? '').trim();
    if (token.isEmpty) throw const FormatException('Set EDITOR_API_KEY or TEMPLATE_API_KEY');
    final base = (Platform.environment['BCSFE_API_URL'] ?? 'https://battle-cats-save-file-editor-api.vercel.app').replaceFirst(RegExp(r'/+$'), '');
    final uri = Uri.parse('$base/v2/save/edit');
    if (!['http', 'https'].contains(uri.scheme) || uri.host.isEmpty ||
        uri.userInfo.isNotEmpty || uri.hasQuery || uri.hasFragment) {
      throw const FormatException('BCSFE_API_URL must be an HTTP(S) base URL without credentials, query, or fragment');
    }
    if (await input.length() > maxBytes) throw const FormatException('Request exceeds 2 MiB');
    final body = await input.readAsBytes();
    if (body.length > maxBytes) throw const FormatException('Request exceeds 2 MiB');
    dynamic payload;
    try {
      payload = jsonDecode(utf8.decode(body));
    } on FormatException {
      throw const FormatException('Request must be valid UTF-8 JSON');
    }
    if (payload is! Map<String, dynamic> || payload['output'] != 'file' ||
        payload['country_code'] is! String || payload['save_base64'] is! String || payload['operations'] is! List) {
      throw const FormatException('Request needs country_code, save_base64, operations, and output:"file"');
    }
    final data = await download(uri, token, body);
    await output.create(exclusive: true);
    created = true;
    await output.writeAsBytes(data, flush: true);
    created = false;
    stdout.writeln('Saved ${data.length} bytes to ${output.path}');
  } catch (error) {
    if (created && output != null) await output.delete();
    stderr.writeln(error);
    exitCode = 1;
  }
}
