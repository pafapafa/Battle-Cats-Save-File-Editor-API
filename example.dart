import 'dart:convert';
import 'package:http/http.dart' as http;

void main() async {
  var url = Uri.parse('https://battle-cats-save-file-editor-api.vercel.app/edit');
  var response = await http.post(
    url,
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'transfer_code': '1a2b3c4d5',
      'confirmation_code': '1234',
      'country_code': 'kr',
      'catfood': 45000,
      'unlock_cats': true,
    }),
  );

  print('Response status: ${response.statusCode}');
  print('Response body: ${response.body}');
}
