import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/robot_status.dart';

class RobotApiService {
  static const int timeout = 3;

  final String baseUrl;
  final String streamUrl;
  final http.Client client;

  RobotApiService({
    required this.baseUrl,
    required this.streamUrl,
    http.Client? client,
  }) : client = client ?? http.Client();

  Future<RobotStatus> getStatus() async {
    try {
      final response = await client
          .get(
        Uri.parse('$baseUrl/api/status'),
        headers: {'Content-Type': 'application/json'},
      )
          .timeout(const Duration(seconds: timeout));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return RobotStatus.fromJson(data);
      } else {
        throw Exception('HTTP Error: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('连接失败: $e');
    }
  }

  String getCameraUrl() {
    return '$baseUrl/api/camera';
  }

  String getCameraStreamUrl() {
    return streamUrl;
  }

  // ===== 新增：获取对话历史 =====
  Future<List<Map<String, dynamic>>> getHistory() async {
    try {
      final response = await client
          .get(
        Uri.parse('$baseUrl/api/history'),
        headers: {'Content-Type': 'application/json'},
      )
          .timeout(const Duration(seconds: 3));

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data is List) {
          return data.map((item) => Map<String, dynamic>.from(item)).toList();
        }
        return [];
      } else {
        throw Exception('HTTP Error: ${response.statusCode}');
      }
    } catch (e) {
      print('获取历史记录失败: $e');
      return [];
    }
  }

  Future<bool> healthCheck() async {
    try {
      final response = await client
          .get(Uri.parse('$baseUrl/health'))
          .timeout(const Duration(seconds: 2));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  void dispose() {
    client.close();
  }
}