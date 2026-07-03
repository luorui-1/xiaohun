# 多模态陪伴机器人

一个基于RDK X5的陪伴交互系统，集成了**情绪识别、表情动画、手势控制、语音对话和天气查询**功能。

##  项目概述

本项目包含三个核心模块：

1. **情绪识别系统** (`emotion.py`) - 通过BPU加速的YOLOv8s模型实时识别用户表情（开心/难过/生气/平静）
2. **主控系统** (`main.py`) - 根据表情触发动画、手势控制舵机、查询天气、开关语音助手
3. **小混语音助手** (`xiaohun.py`) - 提供实时语音交互，支持情绪感知对话

##  主要功能

### 情绪识别与表情系统

* **端侧AI情绪识别**
  * 基于YOLOv8s_emotion模型，BPU加速推理
  * 支持4种表情识别：开心、难过、生气、平静
  * 识别置信度>0.5时自动触发对应动画
* **表情动画播放**
  * 支持13种表情动画（开心、难过、生气、平静、眨眼、兴奋等）
  * 全屏显示，自动适配屏幕分辨率
  * 动画队列管理，避免播放冲突
* **天气信息查询**
  * 集成和风天气API
  * 显示温度、湿度、天气状况等详细信息
  * 语音播报天气信息，5秒后自动返回待机
* **舵机控制**
  * 初始化序列：启动时自动执行左→右→中心运动
  * 平滑运动控制，支持0-180度范围
  * 基于手部位置的智能滤波跟踪算法

### 小混语音助手

* **情绪感知对话**
  * 根据用户表情动态调整回复风格
  * AI主动发起对话（无语音输入时）
  * 支持中英文混合识别
* **语音服务集成**
  * 百度ASR语音识别
  * DeepSeek LLM智能对话
  * Edge TTS语音合成
* **对话记录管理**
  * 通过HTTP API同步到Web服务器
  * 支持历史记录查询

##  系统要求

### 硬件要求

* RDK X5开发板（10TOPS BPU算力）
* USB摄像头（用于手势和表情识别）
* 麦克风和扬声器（用于语音交互）
* SG90舵机（用于头部跟踪）
* 屏幕（用于表情、天气信息显示）

### 软件要求

* Python 3.8+
* ROS2 Humble
* TROS（地平线机器人操作系统）

## 📁 项目结构

```
xiaohun/
├── emotion.py             # 情绪识别主程序（BPU加速）
├── main.py                # 机器人主控程序
├── xiaohun.py             # 小智语音助手
├── http_server.py         # HTTP API服务器
├── requirements.txt       # Python依赖
├── 3D模型/                # 机器人3D建模文件
├── 手机app/               # 手机端控制应用源码
├── emotions/              # 表情动画资源文件夹
├── README.md              # 英文版项目说明文档
└── README-cn.md           # 中文版项目说明文档
```
##  使用方法

### 1. 准备工作

1. **准备模型文件**
   * 将YOLOv8s_emotion量化模型放入指定路径
   * 确保模型文件为 `.bin` 格式

2. **准备表情动画资源**
   * 确保 `emotions/` 文件夹存在
   * 每个表情文件夹中包含按顺序命名的帧图片（frame0.png, frame1.png, ...）

3. **配置API密钥**
   * 在对应程序中配置百度ASR、DeepSeek、天气API密钥

### 2. 启动系统

**分别启动（推荐调试）：**

```bash
# 终端1: 启动情绪识别
source /opt/tros/humble/setup.bash
python3 emotion.py

# 终端2: 启动主控
source /opt/tros/humble/setup.bash
python3 main.py

# 终端3: 启动语音助手
source /opt/tros/humble/setup.bash
python3 xiaohun.py

# 终端4: 启动HTTP服务器
python3 http_server.py
```
### 3. 手势控制说明

| 手势ID | 手势类型 | 功能说明 |
|--------|----------|----------|
| 11 | Okay | 查询天气并语音播报 |
| 12 | 左 | 开启小智语音助手 |
| 13 | 右 | 关闭小智语音助手 |
| 2 | 大拇指 | 随机播放表情动画 |
| 3 | V手势 | 开启头部跟随模式 |

### 4. 情绪触发流程

1. `emotion.py` 实时识别用户表情
2. 检测到表情变化（置信度>0.5）时，发布 `/emotion_animation_trigger` 话题
3. `main.py` 接收到触发信号，播放对应表情动画
4. 同时通过 `/user_emotion` 发布表情状态给语音助手
5. 语音助手根据表情调整回复风格

##  ROS2话题说明

### 发布话题

| 节点 | 话题 | 类型 | 说明 |
|------|------|------|------|
| emotion.py | `/user_emotion` | String | 表情状态（JSON格式） |
| emotion.py | `/emotion_animation_trigger` | String | 动画触发信号 |
| main.py | `/xiaozhi_video` | Bool | 小智开关控制 |
| main.py | `/robot_speech` | String | 语音播报内容 |

### 订阅话题

| 节点 | 话题 | 类型 | 说明 |
|------|------|------|------|
| main.py | `/user_emotion` | String | 接收表情状态 |
| main.py | `/emotion_animation_trigger` | String | 接收动画触发 |
| main.py | `/hobot_hand_gesture_detection` | PerceptionTargets | 手势识别结果 |
| xiaohun.py | `/xiaozhi_video` | Bool | 录音控制信号 |
| http_server.py | `/user_emotion` | String | 表情状态（API展示） |
| http_server.py | `/image` | CompressedImage | 摄像头图像（视频流） |

##  表情动画列表

| 表情名称 | 帧数 | 说明 |
|----------|------|------|
| happy | 49 | 开心表情 |
| sad | 45 | 难过表情 |
| angry | 24 | 生气表情 |
| neutral | 56 | 平静表情 |
| blink | 39 | 眨眼动画 |
| excited | 24 | 兴奋表情 |
| dizzy | 63 | 眩晕表情 |
| happy2 | 22 | 开心表情2 |
| happy3 | 25 | 开心表情3 |
| blink2 | 23 | 眨眼动画2 |
| bootup | 118 | 启动动画 |
| bootup3 | 113 | 启动动画3 |
| sleep | 121 | 睡眠动画 |

##  舵机控制参数

* **PWM频率**：50Hz
* **占空比范围**：2.5% - 12.5%（对应0°-180°）
* **初始化序列**：左(5%) → 右(10%) → 中心(7.5%)
* **跟踪频率**：每10帧处理一次
* **滤波系数**：手部位置0.3，占空比0.05

##  HTTP API接口

启动 `http_server.py` 后，可通过以下接口访问：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取完整状态（表情+系统+小智） |
| `/api/camera` | GET | 获取单帧图像 |
| `/api/camera_stream` | GET | 实时视频流（MJPEG） |
| `/api/emotions` | GET | 获取当前表情 |
| `/api/history` | GET | 获取对话历史 |
| `/health` | GET | 健康检查 |

访问地址：`http://<RDK_X5_IP>:5000`

##  故障排除

### 情绪识别不工作

1. 检查模型文件路径是否正确
2. 确认摄像头是否正常连接
3. 检查ROS话题 `/image` 是否正常发布
4. 查看BPU驱动是否正常：`hrut_bpuprofile -b 0 -r 1`

### 舵机不响应

1. 检查GPIO引脚配置是否正确（默认33号引脚）
2. 确认舵机电源连接正常（5V供电）
3. 检查PWM信号是否正常输出
4. 确认GPIO权限：`sudo chmod 666 /dev/gpiochip0`

### 表情动画不显示

1. 确认 `emotions/` 文件夹存在
2. 检查动画帧文件命名是否正确（frame0.png, frame1.png, ...）
3. 确认图片文件格式为PNG
4. 检查显示环境变量：`echo $DISPLAY`

### 语音助手无响应

1. 检查麦克风和扬声器是否正常连接
2. 确认API密钥配置正确
3. 查看日志文件 `xiaohun.log` 获取详细错误信息
4. 测试音频设备：`arecord -l` 和 `aplay -l`

**注意**：使用前请仔细阅读配置说明，确保硬件连接正确。建议先分别启动各模块测试，确认正常后再使用一键启动脚本。
