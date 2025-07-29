# 小龙虾智能视觉切割系统 - 安装部署指南

## 📋 系统要求

### 硬件要求
- **CPU**: Intel i5-8400 或 AMD Ryzen 5 3600 以上
- **内存**: 16GB RAM (推荐 32GB)
- **显卡**: NVIDIA GTX 1060 6GB 或更高 (支持CUDA计算)
- **存储**: 100GB 可用空间 (SSD推荐)
- **摄像头**: USB 3.0 工业相机 (分辨率≥1920x1080)

### 软件环境
- **操作系统**: Windows 10/11 (64位) 或 Ubuntu 18.04+
- **Python**: 3.8.x - 3.11.x
- **CUDA**: 11.6+ (如需GPU加速)

## 🚀 快速安装 (Windows)

### 步骤1: 下载项目
```bash
git clone https://github.com/zhangzheng/crayfish-cutting-system.git
cd crayfish-cutting-system
```

### 步骤2: 创建虚拟环境
```bash
python -m venv crayfish_env
crayfish_env\Scripts\activate
```

### 步骤3: 安装依赖
```bash
# 安装基础依赖
pip install -r requirements.txt

# 如需GPU支持，额外安装CUDA版本的PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 步骤4: 下载模型文件
```bash
# 创建模型目录
mkdir driver\models

# 下载小龙虾检测模型 (约185MB)
# 请联系开发团队获取模型下载链接
# 将 crayfish_yolov5_lite.pt 放置到 driver\ 目录
```

### 步骤5: 启动系统
```bash
python main.py
```

默认登录信息:
- 用户名: `zhangzheng`
- 密码: `123456`

## 🐧 Linux 部署指南

### Ubuntu/CentOS 安装
```bash
# 更新系统包
sudo apt update && sudo apt upgrade -y

# 安装系统依赖
sudo apt install python3.8 python3.8-venv python3.8-dev
sudo apt install libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev
sudo apt install libportaudio2 libportaudiocpp0 portaudio19-dev

# 克隆项目
git clone https://github.com/zhangzheng/crayfish-cutting-system.git
cd crayfish-cutting-system

# 创建虚拟环境
python3.8 -m venv crayfish_env
source crayfish_env/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动系统
python main.py
```

## 🔧 详细配置说明

### PyQt5 环境配置
```bash
# Windows 下可能需要额外安装
pip install PyQt5-tools

# Linux 下如遇到 Qt 相关错误
sudo apt install python3-pyqt5 python3-pyqt5.qtmultimedia
export QT_QPA_PLATFORM=xcb  # 如在服务器环境运行
```

### CUDA 环境配置 (GPU加速)
```bash
# 检查CUDA版本
nvcc --version

# 安装对应版本的PyTorch (以CUDA 11.8为例)
pip uninstall torch torchvision torchaudio
pip install torch==2.0.1+cu118 torchvision==0.15.2+cu118 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118

# 验证GPU可用性
python -c "import torch; print(torch.cuda.is_available())"
```

### OpenCV 配置优化
```bash
# 如需摄像头支持，确保安装完整版OpenCV
pip uninstall opencv-python
pip install opencv-python-headless==4.8.1.78
pip install opencv-python==4.8.1.78

# Linux下摄像头权限设置
sudo usermod -a -G video $USER
# 重新登录后生效
```

## 📦 模型文件配置

### 必需模型文件清单

| 文件名 | 大小 | 说明 | 放置路径 |
|--------|------|------|----------|
| `bestyolo.pt` | 3.31MB | 小龙虾检测主模型 | `driver/` |
| `bestseg.pt` | 5.86MB | YOLOv11分割模型 | `driver/` |
| `vosk-model-small-cn-0.22` | 42MB | 中文语音识别 | `driver/` |
| `names1.txt` | 1KB | 检测类别标签 | `driver/` |
| `names2.txt` | 1KB | 分割类别标签 | `driver/` |
### 模型下载脚本
```python
# download_models.py - 自动下载脚本
import os
import requests
from tqdm import tqdm

def download_file(url, filename):
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(filename, 'wb') as file, tqdm(
        desc=filename,
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(chunk_size=1024):
            size = file.write(data)
            bar.update(size)

# 运行下载
python download_models.py
```

## 🎯 摄像头配置

### USB摄像头设置
```python
# 测试摄像头连接
import cv2

# 检测可用摄像头
for i in range(3):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f"摄像头 {i} 可用")
        # 设置分辨率
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.release()
```

### 工业相机配置
```bash
# 安装工业相机驱动 (以海康威视为例)
# 1. 下载并安装 MVS Viewer
# 2. 配置相机IP地址
# 3. 修改系统配置文件

# 在 config.yaml 中设置相机参数
camera:
  device_id: 0  # USB摄像头使用数字ID
  # device_id: "rtsp://192.168.1.100:554/stream"  # 网络相机使用RTSP地址
  resolution: [1920, 1080]
  fps: 30
  exposure: auto
```

## 🔍 性能调优建议

### 系统性能优化
```bash
# Windows 性能设置
# 1. 设置高性能电源模式
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c

# 2. 关闭不必要的系统服务
# 控制面板 → 管理工具 → 服务
# 停用: Windows Search, Superfetch 等

# 3. 设置程序优先级
# 任务管理器中将 python.exe 设为"高"优先级
```

### YOLO模型优化
```python
# 在 sub3.py 中的优化设置
class OptimizedYOLO:
    def __init__(self):
        # 启用混合精度推理
        self.model.half()  # FP16推理，速度提升30%
        
        # 设置最优置信度阈值
        self.conf_threshold = 0.6  # 根据实际情况调整
        self.iou_threshold = 0.45
        
        # 启用TensorRT加速 (如有NVIDIA GPU)
        # self.model = torch.jit.trace(self.model, example_input)
```

## ❌ 常见问题解决

### 问题1: ImportError - 无法导入PyQt5
```bash
# 解决方案
pip uninstall PyQt5 PyQt5-tools
pip install PyQt5==5.15.7 PyQt5-tools==5.15.4.3.2

# 如仍有问题，尝试
conda install pyqt=5.15.7
```

### 问题2: CUDA out of memory
```python
# 在模型初始化时添加内存管理
torch.cuda.empty_cache()

# 或减少批处理大小
batch_size = 1  # 降低为1
```

### 问题3: 摄像头无法打开
```python
# 检查摄像头占用情况
import psutil
for proc in psutil.process_iter(['pid', 'name']):
    if 'camera' in proc.info['name'].lower():
        print(f"进程 {proc.info['pid']} 正在使用摄像头")
```

### 问题4: 语音识别无法工作
```bash
# 检查音频设备
python -c "import pyaudio; p = pyaudio.PyAudio(); print([p.get_device_info_by_index(i)['name'] for i in range(p.get_device_count())])"

# 安装额外的音频库
pip install sounddevice librosa
```

## 📞 技术支持

如在安装过程中遇到问题，请联系:

- **邮箱**: 1120232928@bit.edu.cn
- **项目地址**: https://github.com/zhangzheng/crayfish-cutting-system
**安装成功标志**: 系统启动后显示登录界面，输入凭据后进入主控制面板。

---
*最后更新: 2025年7月28日*
