import 'package:flutter/material.dart';
import 'screens/home_screen.dart';

void main() {
  runApp(const RobotMonitorApp());
}

class RobotMonitorApp extends StatelessWidget {
  const RobotMonitorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'RDK X5 监控器',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        primaryColor: Colors.blue,
        colorScheme: const ColorScheme.dark().copyWith(
          primary: Colors.blue,
        ),
        cardColor: Colors.grey[900],
      ),
      home: const HomeScreen(),
    );
  }
}