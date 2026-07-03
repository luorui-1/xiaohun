#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String
import cv2
import numpy as np
from scipy.special import softmax
from time import time, sleep
from hobot_dnn import pyeasy_dnn as dnn
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os
import signal
import sys
import json

# ====================== 配置 ======================
quantize_model_path = "/home/sunrise/bibuting/yolov8s_emotion_modified.bin"
conf = 0.3
conf_inverse = -np.log(1/conf - 1)

# 表情映射
emotion_labels = {0: "happy", 1: "sad", 2: "angry", 3: "neutral"}
emotion_colors = {"happy": (0,255,0), "sad": (255,0,0), "angry": (0,0,255), "neutral": (128,128,128)}
emotion_emoji = {"neutral": "😐", "happy": "😊", "sad": "😢", "angry": "😠"}
emotion_chinese = {"happy": "开心", "sad": "难过", "angry": "生气", "neutral": "平静"}

# 表情对应的动画名称（与emotions文件夹中的文件夹名对应）
emotion_animation_map = {
    "happy": "happy",      # 使用 happy 动画
    "sad": "sad",          # 使用 sad 动画
    "angry": "angry",      # 使用 angry 动画
    "neutral": "neutral"   # 使用 neutral 动画
}

# 全局变量
current_frame = None
frame_lock = threading.Lock()
server_running = True

# ===== 存储当前检测到的表情 =====
current_emotion = "neutral"
current_confidence = 0.0
emotion_lock = threading.Lock()

# ===== 表情变化检测 =====
last_emotion = "neutral"
last_emotion_change_time = 0
emotion_change_cooldown = 1.0  # 1秒冷却，防止频繁触发

def signal_handler(sig, frame):
    global server_running
    print("\n正在关闭服务器...")
    server_running = False
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# ====================== 图像处理 ======================
def bgr2nv12(image):
    h, w = image.shape[:2]
    yuv = cv2.cvtColor(image, cv2.COLOR_BGR2YUV_I420)
    y = yuv[:h]
    u = yuv[h:h + h//4].reshape(-1)
    v = yuv[h + h//4:].reshape(-1)
    uv = np.empty(h // 2 * w, dtype=np.uint8)
    uv[0::2] = u
    uv[1::2] = v
    uv = uv.reshape(h // 2, w)
    return np.concatenate([y, uv], axis=0)

def draw_emotion_box(img, box, emotion_name, score):
    x1, y1, x2, y2 = box
    color = emotion_colors.get(emotion_name, (0,255,0))
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)
    label = f"{emotion_emoji.get(emotion_name, '')} {emotion_name}: {score:.2f}"
    (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    label_y = y1 - 10 if y1 - label_h > 0 else y1 + label_h + 10
    cv2.rectangle(img, (x1, label_y - label_h - 5), (x1 + label_w, label_y), color, -1)
    cv2.putText(img, label, (x1, label_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2)

# ====================== 模型加载 ======================
print("加载模型...")
model = dnn.load(quantize_model_path)

s_scale = model[0].outputs[0].properties.scale_data[:, np.newaxis]
m_scale = model[0].outputs[1].properties.scale_data[:, np.newaxis]
l_scale = model[0].outputs[2].properties.scale_data[:, np.newaxis]
weights = np.arange(16).astype(np.float32)[np.newaxis, :, np.newaxis]

s_anchor = np.stack([np.tile(np.linspace(0.5, 79.5, 80), 80), np.repeat(np.arange(0.5, 80.5, 1), 80)], axis=0)
m_anchor = np.stack([np.tile(np.linspace(0.5, 39.5, 40), 40), np.repeat(np.arange(0.5, 40.5, 1), 40)], axis=0)
l_anchor = np.stack([np.tile(np.linspace(0.5, 19.5, 20), 20), np.repeat(np.arange(0.5, 20.5, 1), 20)], axis=0)

def process_scale(bbox_data, cls_data, anchor, stride, scale):
    max_scores = np.max(cls_data, axis=0)
    valid = np.flatnonzero(max_scores >= conf_inverse)
    if len(valid) == 0:
        return None, None, None
    cls_ids = np.argmax(cls_data[:, valid], axis=0)
    cls_scores = 1 / (1 + np.exp(-max_scores[valid]))
    bbox = bbox_data[:, valid].astype(np.float32) * scale
    bbox = bbox.reshape(4, 16, -1)
    bbox = softmax(bbox, axis=1)
    ltrb = np.sum(bbox * weights, axis=1)
    x, y = anchor[:, valid]
    l, t, r, b = ltrb
    x1 = (x - l * 0.85) * stride
    y1 = (y - t * 0.85) * stride
    x2 = (x + r * 0.85) * stride
    y2 = (y + b * 0.85) * stride
    return np.stack([x1, y1, x2, y2], axis=1), cls_scores, cls_ids

def detect_emotion(frame):
    global current_emotion, current_confidence, last_emotion, last_emotion_change_time
    
    h, w = frame.shape[:2]
    scale_x, scale_y = w / 640, h / 640
    img = cv2.resize(frame, (640, 640))
    img = bgr2nv12(img)
    img = np.expand_dims(img, axis=0).astype(np.uint8)
    outputs = model[0].forward(img)
    
    results = []
    s_box, s_score, s_id = process_scale(outputs[0].buffer.reshape(64, -1), outputs[3].buffer.reshape(4, -1), s_anchor, 8, s_scale)
    if s_box is not None:
        results.extend(zip(s_box, s_score, s_id))
    m_box, m_score, m_id = process_scale(outputs[1].buffer.reshape(64, -1), outputs[4].buffer.reshape(4, -1), m_anchor, 16, m_scale)
    if m_box is not None:
        results.extend(zip(m_box, m_score, m_id))
    l_box, l_score, l_id = process_scale(outputs[2].buffer.reshape(64, -1), outputs[5].buffer.reshape(4, -1), l_anchor, 32, l_scale)
    if l_box is not None:
        results.extend(zip(l_box, l_score, l_id))
    
    if not results:
        with emotion_lock:
            current_emotion = "neutral"
            current_confidence = 0.0
        return []
    
    boxes = np.array([r[0] for r in results])
    scores = np.array([r[1] for r in results])
    ids = np.array([r[2] for r in results])
    
    indices = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), conf, 0.3)
    
    if len(indices) == 0:
        with emotion_lock:
            current_emotion = "neutral"
            current_confidence = 0.0
        return []
    
    emotions = []
    best_emotion = "neutral"
    best_score = 0.0
    
    for idx in indices:
        i = idx[0] if isinstance(idx, (list, np.ndarray)) else idx
        x1, y1, x2, y2 = boxes[i]
        if x2 - x1 < 30 or y2 - y1 < 30:
            continue
        x1, y1, x2, y2 = int(x1*scale_x), int(y1*scale_y), int(x2*scale_x), int(y2*scale_y)
        x1, y1, x2, y2 = max(0,x1), max(0,y1), min(w,x2), min(h,y2)
        if x2 > x1 and y2 > y1:
            emotion_name = emotion_labels[ids[i]%4]
            score = float(scores[i])
            emotions.append({'box': (x1,y1,x2,y2), 'emotion': emotion_name, 'score': score})
            if score > best_score:
                best_score = score
                best_emotion = emotion_name
    
    # 更新全局表情状态
    with emotion_lock:
        new_emotion = best_emotion
        current_emotion = new_emotion
        current_confidence = best_score
        
        # ===== 检测表情变化（触发动画） =====
        current_time = time()
        # 只有置信度大于0.5才认为是有效的表情变化
        if best_score > 0.5:
            # 表情发生变化，且不在冷却期内
            if new_emotion != last_emotion and (current_time - last_emotion_change_time) > emotion_change_cooldown:
                last_emotion = new_emotion
                last_emotion_change_time = current_time
                # 标记需要触发动画（通过返回特殊标记）
                emotions.append({'trigger_animation': True, 'emotion': new_emotion})
                print(f" 检测到表情变化: {emotion_emoji.get(new_emotion, '')}{emotion_chinese.get(new_emotion, '')} -> 触发动画")
    
    return emotions

# ====================== ROS节点 ======================
class EmotionROSNode(Node):
    def __init__(self):
        super().__init__('emotion_ros_node')
        
        # 订阅摄像头图像
        self.sub = self.create_subscription(
            CompressedImage,
            '/image',
            self.image_callback,
            10
        )
        
        # ===== 发布表情信息 =====
        self.emotion_pub = self.create_publisher(String, '/user_emotion', 10)
        
        # ===== 发布动画触发信号 =====
        self.animation_pub = self.create_publisher(String, '/emotion_animation_trigger', 10)
        
        # 帧率统计
        self.frame_count = 0
        self.last_fps_time = time()
        self.emotion_log_counter = 0
        self.publish_counter = 0
        
        # 上次触发动画的表情
        self.last_triggered_emotion = None
        self.last_trigger_time = 0
        
        self.get_logger().info("情绪识别ROS节点已启动")
        print("="*60)
        print("情绪识别已启动（表情触发动画模式）")
        print("表情会通过 /user_emotion 话题发布给主程序")
        print("动画触发通过 /emotion_animation_trigger 话题发布")
        print("="*60)
    
    def publish_emotion(self):
        """发布当前表情信息"""
        global current_emotion, current_confidence
        
        with emotion_lock:
            emotion = current_emotion
            confidence = current_confidence
        
        # 构造表情数据
        emotion_data = {
            'emotion': emotion,
            'confidence': float(confidence),
            'emoji': emotion_emoji.get(emotion, '😐'),
            'chinese': emotion_chinese.get(emotion, '平静'),
            'prompt': self.get_emotion_prompt(emotion)
        }
        
        msg = String()
        msg.data = json.dumps(emotion_data, ensure_ascii=False)
        self.emotion_pub.publish(msg)
        
        # 每10次打印一次日志
        self.publish_counter += 1
        if self.publish_counter % 10 == 0:
            self.get_logger().info(f" 发布表情: {emotion_emoji.get(emotion, '')}{emotion_chinese.get(emotion, '')} (置信度: {confidence:.2f})")
    
    def trigger_animation(self, emotion_name):
        """触发动画播放"""
        # 获取对应的动画名称
        animation_name = emotion_animation_map.get(emotion_name, "neutral")
        
        # 构造触发消息
        trigger_data = {
            'animation': animation_name,
            'emotion': emotion_name,
            'emoji': emotion_emoji.get(emotion_name, '😐'),
            'chinese': emotion_chinese.get(emotion_name, '平静')
        }
        
        msg = String()
        msg.data = json.dumps(trigger_data, ensure_ascii=False)
        self.animation_pub.publish(msg)
        
        self.get_logger().info(f" 触发动画: {animation_name} ({emotion_emoji.get(emotion_name, '')}{emotion_chinese.get(emotion_name, '')})")
    
    def get_emotion_prompt(self, emotion):
        """根据表情生成AI提示词"""
        prompts = {
            "happy": "用户看起来很开心，请用热情欢快的语气回应，可以分享快乐的心情。",
            "sad": "用户看起来有点难过，请用温柔安慰的语气回应，给予鼓励和支持。",
            "angry": "用户看起来有些生气，请用平和冷静的语气回应，帮助平复情绪。",
            "neutral": "用户表情平静，请用自然友好的语气正常对话。"
        }
        return prompts.get(emotion, prompts["neutral"])
    
    def image_callback(self, msg):
        global current_frame
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return
            
            # 检测表情
            emotions = detect_emotion(frame)
            
            # 检查是否有动画触发标记
            trigger_animation = False
            trigger_emotion = None
            for e in emotions:
                if e.get('trigger_animation', False):
                    trigger_animation = True
                    trigger_emotion = e.get('emotion', 'neutral')
                    break
            
            # 触发动画
            if trigger_animation and trigger_emotion:
                self.trigger_animation(trigger_emotion)
            
            # 每5帧发布一次表情（减少话题负载）
            self.frame_count += 1
            if self.frame_count % 5 == 0:
                self.publish_emotion()
            
            # 帧率统计
            now = time()
            if now - self.last_fps_time >= 1.0:
                fps = self.frame_count
                self.frame_count = 0
                self.last_fps_time = now
                
                with emotion_lock:
                    emo = current_emotion
                    score = current_confidence
                if emo != "neutral" or score > 0.3:
                    print(f"[{fps}fps] {emotion_emoji.get(emo, '')}{emotion_chinese.get(emo, '')} {score:.2f}")
                else:
                    print(f"[{fps}fps] no face")
            
            # 绘制表情框
            for e in emotions:
                if 'trigger_animation' in e:
                    continue
                draw_emotion_box(frame, e['box'], e['emotion'], e['score'])
            
            # 添加文字说明
            cv2.putText(frame, f"Emotions: {len(emotions)}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            cv2.putText(frame, "EMOTION", (10, 70), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            if len(emotions) > 0:
                current_emo = emotions[0]['emotion']
                current_score = emotions[0]['score']
                cv2.putText(frame, f"Current: {current_emo} {current_score:.2f}", (10, 110), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.putText(frame, f"FPS: {self.frame_count}", (10, 150), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            with frame_lock:
                current_frame = frame.copy()
                
        except Exception as e:
            self.get_logger().error(f"处理错误: {e}")

# ====================== HTTP服务器 ======================
class VideoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global current_frame
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = '''<!DOCTYPE html>
<html>
<head>
    <title>Emotion Detection</title>
    <style>
        body { margin: 0; padding: 0; background: black; text-align: center; }
        img { width: 100%; height: 100vh; object-fit: contain; }
        .info { position: fixed; bottom: 10px; left: 10px; color: white; background: rgba(0,0,0,0.5); padding: 5px 10px; border-radius: 5px; font-family: monospace; }
    </style>
</head>
<body>
    <img id="video" src="/stream">
    <div class="info">😊 情绪识别 (表情触发动画模式)</div>
    <script>
        var img = document.getElementById('video');
        setInterval(function() {
            img.src = '/stream?' + new Date().getTime();
        }, 33);
    </script>
</body>
</html>'''
            self.wfile.write(html.encode())
        elif self.path.startswith('/stream'):
            with frame_lock:
                if current_frame is not None:
                    _, jpg = cv2.imencode('.jpg', current_frame)
                    self.send_response(200)
                    self.send_header('Content-type', 'image/jpeg')
                    self.end_headers()
                    try:
                        self.wfile.write(jpg.tobytes())
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                else:
                    self.send_response(204)
                    self.end_headers()
    
    def log_message(self, format, *args):
        pass

# ====================== 主程序 ======================
def main():
    global server_running
    
    rclpy.init(args=None)
    ros_node = EmotionROSNode()
    
    def spin_ros():
        rclpy.spin(ros_node)
    
    ros_thread = threading.Thread(target=spin_ros, daemon=True)
    ros_thread.start()
    
    sleep(2)
    
    try:
        server = HTTPServer(('0.0.0.0', 8000), VideoHandler)
        print("="*60)
        print("表情识别服务器已启动！")
        print("在浏览器打开: http://192.168.128.10:8000")
        print("按 Ctrl+C 停止")
        print("="*60)
        server.serve_forever()
    except OSError:
        server = HTTPServer(('0.0.0.0', 8001), VideoHandler)
        print("端口8000被占用，使用8001端口")
        print("在浏览器打开: http://192.168.128.10:8001")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器关闭")
        server_running = False
        server.shutdown()
        ros_node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()