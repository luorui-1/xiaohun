import 'package:flutter/material.dart';
import '../services/robot_api_service.dart';

class HistoryScreen extends StatefulWidget {
  final RobotApiService apiService;

  const HistoryScreen({super.key, required this.apiService});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Map<String, dynamic>> _history = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() {
      _isLoading = true;
    });
    final data = await widget.apiService.getHistory();
    setState(() {
      _history = data;
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('对话历史'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadHistory,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _history.isEmpty
          ? const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.chat_bubble_outline, size: 48, color: Colors.grey),
            SizedBox(height: 8),
            Text('暂无对话记录', style: TextStyle(color: Colors.grey)),
            SizedBox(height: 4),
            Text('和小智聊聊天吧！', style: TextStyle(color: Colors.grey, fontSize: 12)),
          ],
        ),
      )
          : ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _history.length,
        itemBuilder: (context, index) {
          final item = _history[index];
          final speaker = item['speaker'] ?? '';
          final text = item['text'] ?? '';
          final time = item['time'] ?? '';
          final isUser = speaker == 'user';

          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
              children: [
                if (!isUser)
                  CircleAvatar(
                    radius: 14,
                    backgroundColor: Colors.blue[700],
                    child: const Text('智', style: TextStyle(fontSize: 12, color: Colors.white)),
                  ),
                const SizedBox(width: 8),
                Flexible(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: isUser ? Colors.blue[800] : Colors.grey[800],
                      borderRadius: BorderRadius.only(
                        topLeft: const Radius.circular(12),
                        topRight: const Radius.circular(12),
                        bottomLeft: isUser ? const Radius.circular(12) : const Radius.circular(4),
                        bottomRight: isUser ? const Radius.circular(4) : const Radius.circular(12),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          text,
                          style: const TextStyle(fontSize: 14, color: Colors.white),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          time,
                          style: TextStyle(fontSize: 10, color: Colors.grey[500]),
                        ),
                      ],
                    ),
                  ),
                ),
                if (isUser)
                  const SizedBox(width: 8),
                if (isUser)
                  const CircleAvatar(
                    radius: 14,
                    backgroundColor: Colors.green,
                    child: Text('我', style: TextStyle(fontSize: 12, color: Colors.white)),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}