import 'dart:async';
import 'package:flutter/material.dart';
import '../services/robot_api_service.dart';
import '../models/robot_status.dart';
import '../utils/constants.dart';
import '../widgets/emotion_display.dart';
import '../widgets/status_card.dart';
import '../widgets/system_info.dart';
import 'settings_screen.dart';
import 'camera_screen.dart';
import 'history_screen.dart';  // ← 新增

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late RobotApiService _apiService;
  RobotStatus? _status;
  bool _isConnected = false;
  bool _isLoading = true;
  Timer? _timer;
  String _ip = AppConstants.defaultIp;

  @override
  void initState() {
    super.initState();
    _initApiService();
  }

  void _initApiService() {
    _apiService = RobotApiService(
      baseUrl: AppConstants.getBaseUrl(_ip),
      streamUrl: AppConstants.getStreamUrl(_ip),
    );
    _fetchStatus();
    _timer = Timer.periodic(
      const Duration(seconds: AppConstants.updateInterval),
          (timer) => _fetchStatus(),
    );
  }

  Future<void> _fetchStatus() async {
    try {
      final status = await _apiService.getStatus();
      setState(() {
        _status = status;
        _isConnected = true;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _isConnected = false;
        _isLoading = false;
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _apiService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('RDK X5 监控器'),
        actions: [
          IconButton(
            icon: Icon(
              _isConnected ? Icons.wifi : Icons.wifi_off,
              color: _isConnected ? Colors.green : Colors.red,
            ),
            onPressed: _fetchStatus,
            tooltip: '刷新',
          ),
          IconButton(
            icon: const Icon(Icons.videocam),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => CameraScreen(
                    cameraStreamUrl: _apiService.getCameraStreamUrl(),
                  ),
                ),
              );
            },
            tooltip: '摄像头',
          ),
          // ===== 新增：对话历史按钮 =====
          IconButton(
            icon: const Icon(Icons.history),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => HistoryScreen(apiService: _apiService),
                ),
              );
            },
            tooltip: '对话历史',
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () async {
              final newIp = await Navigator.push<String>(
                context,
                MaterialPageRoute(
                  builder: (context) => SettingsScreen(currentIp: _ip),
                ),
              );
              if (newIp != null && newIp != _ip) {
                setState(() {
                  _ip = newIp;
                  _apiService.dispose();
                  _initApiService();
                });
              }
            },
            tooltip: '设置',
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (!_isConnected) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.wifi_off, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            const Text('未连接到机器人', style: TextStyle(fontSize: 18)),
            const SizedBox(height: 8),
            Text('请检查 IP: $_ip', style: TextStyle(color: Colors.grey)),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _fetchStatus,
              child: const Text('重新连接'),
            ),
          ],
        ),
      );
    }

    if (_status == null) {
      return const Center(child: Text('暂无数据'));
    }

    final status = _status!;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          EmotionDisplay(emotion: status.emotion),
          const SizedBox(height: 16),
          StatusCard(
            title: '功能状态',
            children: [
              StatusItem(
                icon: Icons.mic,
                label: '小智语音',
                value: status.xiaozhi.enabled ? '已开启' : '已关闭',
                isActive: status.xiaozhi.enabled,
              ),
            ],
          ),
          const SizedBox(height: 16),
          SystemInfoWidget(system: status.system),
          const SizedBox(height: 16),
          Text(
            '最后更新: ${DateTime.fromMillisecondsSinceEpoch((status.timestamp * 1000).toInt()).toString().substring(0, 19)}',
            style: TextStyle(
              color: Colors.grey[600],
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}