class AppConstants {
  static const String defaultIp = '192.168.12.160';
  static const int apiPort = 5000;
  static const int streamPort = 5005;
  static const int updateInterval = 1;

  static String getBaseUrl(String ip) {
    return 'http://$ip:$apiPort';
  }

  static String getStreamUrl(String ip) {
    return 'http://$ip:$streamPort/stream';
  }
}