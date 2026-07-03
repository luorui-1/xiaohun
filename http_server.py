#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
HTTP API 服务器 - 为手机App提供RDK X5状态信息
"""

import json
import time
import threading
import os
import subprocess
import sys
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
import cv2
import numpy as np
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge
import psutil

app = Flask(__name__)
CORS(app)

# ============================================================================
# 对话历史存储
# ============================================================================

conversation_history = []
max_history = 100

def add_conversation(speaker, text):
    """添加对话记录"""
    global conversation_history
    if not text or text.strip() == '':
        return
    entry = {
        'time': time.strftime('%H:%M:%S'),
        'speaker': speaker,
        'text': text
    }
    conversation_history.append(entry)
    if len(conversation_history) > max_history:
        conversation_history.pop(0)

# ============================================================================
# 工具函数
# ============================================================================

def get_wlan0_ip():
    try:
        result = subprocess.run(['ip', 'addr', 'show', 'wlan0'],
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'inet ' in line:
                    ip = line.strip().split()[1].split('/')[0]
                    return ip
    except:
        pass
    return '127.0.0.1'

def get_bpu_usage():
    try:
        result = subprocess.run(
            "hrut_bpuprofile -b 0 -r 1 2>/dev/null | tail -1 | awk '{print $2}' | tr -d '%'",
            shell=True, capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and result.stdout:
            val = result.stdout.strip()
            if val and val.replace('.', '').isdigit():
                return float(val)
    except:
        pass
    
    try:
        result = subprocess.run(
            "ps aux | grep -E 'hobot_usb_cam|hobot_codec|cam-service' | grep -v grep | awk '{sum+=$3} END {print sum}'",
            shell=True, capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and result.stdout:
            val = result.stdout.strip()
            if val and float(val) > 0:
                return float(val)
    except:
        pass
    
    return 0.0

def get_system_stats():
    state.cpu_usage = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    state.memory_usage = mem.percent
    try:
        temp = subprocess.check_output("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0", shell=True).decode().strip()
        state.temperature = int(temp) / 1000 if temp else 0
    except:
        state.temperature = 0
    state.bpu_usage = get_bpu_usage()

# ============================================================================
# 全局状态存储
# ============================================================================

class RobotState:
    def __init__(self):
        self.emotion = "neutral"
        self.emotion_confidence = 0.0
        self.emotion_emoji = "😐"
        self.emotion_chinese = "平静"
        self.xiaozhi_status = False
        self.cpu_usage = 0
        self.memory_usage = 0
        self.temperature = 0
        self.bpu_usage = 0
        self.last_update = time.time()
        self.camera_frame = None
        self.frame_lock = threading.Lock()
        self.frame_counter = 0

state = RobotState()
bridge = CvBridge()

# ============================================================================
# ROS2 节点 - 订阅话题
# ============================================================================

class StateSubscriber(Node):
    def __init__(self):
        super().__init__('http_api_subscriber')
        
        self.emotion_sub = self.create_subscription(
            String,
            '/user_emotion',
            self.emotion_callback,
            10
        )
        
        self.xiaozhi_sub = self.create_subscription(
            Bool,
            '/xiaozhi_video',
            self.xiaozhi_callback,
            10
        )
        
        # 订阅机器人语音指令（用于记录对话）
        self.speech_sub = self.create_subscription(
            String,
            '/robot_speech',
            self.speech_callback,
            10
        )
        
        self.image_sub = self.create_subscription(
            CompressedImage,
            '/image',
            self.image_callback,
            10
        )
        
        self.get_logger().info("✅ HTTP API 状态订阅节点已启动")
    
    def emotion_callback(self, msg):
        try:
            data = json.loads(msg.data)
            state.emotion = data.get('emotion', 'neutral')
            state.emotion_confidence = data.get('confidence', 0.0)
            state.emotion_emoji = data.get('emoji', '😐')
            state.emotion_chinese = data.get('chinese', '平静')
            state.last_update = time.time()
        except Exception as e:
            pass
    
    def xiaozhi_callback(self, msg):
        state.xiaozhi_status = msg.data
    
    def speech_callback(self, msg):
        text = msg.data
        self.get_logger().info(f"🔊 http_server收到语音指令: {text}")
        if text and text.strip():
            add_conversation('bot', text)
            self.get_logger().info(f" 记录对话: {text}")
    
    def image_callback(self, msg):
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if frame is not None:
                state.frame_counter += 1
                with state.frame_lock:
                    _, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    state.camera_frame = jpg.tobytes()
        except Exception as e:
            pass

def ros_spin():
    rclpy.init(args=None)
    node = StateSubscriber()
    rclpy.spin(node)

# ============================================================================
# HTTP API 接口
# ============================================================================

@app.route('/api/status', methods=['GET'])
def get_status():
    get_system_stats()
    return jsonify({
        'emotion': {
            'name': state.emotion,
            'confidence': state.emotion_confidence,
            'emoji': state.emotion_emoji,
            'chinese': state.emotion_chinese
        },
        'xiaozhi': {
            'enabled': state.xiaozhi_status
        },
        'system': {
            'cpu': round(state.cpu_usage, 1),
            'memory': round(state.memory_usage, 1),
            'temperature': round(state.temperature, 1),
            'bpu': round(state.bpu_usage, 1)
        },
        'timestamp': time.time()
    })

@app.route('/api/camera', methods=['GET'])
def get_camera():
    with state.frame_lock:
        if state.camera_frame is None:
            return Response(status=204)
        return Response(state.camera_frame, mimetype='image/jpeg')

@app.route('/api/camera_stream')
def camera_stream():
    def generate():
        while True:
            with state.frame_lock:
                if state.camera_frame is not None:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + 
                           state.camera_frame + b'\r\n')
            time.sleep(0.05)
    return Response(stream_with_context(generate()), 
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/emotions', methods=['GET'])
def get_emotions():
    return jsonify({
        'current': {
            'name': state.emotion,
            'confidence': state.emotion_confidence,
            'emoji': state.emotion_emoji,
            'chinese': state.emotion_chinese
        },
        'timestamp': state.last_update
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    """获取对话历史记录"""
    return jsonify(conversation_history)

@app.route('/api/history/add', methods=['POST'])
def add_history():
    """手动添加对话记录"""
    try:
        data = request.get_json()
        speaker = data.get('speaker', 'bot')
        text = data.get('text', '')
        if text:
            add_conversation(speaker, text)
            return jsonify({'status': 'ok'})
        return jsonify({'status': 'error', 'message': 'text is empty'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'uptime': time.time()})

if __name__ == '__main__':
    try:
        import psutil
    except ImportError:
        print(" psutil 未安装，正在尝试安装...")
        os.system("pip3 install psutil")
        import psutil
    
    ros_thread = threading.Thread(target=ros_spin, daemon=True)
    ros_thread.start()
    
    ip = get_wlan0_ip()
    print("=" * 60)
    print(" HTTP API 服务器启动")
    print("=" * 60)
    print(f" 访问地址: http://{ip}:5000")
    print(f"   - 状态接口: /api/status")
    print(f"   - 摄像头接口: /api/camera")
    print(f"   - 实时视频流: /api/camera_stream")
    print(f"   - 对话历史: /api/history")
    print(f"   - 健康检查: /health")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)