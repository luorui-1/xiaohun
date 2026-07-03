import 'package:flutter/material.dart';
import '../models/robot_status.dart';

class EmotionDisplay extends StatelessWidget {
  final Emotion emotion;

  const EmotionDisplay({super.key, required this.emotion});

  @override
  Widget build(BuildContext context) {
    final confidencePercent = (emotion.confidence * 100).toStringAsFixed(1);

    Color getEmotionColor(String name) {
      switch (name) {
        case 'happy':
          return Colors.green;
        case 'sad':
          return Colors.blue;
        case 'angry':
          return Colors.red;
        default:
          return Colors.grey;
      }
    }

    final color = getEmotionColor(emotion.name);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 60,
              height: 60,
              decoration: BoxDecoration(
                color: color.withOpacity(0.2),
                borderRadius: BorderRadius.circular(30),
              ),
              child: Center(
                child: Text(
                  emotion.emoji,
                  style: const TextStyle(fontSize: 32),
                ),
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '当前表情',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    emotion.chinese,
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: color,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Row(
                    children: [
                      Expanded(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(4),
                          child: LinearProgressIndicator(
                            value: emotion.confidence,
                            backgroundColor: Colors.grey[800],
                            valueColor: AlwaysStoppedAnimation<Color>(color),
                            minHeight: 6,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        '$confidencePercent%',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[500],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}