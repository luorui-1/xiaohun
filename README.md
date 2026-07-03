# Multimodal Companion Robot

A companion interaction system based on RDK X5, integrating **emotion recognition, expressive animations, gesture control, voice dialogue, and weather inquiry** functionalities.

---

## Project Overview

This project consists of three core modules:

1. **Emotion Recognition System** (`emotion.py`) - Utilizes a BPU-accelerated YOLOv8s model to recognize user emotions in real-time (happy/sad/angry/neutral).
2. **Main Control System** (`main.py`) - Triggers animations based on emotions, controls servos via gestures, queries weather, and toggles the voice assistant.
3. **Xiaohun Voice Assistant** (`xiaohun.py`) - Provides real-time voice interaction with emotion-aware dialogue capabilities.

---

## Key Features

### Emotion Recognition & Expression System

- **On-Device AI Emotion Recognition**
  - Based on the YOLOv8s_emotion model with BPU acceleration.
  - Supports 4 emotion categories: happy, sad, angry, neutral.
  - Automatically triggers corresponding animations when confidence > 0.5.

- **Expressive Animation Playback**
  - Supports 13 expressive animations (happy, sad, angry, neutral, blink, excited, etc.).
  - Full-screen display with automatic screen resolution adaptation.
  - Animation queue management to prevent playback conflicts.

- **Weather Information Inquiry**
  - Integrates with the QWeather API.
  - Displays detailed information including temperature, humidity, and weather conditions.
  - Voice broadcast of weather information, automatically returning to standby after 5 seconds.

- **Servo Control**
  - Initialization sequence: automatically performs left → right → center movement on startup.
  - Smooth motion control supporting 0-180 degree range.
  - Intelligent filtering and tracking algorithm based on hand position.

### Xiaohun Voice Assistant

- **Emotion-Aware Dialogue**
  - Dynamically adjusts response style based on user emotion.
  - AI proactively initiates conversation (when there is no voice input).
  - Supports mixed Chinese-English recognition.

- **Voice Service Integration**
  - Baidu ASR (Automatic Speech Recognition).
  - DeepSeek LLM for intelligent dialogue.
  - Edge TTS for speech synthesis.

- **Dialogue History Management**
  - Synchronizes to web server via HTTP API.
  - Supports historical record querying.

---

## System Requirements

### Hardware Requirements

- RDK X5 development board (10 TOPS BPU compute power).
- USB camera (for gesture and emotion recognition).
- Microphone and speaker (for voice interaction).
- SG90 servo (for head tracking).
- Display screen (for animations and weather information).

### Software Requirements

- Python 3.8+
- ROS2 Humble
- TROS (Horizon Robotics Operating System)

---

## Project Structure

```
rdk-x5-emotion-robot/
├── emotion.py             # Emotion recognition main program (BPU accelerated)
├── main.py                # Robot main control program
├── xiaohun.py             # Xiaohun voice assistant
├── http_server.py         # HTTP API server
├── requirements.txt       # Python dependencies
├── emotions/              # Expression animation resource folder
│   ├── happy/             # Happy animation frames
│   ├── sad/               # Sad animation frames
│   ├── angry/             # Angry animation frames
│   ├── neutral/           # Neutral animation frames
│   ├── blink/             # Blink animation frames
│   ├── excited/           # Excited animation frames
│   ├── dizzy/             # Dizzy animation frames
│   ├── happy2/            # Happy2 animation frames
│   ├── happy3/            # Happy3 animation frames
│   ├── blink2/            # Blink2 animation frames
│   ├── bootup/            # Bootup animation frames
│   ├── bootup3/           # Bootup3 animation frames
│   └── sleep/             # Sleep animation frames
├── README-cn.md 
└── README.md              # This file
```

---

## Usage Instructions

### 1. Preparation

1. **Prepare Model File**
   - Place the quantized YOLOv8s_emotion model in the specified path.
   - Ensure the model file is in `.bin` format.

2. **Prepare Expression Animation Resources**
   - Ensure the `emotions/` folder exists.
   - Each expression folder should contain sequentially named frame images (frame0.png, frame1.png, ...).

3. **Configure API Keys**
   - Configure Baidu ASR, DeepSeek, and Weather API keys in the corresponding programs.

### 2. Launch the System

**Launch Separately (Recommended for Debugging):**

```bash
# Terminal 1: Start emotion recognition
source /opt/tros/humble/setup.bash
python3 emotion.py

# Terminal 2: Start main control
source /opt/tros/humble/setup.bash
python3 main.py

# Terminal 3: Start voice assistant
source /opt/tros/humble/setup.bash
python3 xiaohun.py

# Terminal 4: Start HTTP server
python3 http_server.py
```

### 3. Gesture Control Mapping

| Gesture ID | Gesture Type | Function |
|------------|--------------|----------|
| 11 | Okay | Query weather and broadcast via voice |
| 12 | Left | Activate Xiaohun voice assistant |
| 13 | Right | Deactivate Xiaohun voice assistant |
| 2 | Thumbs Up | Play random expression animation |
| 3 | V Sign | Enable head following mode |

### 4. Emotion Triggering Workflow

1. `emotion.py` recognizes user emotion in real-time.
2. Upon detecting a change in emotion (confidence > 0.5), it publishes to the `/emotion_animation_trigger` topic.
3. `main.py` receives the trigger signal and plays the corresponding expression animation.
4. Simultaneously, it publishes the emotion status via `/user_emotion` to the voice assistant.
5. The voice assistant adjusts its response style based on the emotion.

---

## ROS2 Topic Communication

### Published Topics

| Node | Topic | Type | Description |
|------|-------|------|-------------|
| emotion.py | `/user_emotion` | String | Emotion status (JSON format) |
| emotion.py | `/emotion_animation_trigger` | String | Animation trigger signal |
| main.py | `/xiaozhi_video` | Bool | Xiaohun control switch |
| main.py | `/robot_speech` | String | Voice broadcast content |

### Subscribed Topics

| Node | Topic | Type | Description |
|------|-------|------|-------------|
| main.py | `/user_emotion` | String | Receive emotion status |
| main.py | `/emotion_animation_trigger` | String | Receive animation trigger |
| main.py | `/hobot_hand_gesture_detection` | PerceptionTargets | Gesture recognition results |
| xiaohun.py | `/xiaozhi_video` | Bool | Recording control signal |
| http_server.py | `/user_emotion` | String | Emotion status (API display) |
| http_server.py | `/image` | CompressedImage | Camera image (video stream) |

---

## Expression Animation List

| Animation Name | Frame Count | Description |
|----------------|-------------|-------------|
| happy | 49 | Happy expression |
| sad | 45 | Sad expression |
| angry | 24 | Angry expression |
| neutral | 56 | Neutral expression |
| blink | 39 | Blink animation |
| excited | 24 | Excited expression |
| dizzy | 63 | Dizzy expression |
| happy2 | 22 | Happy expression 2 |
| happy3 | 25 | Happy expression 3 |
| blink2 | 23 | Blink animation 2 |
| bootup | 118 | Startup animation |
| bootup3 | 113 | Startup animation 3 |
| sleep | 121 | Sleep animation |

---

## Servo Control Parameters

- **PWM Frequency**: 50Hz
- **Duty Cycle Range**: 2.5% - 12.5% (corresponding to 0°-180°)
- **Initialization Sequence**: Left (5%) → Right (10%) → Center (7.5%)
- **Tracking Frequency**: Processed every 10 frames
- **Filter Coefficients**: Hand position 0.3, Duty cycle 0.05

---

## HTTP API Interface

After launching `http_server.py`, the following endpoints are available:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Get complete status (emotion + system + Xiaohun) |
| `/api/camera` | GET | Get a single image frame |
| `/api/camera_stream` | GET | Real-time video stream (MJPEG) |
| `/api/emotions` | GET | Get current emotion |
| `/api/history` | GET | Get dialogue history |
| `/health` | GET | Health check |

Access URL: `http://<RDK_X5_IP>:5000`

---

## Troubleshooting

### Emotion Recognition Not Working

1. Check if the model file path is correct.
2. Verify the camera is properly connected.
3. Check if the ROS topic `/image` is being published.
4. Check BPU driver status: `hrut_bpuprofile -b 0 -r 1`

### Servo Not Responding

1. Verify GPIO pin configuration (default is pin 33).
2. Ensure the servo power connection is normal (5V supply).
3. Check if the PWM signal is being output correctly.
4. Verify GPIO permissions: `sudo chmod 666 /dev/gpiochip0`

### Animations Not Displaying

1. Confirm the `emotions/` folder exists.
2. Verify animation frame file naming (frame0.png, frame1.png, ...).
3. Ensure image files are in PNG format.
4. Check display environment variable: `echo $DISPLAY`

### Voice Assistant Not Responding

1. Verify microphone and speaker connections.
2. Confirm API keys are correctly configured.
3. Check the log file `xiaohun.log` for detailed error information.
4. Test audio devices: `arecord -l` and `aplay -l`

---


**Note:** Please read the configuration instructions carefully before use to ensure correct hardware connections. It is recommended to test each module separately first before using a one-click startup script.
