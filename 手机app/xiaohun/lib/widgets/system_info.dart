import 'package:flutter/material.dart';
import '../models/robot_status.dart';

class SystemInfoWidget extends StatelessWidget {
  final SystemInfo system;

  const SystemInfoWidget({super.key, required this.system});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '系统状态',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _buildSystemItem(
                    label: 'CPU',
                    value: '${system.cpu.toStringAsFixed(1)}%',
                    color: _getUsageColor(system.cpu),
                    icon: Icons.memory,
                  ),
                ),
                Expanded(
                  child: _buildSystemItem(
                    label: '内存',
                    value: '${system.memory.toStringAsFixed(1)}%',
                    color: _getUsageColor(system.memory),
                    icon: Icons.storage,
                  ),
                ),
                Expanded(
                  child: _buildSystemItem(
                    label: 'BPU',
                    value: '${system.bpu.toStringAsFixed(1)}%',
                    color: _getUsageColor(system.bpu),
                    icon: Icons.speed,
                  ),
                ),
                Expanded(
                  child: _buildSystemItem(
                    label: '温度',
                    value: '${system.temperature.toStringAsFixed(1)}°C',
                    color: _getTemperatureColor(system.temperature),
                    icon: Icons.thermostat,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSystemItem({
    required String label,
    required String value,
    required Color color,
    required IconData icon,
  }) {
    return Column(
      children: [
        Icon(icon, color: color, size: 24),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            color: Colors.grey[500],
          ),
        ),
      ],
    );
  }

  Color _getUsageColor(double value) {
    if (value < 50) return Colors.green;
    if (value < 70) return Colors.orange;
    return Colors.red;
  }

  Color _getTemperatureColor(double value) {
    if (value < 70) {
      return Colors.green;
    } else if (value < 75) {
      return Colors.orange;
    } else if (value < 80) {
      return Colors.deepOrange;
    } else {
      return Colors.red;
    }
  }
}