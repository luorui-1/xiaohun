import 'package:flutter/material.dart';
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

class CameraScreen extends StatefulWidget {
  final String cameraStreamUrl;

  const CameraScreen({super.key, required this.cameraStreamUrl});

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen> {
  String? _imageBase64;
  Timer? _timer;
  bool _isLoading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _fetchImage();
    _timer = Timer.periodic(const Duration(milliseconds: 300), (timer) {
      _fetchImage();
    });
  }

  Future<void> _fetchImage() async {
    try {
      final url = '${widget.cameraStreamUrl}?t=${DateTime.now().millisecondsSinceEpoch}';
      final response = await http.get(
        Uri.parse(url),
        headers: {
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      ).timeout(const Duration(seconds: 5));  // ← 改成 5 秒

      if (response.statusCode == 200 && response.bodyBytes.isNotEmpty) {
        if (mounted) {
          setState(() {
            _imageBase64 = base64Encode(response.bodyBytes);
            _isLoading = false;
            _error = '';
          });
        }
      } else {
        throw Exception('HTTP ${response.statusCode}');
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
        });
      }
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('实时摄像头'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              setState(() {
                _isLoading = true;
                _error = '';
              });
              _fetchImage();
            },
          ),
        ],
      ),
      body: Container(
        color: Colors.black,
        child: Center(
          child: _buildContent(),
        ),
      ),
    );
  }

  Widget _buildContent() {
    if (_error.isNotEmpty) {
      return Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 48, color: Colors.red),
          const SizedBox(height: 8),
          Text(
            '加载失败: $_error',
            style: const TextStyle(color: Colors.white, fontSize: 12),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: () {
              setState(() {
                _error = '';
                _isLoading = true;
              });
              _fetchImage();
            },
            child: const Text('重试'),
          ),
        ],
      );
    }

    if (_isLoading) {
      return const Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(color: Colors.white),
          SizedBox(height: 8),
          Text('加载中...', style: TextStyle(color: Colors.white)),
        ],
      );
    }

    if (_imageBase64 == null) {
      return const Text('无数据', style: TextStyle(color: Colors.white));
    }

    return Image.memory(
      base64Decode(_imageBase64!),
      fit: BoxFit.contain,
      width: double.infinity,
      height: double.infinity,
      gaplessPlayback: true,
      errorBuilder: (context, error, stackTrace) {
        return const Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.image_not_supported, size: 48, color: Colors.red),
            SizedBox(height: 8),
            Text('解码失败', style: TextStyle(color: Colors.white)),
          ],
        );
      },
    );
  }
}