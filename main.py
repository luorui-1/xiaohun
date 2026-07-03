#!/usr/bin/env python3
import os
os.environ["DISPLAY"] = ":0"
os.environ["SDL_VIDEODRIVER"] = "x11"
os.environ["GTK_BACKEND"] = "x11"
import rclpy
from rclpy.node import Node
from ai_msgs.msg import PerceptionTargets
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge
import cv2
from std_msgs.msg import Bool, String
import numpy as np
import sys
import signal
import Hobot.GPIO as GPIO
from tkinter import Tk, Label, Frame, font
from PIL import Image as PILImage, ImageTk
import random
import requests
from datetime import datetime
import threading
import time
import json
import asyncio
import tempfile
import pygame
import edge_tts

GPIO.setwarnings(False)

def signal_handler(signal, frame):
    sys.exit(0)

class Handfollower(Node):
    def __init__(self):
        super().__init__('hand_follower')
        self.output_pin = 33
        self.img_width = 640
        self.center_x = self.img_width / 2

        # 状态控制
        self.following_enabled = False
        self.current_duty = 7.5
        
        # 滤波参数
        self.filtered_duty = 7.5
        self.filtered_hand_x = self.center_x
        self.last_hand_x = None
        self.hand_filter_alpha = 0.3
        
        # 初始化运动序列控制变量
        self.init_sequence_active = False
        self.init_positions = []
        self.init_step_index = 0
        self.init_incr = 0.3
        
        # 跟踪帧计数器
        self.tracking_frame_counter = 0

        # 表情相关
        self.current_user_emotion = "neutral"
        self.current_emotion_confidence = 0.0
        self.current_emotion_emoji = "😐"
        self.current_emotion_chinese = "平静"
        self.current_emotion_prompt = None
        
        # ===== 动画触发相关 =====
        self.emotion_animation_queue = []
        self.queue_lock = threading.Lock()
        self.is_playing = False
        self.current_emotion = None
        self.frame_index = 0
        
        # 小混状态
        self.xiaozhi_triggered = False
        
        # TTS语音播报控制
        self.is_speaking = False
        self.tts_lock = threading.Lock()
        
        # 初始化pygame mixer
        try:
            pygame.mixer.init()
            pygame.mixer.music.set_volume(0.4)
        except:
            pass
        
        # ===== ROS发布者 =====
        self.detection_pub = self.create_publisher(Bool, '/xiaozhi_video', 10)
        # ===== 发布语音播报话题 =====
        self.speech_pub = self.create_publisher(String, '/robot_speech', 10)
        
        # 订阅表情话题
        self.emotion_sub = self.create_subscription(
            String,
            '/user_emotion',
            self.emotion_callback,
            10
        )
        
        # 订阅动画触发话题
        self.animation_sub = self.create_subscription(
            String,
            '/emotion_animation_trigger',
            self.animation_trigger_callback,
            10
        )
        
        # ROS订阅者 - 手势识别
        self.target_sub = self.create_subscription(
            PerceptionTargets,
            '/hobot_hand_gesture_detection',
            self.target_callback,
            10
        )

        # ===== GPIO和舵机初始化 =====
        GPIO.setmode(GPIO.BOARD)
        self.pwm = GPIO.PWM(self.output_pin, 50)  # 50Hz 频率
        self.pwm.ChangeDutyCycle(self.current_duty)  # 先设置占空比
        self.pwm.start(self.current_duty)  # 再启动PWM
        
        # Tkinter窗口初始化
        self.init_tkinter()
        
        # 定时器（20ms刷新一次）
        self.timer = self.create_timer(0.02, self.update_frame)
        
        # 执行初始化运动序列
        self.execute_init_sequence()
        
        self.get_logger().info(" Handfollower节点启动完成，等待表情触发动画...")
    
    def init_tkinter(self):
        """初始化Tkinter窗口"""
        self.root = Tk()
        self.root.title("Robot Emotion")
        self.root.attributes('-fullscreen', True)
        self.root.config(cursor="none")
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        self.label = Label(self.root, bg="black")
        self.label.pack(expand=True, fill="both")

        # 表情动画配置
        self.frame_count = {
            'blink': 39, 'happy': 45, 'sad': 47, 'dizzy': 67, 'excited': 24, 
            'neutral': 61, 'happy2': 20, 'angry': 20, 'happy3': 26, 
            'bootup3': 124, 'blink2': 20, 'bootup': 120, 'sleep': 112,
        }
        self.emotions_list = list(self.frame_count.keys())
        
        # 天气显示
        self.showing_weather = False
        self.weather_data = None
        self.weather_api_key = "33284cc2c0e242b2ac2d1b5c31965166"
    
    def emotion_callback(self, msg):
        try:
            data = json.loads(msg.data)
            self.current_user_emotion = data.get('emotion', 'neutral')
            self.current_emotion_confidence = data.get('confidence', 0.0)
            self.current_emotion_emoji = data.get('emoji', '😐')
            self.current_emotion_chinese = data.get('chinese', '平静')
            self.current_emotion_prompt = data.get('prompt', None)
            
            if random.random() < 0.1:
                self.get_logger().info(f" 收到表情: {self.current_emotion_emoji}{self.current_emotion_chinese}")
        except Exception as e:
            self.get_logger().error(f"解析表情失败: {e}")
    
    def animation_trigger_callback(self, msg):
        try:
            data = json.loads(msg.data)
            animation_name = data.get('animation', 'neutral')
            emotion = data.get('emotion', 'neutral')
            emoji = data.get('emoji', '😐')
            chinese = data.get('chinese', '平静')
            
            self.get_logger().info(f" 收到动画触发: {animation_name} ({emoji}{chinese})")
            
            if animation_name not in self.frame_count:
                self.get_logger().warn(f" 未知动画: {animation_name}")
                return
            
            emotion_dir = f'emotions/{animation_name}'
            if not os.path.exists(emotion_dir):
                self.get_logger().error(f"❌ 动画文件夹不存在: {emotion_dir}")
                return
            
            with self.queue_lock:
                if animation_name not in self.emotion_animation_queue:
                    self.emotion_animation_queue.append(animation_name)
                    self.get_logger().info(f" 动画已加入队列: {animation_name} (队列长度: {len(self.emotion_animation_queue)})")
                else:
                    self.get_logger().info(f" 动画 {animation_name} 已在队列中，跳过")
                    
        except Exception as e:
            self.get_logger().error(f"解析动画触发失败: {e}")
    
    def target_callback(self, msg):
        current_hand_x = None
        detected_tracking_gesture = False  # 改为通用名称
        
        for target in msg.targets:
            for roi in target.rois:
                if roi.type == "hand":
                    rect = roi.rect
                    if len(target.attributes) != 0:
                        label_id = int(target.attributes[0].value)
                        hand_x = rect.x_offset + rect.width / 2
                        
                        # ===== 舵机跟踪检测为手势3 (V手势) =====
                        if self.following_enabled and label_id == 3:
                            current_hand_x = hand_x
                            detected_tracking_gesture = True
                            self.last_hand_x = hand_x

                        if not self.is_playing and not self.showing_weather:
                            # ===== 手势控制逻辑 =====
                            if label_id == 11:  # Okay手势 -> 显示天气
                                if not self.xiaozhi_triggered:
                                    self.show_weather()
                            
                            elif label_id == 3:  # V手势 -> 开启跟随模式
                                if not self.following_enabled:
                                    self.get_logger().info(" 开启跟随模式")
                                    self.following_enabled = True
                            
                            elif label_id == 12:  # 左 -> 开启小混
                                if not self.xiaozhi_triggered:
                                    msg = Bool()
                                    msg.data = True
                                    self.detection_pub.publish(msg)
                                    self.get_logger().info(f"✅ 开启小混")
                                    self.xiaozhi_triggered = True
                            
                            elif label_id == 13:  # 右 -> 关闭小混
                                if self.xiaozhi_triggered:
                                    msg = Bool()
                                    msg.data = False
                                    self.detection_pub.publish(msg)
                                    self.get_logger().info("✅ 关闭小混")
                                    self.xiaozhi_triggered = False
                            
                            elif label_id == 2:  # 大拇指 -> 随机表情
                                self.start_random_emotion()
        
        if self.following_enabled and not self.init_sequence_active:
            self.tracking_frame_counter += 1
            if self.tracking_frame_counter >= 10:
                self.tracking_frame_counter = 0
                if detected_tracking_gesture and current_hand_x is not None:
                    self.update_servo_by_error(current_hand_x)
    
    def start_random_emotion(self):
        if self.is_playing or self.showing_weather:
            return
        
        # ===== 根据当前表情生成情绪反馈文字并发布 =====
        emotion = self.current_user_emotion
        if emotion == "happy":
            speech_text = "看到你笑，我也很开心！"
        elif emotion == "sad":
            speech_text = "别难过，我在这里陪着你。"
        elif emotion == "angry":
            speech_text = "别生气啦，深呼吸，放轻松。"
        else:
            speech_text = "你好呀，今天有什么想聊的吗？"
        
        speech_msg = String()
        speech_msg.data = speech_text
        self.speech_pub.publish(speech_msg)
        self.get_logger().info(f" 情绪反馈已发布: {speech_text}")
        
        # 触发动画
        self.current_emotion = random.choice(self.emotions_list)
        self.frame_index = 0
        self.is_playing = True
        self.get_logger().info(f" 触发表情: {self.current_emotion}")

    def update_frame(self):
        """每20ms执行一次的刷新逻辑"""
        
        # ===== 1. 初始化运动序列 =====
        if self.init_sequence_active:
            self._update_init_sequence()
            try:
                self.root.update()
            except:
                pass
            return
        
        # ===== 2. 天气显示 =====
        if self.showing_weather:
            try:
                self.root.update()
            except:
                pass
            return
        
        # ===== 3. 检查动画队列 =====
        if not self.is_playing:
            with self.queue_lock:
                if len(self.emotion_animation_queue) > 0:
                    animation_name = self.emotion_animation_queue.pop(0)
                    self.get_logger().info(f" 从队列取出动画: {animation_name} (剩余: {len(self.emotion_animation_queue)})")
                    
                    emotion_dir = f'emotions/{animation_name}'
                    if os.path.exists(emotion_dir):
                        first_frame = f'{emotion_dir}/frame0.png'
                        if os.path.exists(first_frame):
                            self.current_emotion = animation_name
                            self.frame_index = 0
                            self.is_playing = True
                            self.get_logger().info(f" 开始播放动画: {animation_name}")
                        else:
                            self.get_logger().error(f"❌ 第一帧不存在: {first_frame}")
                    else:
                        self.get_logger().error(f"❌ 动画文件夹不存在: {emotion_dir}")
        
        # ===== 4. 播放动画 =====
        if self.is_playing and self.current_emotion:
            emotion_dir = f'emotions/{self.current_emotion}'
            image_path = f'{emotion_dir}/frame{self.frame_index}.png'
            
            if os.path.exists(image_path):
                try:
                    img = PILImage.open(image_path)
                    img = img.resize((self.screen_width, self.screen_height), PILImage.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    
                    self.label.config(image=photo)
                    self.label.image = photo 
                    
                    self.frame_index += 1
                    
                    total_frames = self.frame_count.get(self.current_emotion, 0)
                    if self.frame_index >= total_frames:
                        self.get_logger().info(f"✅ 动画 {self.current_emotion} 播放完成")
                        self.current_emotion = None
                        self.frame_index = 0
                        self.is_playing = False
                        self.label.config(image='')
                        self.label.image = None
                except Exception as e:
                    self.get_logger().error(f"加载动画帧失败: {e}")
                    self.current_emotion = None
                    self.frame_index = 0
                    self.is_playing = False
                    self.label.config(image='')
                    self.label.image = None
            else:
                self.frame_index += 1
                total_frames = self.frame_count.get(self.current_emotion, 0)
                if self.frame_index >= total_frames:
                    self.get_logger().warn(f" 动画 {self.current_emotion} 帧数不足")
                    self.current_emotion = None
                    self.frame_index = 0
                    self.is_playing = False
                    self.label.config(image='')
                    self.label.image = None

        try:
            self.root.update()
        except:
            pass

    def get_weather_data(self):
        try:
            weather_api_key = "33284cc2c0e242b2ac2d1b5c31965166"
            api_host = "mp4gkk6jy4.re.qweatherapi.com"
            weather_city_id = "101190802"

            url = f"https://{api_host}/v7/weather/now"
            params = {
                "location": weather_city_id,
                "key": weather_api_key
            }

            resp = requests.get(url, params=params, timeout=8)
            data = resp.json()

            if data.get("code") != "200":
                return None

            now = data["now"]
            weather_info = {
                'city': '徐州铜山',
                'country': '中国',
                'temp': int(now.get('temp', 0)),
                'feels_like': int(now.get('feelsLike', 0)),
                'description': now.get('text', ''),
                'humidity': int(now.get('humidity', 0)),
                'wind_speed': round(float(now.get('windSpeed', 0)), 1),
                'pressure': int(now.get('pressure', 0)),
                'icon': now.get('icon', '')
            }
            return weather_info
        except Exception as e:
            self.get_logger().error(f"获取天气数据失败: {str(e)}")
            return None
    
    def _get_weather_speech_text(self, weather_data):
        if weather_data is None:
            return "抱歉，无法获取天气信息"
        
        city = weather_data['city']
        temp = weather_data['temp']
        feels_like = weather_data['feels_like']
        desc = weather_data['description']
        humidity = weather_data['humidity']
        wind_speed = weather_data['wind_speed']
        
        if desc in ['晴', '多云']:
            mood = "天气不错哦！"
        elif desc in ['小雨', '中雨', '大雨', '雷阵雨']:
            mood = "外面下雨了，记得带伞哦！"
        elif desc in ['小雪', '中雪', '大雪']:
            mood = "下雪了，注意保暖哦！"
        elif desc in ['雾', '霾']:
            mood = "能见度较低，出行请注意安全！"
        else:
            mood = ""
        
        speech = f"{city}，当前天气{desc}，气温{temp}度，体感温度{feels_like}度，湿度{humidity}%。"
        if mood:
            speech += mood
        if wind_speed > 5:
            speech += f"风速{wind_speed}米每秒，风有点大哦。"
        
        return speech
    
    async def _tts_save(self, text, output_file, voice="zh-CN-XiaoxiaoNeural"):
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
    
    def _play_tts(self, text):
        if not text or text.strip() == "":
            return
        
        with self.tts_lock:
            if self.is_speaking:
                return
            self.is_speaking = True
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                output_file = f.name
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._tts_save(text, output_file))
            loop.close()
            
            if os.path.exists(output_file):
                self.get_logger().info(f"🔊 播报: {text}")
                pygame.mixer.music.load(output_file)
                pygame.mixer.music.play()
                
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                
                pygame.mixer.music.unload()
                os.unlink(output_file)
                self.get_logger().info("✅ 播报完成")
            
        except Exception as e:
            self.get_logger().error(f"❌ TTS播报失败: {e}")
        finally:
            with self.tts_lock:
                self.is_speaking = False
    
    def speak_weather(self, weather_data):
        if weather_data is None:
            speech_text = "抱歉，无法获取天气信息"
        else:
            speech_text = self._get_weather_speech_text(weather_data)
        
        # ===== 发布天气播报到 /robot_speech =====
        speech_msg = String()
        speech_msg.data = speech_text
        self.speech_pub.publish(speech_msg)
        self.get_logger().info(f" 天气播报已发布: {speech_text}")
        
        thread = threading.Thread(target=self._play_tts, args=(speech_text,), daemon=True)
        thread.start()
    
    def show_weather(self):
        if self.is_playing:
            return
        
        self.get_logger().info(" 获取天气信息...")
        weather_data = self.get_weather_data()
        
        if weather_data is None:
            self.display_weather_error()
            # 发布错误信息
            speech_msg = String()
            speech_msg.data = "抱歉，无法获取天气信息"
            self.speech_pub.publish(speech_msg)
            self._play_tts("抱歉，无法获取天气信息")
            return
        
        self.weather_data = weather_data
        self.showing_weather = True
        self.is_playing = True
        self.display_weather_info(weather_data)
        self.speak_weather(weather_data)
    
    def display_weather_info(self, weather_data):
        for widget in self.label.winfo_children():
            widget.destroy()
        
        main_frame = Frame(self.label, bg="black")
        main_frame.pack(expand=True, fill="both")
        
        title_font = font.Font(family="Arial", size=36, weight="bold")
        temp_font = font.Font(family="Arial", size=56, weight="bold")
        info_font = font.Font(family="Arial", size=20)
        
        city_label = Label(main_frame, text=f"{weather_data['city']}, {weather_data['country']}",
                          font=title_font, fg="white", bg="black")
        city_label.pack(pady=(40, 20))
        
        temp_label = Label(main_frame, text=f"{weather_data['temp']}°C",
                          font=temp_font, fg="#4A90E2", bg="black")
        temp_label.pack(pady=15)
        
        feels_like_label = Label(main_frame, text=f"体感温度: {weather_data['feels_like']}°C",
                                font=info_font, fg="#7F8C8D", bg="black")
        feels_like_label.pack(pady=5)
        
        humidity_label = Label(main_frame, text=f"湿度: {weather_data['humidity']}%",
                              font=info_font, fg="#7F8C8D", bg="black")
        humidity_label.pack(pady=5)
        
        desc_label = Label(main_frame, text=weather_data['description'].title(),
                          font=info_font, fg="#E67E22", bg="black")
        desc_label.pack(pady=15)
        
        speak_label = Label(main_frame, text=" 语音播报中...",
                           font=font.Font(family="Arial", size=16),
                           fg="#2ECC71", bg="black")
        speak_label.pack(pady=5)
        
        self.root.after(5000, self.reset_weather_display)
    
    def display_weather_error(self):
        for widget in self.label.winfo_children():
            widget.destroy()
        
        error_frame = Frame(self.label, bg="black")
        error_frame.pack(expand=True, fill="both")
        
        error_font = font.Font(family="Arial", size=36, weight="bold")
        error_label = Label(error_frame, text="❌ 无法获取天气信息",
                           font=error_font, fg="red", bg="black")
        error_label.pack(expand=True)
        
        self.root.after(3000, self.reset_weather_display)
    
    def reset_weather_display(self):
        self.showing_weather = False
        self.is_playing = False
        self.weather_data = None
        
        for widget in self.label.winfo_children():
            widget.destroy()
        
        self.label.config(bg="black", image='')
        self.label.image = None
        self.get_logger().info(" 天气显示已关闭")
    
    def execute_init_sequence(self):
        self.get_logger().info(" 开始执行初始化运动序列...")
        self.init_positions = [(5, "左"), (10, "右"), (7.5, "中心")]
        self.init_sequence_active = True
        self.init_step_index = 0
    
    def _update_init_sequence(self):
        if not self.init_sequence_active:
            return
        
        if self.init_step_index >= len(self.init_positions):
            self.init_sequence_active = False
            self.filtered_duty = self.current_duty
            self.get_logger().info("✅ 初始化运动序列完成")
            return
        
        target_val, target_name = self.init_positions[self.init_step_index]
        distance = target_val - self.current_duty
        
        if abs(distance) < self.init_incr:
            self.current_duty = target_val
            self.filtered_duty = target_val
            self.pwm.ChangeDutyCycle(self.current_duty)
            self.get_logger().info(f"✓ 到达{target_name}位置: {self.current_duty:.2f}")
            self.init_step_index += 1
            if self.init_step_index < len(self.init_positions):
                next_target_val, next_target_name = self.init_positions[self.init_step_index]
                self.get_logger().info(f"→ 开始移动到{next_target_name}位置")
        else:
            if distance > 0:
                self.current_duty += self.init_incr
            else:
                self.current_duty -= self.init_incr
            
            self.current_duty = max(2.5, min(12.5, self.current_duty))
            self.filtered_duty = self.current_duty
            self.pwm.ChangeDutyCycle(self.current_duty)
    
    def update_servo_by_error(self, hand_x):
        self.filtered_hand_x = (self.hand_filter_alpha * hand_x + 
                                (1 - self.hand_filter_alpha) * self.filtered_hand_x)
        filtered_hand_x = self.filtered_hand_x
        error = abs(filtered_hand_x - self.center_x)
        
        if error < 75:
            angle = 4
        elif error < 155:
            angle = 6
        elif error < 315:
            angle = 8
        else:
            angle = 10
        
        duty_increment = angle * (12.5 - 2.5) / 180.0
        
        if filtered_hand_x > self.center_x:
            target_duty = self.current_duty - duty_increment
        else:
            target_duty = self.current_duty + duty_increment
        
        target_duty = max(2.5, min(12.5, target_duty))
        self.filtered_duty = 0.95 * target_duty + 0.05 * self.filtered_duty
        self.current_duty = self.filtered_duty
        self.pwm.ChangeDutyCycle(self.current_duty)
    
    def destroy_node(self):
        try:
            self.root.destroy()
        except:
            pass
        try:
            self.pwm.stop()
        except:
            pass
        try:
            GPIO.cleanup()
        except:
            pass
        try:
            pygame.mixer.quit()
        except:
            pass
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = Handfollower()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n 用户中断")
    except Exception as e:
        print(f"❌ 运行错误: {e}")
    finally:
        node.destroy_node()
        rclpy.shutdown()
        print(" 程序退出")

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()