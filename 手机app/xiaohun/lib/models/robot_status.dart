class RobotStatus {
  final Emotion emotion;
  final Xiaozhi xiaozhi;
  final SystemInfo system;
  final double timestamp;

  RobotStatus({
    required this.emotion,
    required this.xiaozhi,
    required this.system,
    required this.timestamp,
  });

  factory RobotStatus.fromJson(Map<String, dynamic> json) {
    return RobotStatus(
      emotion: Emotion.fromJson(json['emotion'] ?? {}),
      xiaozhi: Xiaozhi.fromJson(json['xiaozhi'] ?? {}),
      system: SystemInfo.fromJson(json['system'] ?? {}),
      timestamp: json['timestamp']?.toDouble() ?? 0,
    );
  }
}

class Emotion {
  final String name;
  final double confidence;
  final String emoji;
  final String chinese;

  Emotion({
    required this.name,
    required this.confidence,
    required this.emoji,
    required this.chinese,
  });

  factory Emotion.fromJson(Map<String, dynamic> json) {
    return Emotion(
      name: json['name'] ?? 'neutral',
      confidence: json['confidence']?.toDouble() ?? 0,
      emoji: json['emoji'] ?? '😐',
      chinese: json['chinese'] ?? '平静',
    );
  }
}

class Xiaozhi {
  final bool enabled;

  Xiaozhi({required this.enabled});

  factory Xiaozhi.fromJson(Map<String, dynamic> json) {
    return Xiaozhi(enabled: json['enabled'] ?? false);
  }
}

class SystemInfo {
  final double cpu;
  final double memory;
  final double temperature;
  final double bpu;

  SystemInfo({
    required this.cpu,
    required this.memory,
    required this.temperature,
    required this.bpu,
  });

  factory SystemInfo.fromJson(Map<String, dynamic> json) {
    return SystemInfo(
      cpu: json['cpu']?.toDouble() ?? 0,
      memory: json['memory']?.toDouble() ?? 0,
      temperature: json['temperature']?.toDouble() ?? 0,
      bpu: json['bpu']?.toDouble() ?? 0,
    );
  }
}