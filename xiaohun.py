#!/usr/bin/python
# -*- coding: UTF-8 -*-


import json
import time
import requests
import threading
import pyaudio
import warnings
import urllib3
import logging
import os
import sys
import uuid
import glob
import wave
import io
import base64
import asyncio
import tempfile
import pygame
import edge_tts
import random
import re

# ROS2相关
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

# 屏蔽警告信息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ============================================================================
# 在线API配置
# ============================================================================

BAIDU_ASR_APP_ID = "123094418"           
BAIDU_ASR_API_KEY = "P3TVOL01E2OHu2IP3rGiefiW"        
BAIDU_ASR_SECRET_KEY = "uAthtYsrSdBabeoXvoWeM1MZz5qijt3v"
DEEPSEEK_API_KEY = "sk-ab2d4c4eaa9245868cf35011b58be3ac"
EDGE_TTS_VOICE = "zh-CN-XiaoxiaoNeural"

# ============================================================================
# 系统配置
# ============================================================================

class ALSAErrorSuppressor:
    def __enter__(self):
        self.old_stderr = os.dup(2)
        self.devnull = os.open('/dev/null', os.O_WRONLY)
        os.dup2(self.devnull, 2)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.dup2(self.old_stderr, 2)
        os.close(self.old_stderr)
        os.close(self.devnull)

os.environ['DISPLAY'] = ':0'

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='xiaozhi.log',
    filemode='w'
)

def print_banner():
    print("=" * 60)
    print(" 小混AI语音助手")
    print("=" * 60)
    print(" 使用说明:")
    print("   - 手势12: 开始录音")
    print("   - 手势13: 停止录音")
    print("   - 有语音时: 识别说话内容 + AI根据情绪随机生成回复")
    print("   - 无语音时: AI根据表情主动生成回复")
    print("=" * 60)

def get_wlan0_ip():
    try:
        import subprocess
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

def get_system_mac_address():
    try:
        wlan0_path = '/sys/class/net/wlan0/address'
        if os.path.exists(wlan0_path):
            with open(wlan0_path, 'r') as f:
                mac = f.read().strip()
                if mac and mac != '00:00:00:00:00:00':
                    return mac
    except:
        pass

    try:
        net_interfaces = glob.glob('/sys/class/net/*/address')
        for interface_path in net_interfaces:
            interface_name = interface_path.split('/')[-2]
            if interface_name != 'lo':
                try:
                    with open(interface_path, 'r') as f:
                        mac = f.read().strip()
                        if mac and mac != '00:00:00:00:00:00':
                            return mac
                except:
                    continue
    except:
        pass

    try:
        mac_int = uuid.getnode()
        mac_hex = hex(mac_int)[2:].zfill(12)
        mac_formatted = ':'.join([mac_hex[i:i+2] for i in range(0, 12, 2)])
        return mac_formatted
    except:
        pass

    return '50:cf:14:5a:9f:17'

# ============================================================================
# 在线API处理器
# ============================================================================

class OnlineAPIHandler:
    def __init__(self):
        self.baidu_token = None
        self.token_expire = 0
        self.is_speaking = False
        self.get_baidu_token()
        pygame.mixer.init()
        pygame.mixer.music.set_volume(0.4)
        # 对话历史存储（本地备份）
        self.conversation_history = []
        self.max_history = 100
        # HTTP API 地址（用于发送对话记录到 http_server.py）
        self.history_api_url = "http://localhost:5000/api/history/add"
        print("✅ 在线API处理器初始化成功")
    
    def add_conversation(self, speaker, text):
        """记录对话（本地 + HTTP）"""
        if not text or text.strip() == '':
            return
        
        # 本地记录
        entry = {
            'time': time.strftime('%H:%M:%S'),
            'speaker': speaker,
            'text': text
        }
        self.conversation_history.append(entry)
        if len(self.conversation_history) > self.max_history:
            self.conversation_history.pop(0)
        
        # ===== 通过 HTTP 发送到 http_server.py =====
        self._send_to_history_api(speaker, text)
    
    def _send_to_history_api(self, speaker, text):
        """通过 HTTP 发送对话记录到 http_server.py"""
        try:
            data = {"speaker": speaker, "text": text}
            # 使用短超时，不影响主功能
            requests.post(self.history_api_url, json=data, timeout=0.5)
        except Exception as e:
            # 静默失败，不影响主功能
            pass
    
    def get_history(self):
        return self.conversation_history
    
    def get_baidu_token(self):
        url = f"https://aip.baidubce.com/oauth/2.0/token?client_id={BAIDU_ASR_API_KEY}&client_secret={BAIDU_ASR_SECRET_KEY}&grant_type=client_credentials"
        try:
            response = requests.post(url, timeout=10)
            result = response.json()
            self.baidu_token = result['access_token']
            self.token_expire = time.time() + result['expires_in'] - 300
            print("✅ 百度ASR令牌获取成功")
            return True
        except Exception as e:
            print(f"❌ 百度令牌获取失败: {e}")
            return False
    
    def asr(self, audio_data):
        if time.time() > self.token_expire:
            if not self.get_baidu_token():
                return None
        
        url = "https://vop.baidu.com/server_api"
        speech_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        data = {
            "format": "wav",
            "rate": 16000,
            "channel": 1,
            "token": self.baidu_token,
            "cuid": "xiaozhi_rdk",
            "len": len(audio_data),
            "speech": speech_base64
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            if result.get('err_no') == 0:
                text = result['result'][0]
                print(f" 识别结果: {text}")
                return text
            else:
                print(f"❌ ASR错误: {result.get('err_msg')}")
                return None
        except Exception as e:
            print(f"❌ ASR请求失败: {e}")
            return None
    
    def llm(self, text, user_emotion=None, emotion_prompt=None, is_active_response=False):
        """AI对话 - 每次都由AI随机生成体现情绪的回答"""
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        # 情绪名称
        emotion_names = {
            "happy": "开心",
            "sad": "难过", 
            "angry": "生气",
            "neutral": "平静"
        }
        emotion_name = emotion_names.get(user_emotion, "平静")
        
        # 情绪对应的随机回复风格指引
        emotion_styles = {
            "happy": [
                "用热情欢快的语气，说一句让人感到快乐的话",
                "用活泼俏皮的语气，分享用户的喜悦",
                "用充满正能量的语气，让开心翻倍",
                "用朋友间开心的语气，一起庆祝好心情",
                "用轻松愉快的语气，回应用户的好心情",
                "用温暖开心的语气，让快乐延续",
                "用幽默风趣的语气，逗用户更开心"
            ],
            "sad": [
                "用温柔体贴的语气，说一句安慰的话",
                "用温暖关心的语气，让用户感受到陪伴",
                "用柔和理解的语气，表达对用户的支持",
                "用朋友间关心的语气，传递温暖",
                "用贴心温柔的语气，让用户感到被理解",
                "用安静陪伴的语气，给用户安全感",
                "用轻声细语的语气，说一句暖心的话"
            ],
            "angry": [
                "用平和冷静的语气，帮用户平复情绪",
                "用耐心温和的语气，安抚用户的心情",
                "用舒缓放松的语气，让用户冷静下来",
                "用稳重可靠的语气，给用户安全感",
                "用温柔耐心的语气，化解用户的烦躁",
                "用平静友善的语气，让用户放松",
                "用从容淡定的语气，帮用户舒缓情绪"
            ],
            "neutral": [
                "用自然友好的语气，正常聊天",
                "用亲切随和的语气，轻松对话",
                "用舒服自然的语气，像朋友一样聊天",
                "用温和友善的语气，自然交流",
                "用轻松愉快的语气，随意聊聊",
                "用真诚自然的语气，表达关心",
                "用友好轻松的语气，开启对话"
            ]
        }
        
        # 随机选择一种风格
        styles = emotion_styles.get(user_emotion, emotion_styles["neutral"])
        chosen_style = random.choice(styles)
        
        # 随机选择回复长度
        length_options = ["15-20字", "20-25字", "10-15字"]
        chosen_length = random.choice(length_options)
        
        if is_active_response:
            # 主动回应模式
            system_prompt = f"""你是小混，一个善解人意的AI语音助手。

【用户的状态】
- 表情：{emotion_name}
- 回复风格：{chosen_style}

【你的任务】
用户没有说话，请你根据用户的表情，主动说一句关心、问候或安慰的话。

要求：
1. 语气要{chosen_style}
2. 每次生成不同的内容，不要重复
3. 直接说内容，控制在{chosen_length}
4. 不要说"我说"、"我回答"之类的话
5. 不要问"为什么"之类的问题"""
            
            user_message = "（用户没有说话，请根据我的表情主动说一句合适的话）"
            
        else:
            # 对话模式
            system_prompt = f"""你是小混，一个善解人意的AI语音助手。

【用户的状态】
- 表情：{emotion_name}
- 回复风格：{chosen_style}

【用户说的话】："{text}"

【你的任务】
根据用户说的话和情绪，用{chosen_style}回复。

要求：
1. 每次生成不同的回复内容，不要重复
2. 语气要体现你感知到了用户的情绪
3. 直接说内容，控制在{chosen_length}
4. 不要说"我说"、"我回答"、"我温柔地说"之类的话
5. 不要问"为什么"之类的问题"""
            
            user_message = text
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 1.0,
            "max_tokens": 150,
            "top_p": 0.95
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                reply = response.json()['choices'][0]['message']['content']
                reply = reply.strip()
                # 移除常见描述语
                prefixes_to_remove = [
                    "我温柔地说：", "我平和地说：", "我开心地说：", "我安慰道：",
                    "温柔地说：", "平和地说：", "开心地说：", "安慰道：",
                    "我温柔地回应：", "我平和地回应：", "我开心地回应：",
                    "我说：", "我回答：", "小混："
                ]
                for prefix in prefixes_to_remove:
                    if reply.startswith(prefix):
                        reply = reply[len(prefix):].strip()
                reply = reply.replace('"', '').replace('"', '').replace('「', '').replace('」', '')
                
                # 记录对话（通过 add_conversation 自动发送到 HTTP）
                if not is_active_response and text:
                    self.add_conversation('user', text)
                self.add_conversation('bot', reply)
                
                print(f" 小混: {reply}")
                return reply
            else:
                print(f"❌ LLM错误: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ LLM调用失败: {e}")
            return None
    
    async def _tts_save(self, text, output_file):
        communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
        await communicate.save(output_file)
    
    def tts(self, text):
        if not text:
            print(f" tts收到空文本")
            return
        
        if self.is_speaking:
            print(f" 正在播放中，跳过")
            return
        
        print(f"🔊 tts收到: '{text}'")
        
        # 清理空格
        text = text.strip()
        
        if not text:
            print(f" 文本为空，跳过播放")
            return
        
        self.is_speaking = True
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                output_file = f.name
            
            asyncio.run(self._tts_save(text, output_file))
            
            time.sleep(0.2)
            
            print(" 播放中...")
            pygame.mixer.music.load(output_file)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            pygame.mixer.music.unload()
            os.unlink(output_file)
            print("✅ 播放完成")
            
        except Exception as e:
            print(f"❌ TTS播放失败: {e}")
        finally:
            self.is_speaking = False
    
    def is_busy(self):
        return self.is_speaking

# ============================================================================
# 全局状态变量
# ============================================================================

MAC_ADDR = get_system_mac_address()
running = True
audio = None
api_handler = None

# 录音相关
is_recording = False
recording_frames = []
recording_stream = None
recording_lock = threading.Lock()
recording_active = False
recording_start_time = 0

# 表情相关
current_user_emotion = "neutral"
current_emotion_prompt = None
current_emotion_emoji = "😐"
current_emotion_chinese = "平静"
last_emotion_time = 0

# 表情日志计数器
_emotion_log_counter = 0

# ============================================================================
# 录音核心功能
# ============================================================================

def start_recording():
    """开始持续录音"""
    global is_recording, recording_frames, recording_stream, recording_active, recording_start_time
    
    with recording_lock:
        if is_recording:
            print(" 已在录音中")
            return
        
        print(" 开始录音... (做手势13结束)")
        
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        recording_frames = []
        recording_start_time = time.time()
        
        try:
            recording_stream = audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            is_recording = True
            recording_active = True
            
        except Exception as e:
            print(f"❌ 无法打开麦克风: {e}")
            is_recording = False
            recording_active = False
            return
    
    def record_loop():
        global is_recording, recording_frames, recording_stream, recording_active
        while recording_active:
            try:
                with recording_lock:
                    if not is_recording or recording_stream is None:
                        break
                    data = recording_stream.read(1024, exception_on_overflow=False)
                    recording_frames.append(data)
            except Exception as e:
                print(f"录音错误: {e}")
                break
            time.sleep(0.01)
    
    recording_thread = threading.Thread(target=record_loop, daemon=True)
    recording_thread.start()

def has_sound(audio_data):
    """检测音频是否有真正的语音（非噪音）- 多条件综合判断"""
    try:
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        if len(audio_array) < 100:
            return False
        
        rms = np.sqrt(np.mean(audio_array.astype(np.float32)**2))
        peak = np.max(np.abs(audio_array))
        zero_crossings = np.sum(np.abs(np.diff(np.sign(audio_array)))) / (2 * len(audio_array))
        
        non_zero = audio_array[audio_array != 0]
        if len(non_zero) > 10:
            min_val = np.min(np.abs(non_zero))
            dynamic_range = peak / max(min_val, 1)
        else:
            dynamic_range = 1
        
        voice_ratio = np.sum(np.abs(audio_array) > 200) / len(audio_array)
        
        has_rms = rms > 80
        has_peak = peak > 5000
        has_voice_ratio = voice_ratio > 0.01
        has_dynamic = dynamic_range > 8
        has_zcr = 0.05 < zero_crossings < 0.35
        
        conditions = [has_rms, has_peak, has_voice_ratio, has_dynamic, has_zcr]
        satisfied = sum(conditions)
        has_sound = satisfied >= 3
        
        print(f" 音量检测: RMS={rms:.0f}, 峰值={peak}, 过零率={zero_crossings:.3f}")
        print(f" 语音占比={voice_ratio:.3f}, 动态范围={dynamic_range:.1f}")
        print(f" 判断: RMS={has_rms}, 峰值={has_peak}, 语音占比={has_voice_ratio}, 动态={has_dynamic}, 过零率={has_zcr}")
        print(f" 结果: {'有语音 ✅' if has_sound else '无语音 ❌'} (满足{satisfied}/5)")
        
        return has_sound
        
    except Exception as e:
        print(f"音量检测错误: {e}")
        return False

def stop_recording_and_process(user_emotion=None, emotion_prompt=None, emotion_emoji="😐", emotion_chinese="平静"):
    """停止录音并处理识别"""
    global is_recording, recording_frames, recording_stream, recording_active, audio, api_handler, recording_start_time
    
    with recording_lock:
        if not is_recording:
            print(" 没有正在进行的录音")
            return None
        
        print(" 停止录音，正在处理...")
        is_recording = False
        recording_active = False
        
        if recording_stream:
            try:
                recording_stream.stop_stream()
                recording_stream.close()
            except:
                pass
            recording_stream = None
        
        frames_copy = recording_frames.copy()
        recording_frames = []
    
    if len(frames_copy) == 0:
        print(" 没有录到音频数据")
        return None
    
    recording_duration = time.time() - recording_start_time
    print(f" 录音时长: {recording_duration:.1f}秒")
    
    if recording_duration < 0.5:
        print(f" 录音时间太短 ({recording_duration:.1f}秒 < 0.5秒)，忽略")
        return {"has_voice": False, "duration": recording_duration, "reason": "too_short"}
    
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    
    try:
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames_copy))
        
        audio_data = wav_buffer.getvalue()
        
        if not has_sound(audio_data):
            print(" 未检测到有效语音（可能是环境噪音）")
            return {"has_voice": False, "duration": recording_duration}
        
        print(" 发送音频给百度ASR进行识别...")
        user_text = api_handler.asr(audio_data)
        
        if user_text is None or not user_text.strip():
            print(" 语音识别失败或未识别到文字")
            return {"has_voice": True, "recognized": False}
        
        noise_keywords = ["嗯", "啊", "哦", "呃", "诶", "唉", "嗯嗯", "啊啊", "我不知道", "我不知"]
        if user_text.strip() in noise_keywords:
            print(f" 识别结果 '{user_text}' 可能是噪音，忽略")
            return {"has_voice": False, "duration": recording_duration, "reason": "noise_detected"}
        
        print(f" 用户说: {user_text}")
        print(f" 当前表情: {emotion_emoji}{emotion_chinese}")
        print(" AI思考中...")
        
        reply = api_handler.llm(user_text, user_emotion, emotion_prompt, is_active_response=False)
        
        if reply:
            print(f" 准备播报: '{reply}'")
            api_handler.tts(reply)
            return {"has_voice": True, "recognized": True, "reply": reply}
        
        return {"has_voice": True, "recognized": True}
            
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        return None

def active_emotion_response(user_emotion, emotion_prompt, emotion_emoji, emotion_chinese):
    """AI根据表情主动发起对话（无语音输入时）- AI随机生成版"""
    global api_handler
    
    print(f"\n 检测到表情: {emotion_emoji}{emotion_chinese}")
    print(" 用户没有说话，小混主动生成回应...")
    
    # 让AI根据表情随机生成主动回应
    reply = api_handler.llm("", user_emotion, None, is_active_response=True)
    
    if reply and len(reply) > 0:
        if len(reply) > 30:
            reply = reply[:30]
        api_handler.tts(reply)
        print(f"💬 主动回应: {reply}")
        return reply
    else:
        # 备用（AI调用失败时）
        fallback = {
            "happy": "今天心情真好呀！有什么开心的事吗？",
            "sad": "别难过，我在这儿陪着你呢。",
            "angry": "别生气啦，放松一下，深呼吸。",
            "neutral": "你好呀！今天过得怎么样？"
        }
        fallback_reply = fallback.get(user_emotion, "你好呀！")
        api_handler.tts(fallback_reply)
        api_handler.add_conversation('bot', fallback_reply)
        print(f"💬 主动回应(备用): {fallback_reply}")
        return fallback_reply

# ============================================================================
# ROS2节点
# ============================================================================

class XiaozhiListener(Node):
    def __init__(self):
        super().__init__('xiaozhi_listener')
        self.last_state = False
        self.last_trigger_time = 0
        self.debounce_seconds = 1.0
        self.processing = False
        self.conversation_thread = None
        self._emotion_count = 0
        
        self.current_user_emotion = "neutral"
        self.current_emotion_prompt = None
        self.current_emotion_emoji = "😐"
        self.current_emotion_chinese = "平静"
        
        self.sub = self.create_subscription(
            Bool,
            '/xiaozhi_video',
            self.xiaozhi_callback,
            10
        )
        
        self.emotion_sub = self.create_subscription(
            String,
            '/user_emotion',
            self.emotion_callback,
            10
        )
        
        self.get_logger().info("✅ XiaozhiListener节点已启动")
        print(" 情绪感知功能已启用")

    def emotion_callback(self, msg):
        global current_user_emotion, current_emotion_prompt, current_emotion_emoji, current_emotion_chinese
        
        try:
            data = json.loads(msg.data)
            self.current_user_emotion = data.get('emotion', 'neutral')
            self.current_emotion_prompt = data.get('prompt', None)
            self.current_emotion_emoji = data.get('emoji', '😐')
            self.current_emotion_chinese = data.get('chinese', '平静')
            
            current_user_emotion = self.current_user_emotion
            current_emotion_prompt = self.current_emotion_prompt
            current_emotion_emoji = self.current_emotion_emoji
            current_emotion_chinese = self.current_emotion_chinese
            
            self._emotion_count += 1
            if self._emotion_count % 50 == 0:
                self.get_logger().info(f" 当前表情: {self.current_emotion_emoji}{self.current_emotion_chinese}")
                print(f" 当前表情: {self.current_emotion_emoji}{self.current_emotion_chinese}")
                
        except Exception as e:
            self.get_logger().error(f"解析表情信息失败: {e}")

    def xiaozhi_callback(self, msg: Bool):
        global is_recording
        
        current_time = time.time()
        
        if current_time - self.last_trigger_time < self.debounce_seconds:
            return
        
        if msg.data and self.processing:
            return
        
        self.last_trigger_time = current_time
        
        if msg.data and not self.last_state:
            if not is_recording and not self.processing:
                self.get_logger().info(" 手势12：开始录音")
                thread = threading.Thread(target=start_recording, daemon=True)
                thread.start()
        
        elif not msg.data and self.last_state:
            if is_recording and not self.processing:
                self.get_logger().info(" 手势13：停止录音并识别")
                self.processing = True
                
                emotion = self.current_user_emotion
                prompt = self.current_emotion_prompt
                emoji = self.current_emotion_emoji
                chinese = self.current_emotion_chinese
                
                print(f" 使用当前表情: {emoji}{chinese}")
                
                thread = threading.Thread(
                    target=self._process_conversation,
                    args=(emotion, prompt, emoji, chinese),
                    daemon=True
                )
                thread.start()

        self.last_state = msg.data
    
    def _process_conversation(self, user_emotion=None, emotion_prompt=None, emotion_emoji="😐", emotion_chinese="平静"):
        try:
            if user_emotion is None:
                user_emotion = self.current_user_emotion
                emotion_emoji = self.current_emotion_emoji
                emotion_chinese = self.current_emotion_chinese
                emotion_prompt = self.current_emotion_prompt
            
            result = stop_recording_and_process(user_emotion, emotion_prompt, emotion_emoji, emotion_chinese)
            
            if result:
                if not result.get("has_voice", False):
                    self.get_logger().info(" 未检测到语音，启动AI主动表情回应")
                    active_emotion_response(user_emotion, emotion_prompt, emotion_emoji, emotion_chinese)
                elif result.get("has_voice", False) and not result.get("recognized", True):
                    self.get_logger().info(" 检测到语音但识别失败，启动AI主动表情回应")
                    active_emotion_response(user_emotion, emotion_prompt, emotion_emoji, emotion_chinese)
                
        except Exception as e:
            self.get_logger().error(f"对话处理异常: {e}")
        finally:
            self.processing = False
            self.get_logger().info("✅ 处理完成，状态已重置")

# ============================================================================
# 主程序入口
# ============================================================================

def run():
    global audio, running, api_handler

    try:
        print_banner()
        print(f" 设备MAC地址: {MAC_ADDR}")

        wlan0_ip = get_wlan0_ip()
        print(f" wlan0 IP地址: {wlan0_ip}")

        print(" 初始化音频...")
        with ALSAErrorSuppressor():
            audio = pyaudio.PyAudio()

        print(" 初始化AI服务...")
        api_handler = OnlineAPIHandler()

        print(" 测试API连接...")
        if api_handler.baidu_token:
            print("✅ 百度ASR连接正常")
        
        print(" 测试DeepSeek连接...")
        test_reply = api_handler.llm("你好")
        if test_reply:
            print("✅ DeepSeek连接正常")

        print(" 启动完成!")
        print("=" * 60)
        print(" 使用说明:")
        print("   - 手势12: 开始录音")
        print("   - 手势13: 停止录音")
        print("   - 有语音时: 识别说话内容 + AI随机生成回复")
        print("   - 无语音时: AI根据表情主动生成回复")
        print("=" * 60)

        rclpy.init()
        node = XiaozhiListener()
        rclpy.spin(node)

    except Exception as e:
        print(f"❌ 运行错误: {str(e)}")
        logging.error(f"运行时错误: {str(e)}")
    finally:
        print("\n 清理资源...")
        running = False
        
        global is_recording, recording_active
        is_recording = False
        recording_active = False
        
        if audio:
            try:
                audio.terminate()
            except:
                pass

        try:
            pygame.mixer.quit()
        except:
            pass

        try:
            rclpy.shutdown()
        except:
            pass

        print(" 程序退出")

if __name__ == "__main__":
    import numpy as np
    run()