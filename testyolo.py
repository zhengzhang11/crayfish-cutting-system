# -*- coding: utf-8 -*-
"""
YOLOv5-Lite 实时检测（秒开窗口版）
模型在后台线程懒加载，不阻塞摄像头窗口
"""
import argparse
import cv2
import torch
import numpy as np
import time
import sys
import os
from pathlib import Path
from numpy import random
import threading
from multiprocessing import Value   # 轻量共享变量
import warnings
warnings.filterwarnings("ignore", "torch.meshgrid")
# ---------- PyTorch 2.x 兼容性补丁 ----------
print(f"PyTorch: {torch.__version__}")
if torch.__version__.startswith('2.'):
    _torch_load = torch.load
    torch.load = lambda *a, **k: _torch_load(*a, **{**k, 'weights_only': False})

# ---------- 复用 detect.py 工具 ----------
YOLOV5_ROOT = Path('E:/dachuang/YOLOv5-Lite').resolve()
sys.path.insert(0, str(YOLOV5_ROOT))
from models.experimental import attempt_load
from utils.general import non_max_suppression, scale_coords
from utils.plots import plot_one_box
from utils.torch_utils import select_device


class YOLOv5Lite:
    """
    对外接口保持不变：detect(srcimg) -> (out_img, classIds, confidences, boxes, cost_time)
    """
    def __init__(self,
                 model_pt_path,
                 label_path,
                 confThreshold=0.5,
                 nmsThreshold=0.45,
                 device='cpu'):
        self.model_pt_path = model_pt_path
        self.label_path    = label_path
        self.confThreshold = confThreshold
        self.nmsThreshold  = nmsThreshold
        self.device        = select_device(device)
        self.imgsz         = 640
        self.ready         = Value('b', False)   # 0=未加载  1=已加载
        self.model         = None
        # 后台线程加载
        threading.Thread(target=self._lazy_load, daemon=True).start()

    # ---------- 后台真正加载 ----------
    def _lazy_load(self):
        t0 = time.time()
        # fuse=True 去掉 BN，推理更快
        self.model = attempt_load(self.model_pt_path,
                                  map_location=self.device)
        self.stride = int(self.model.stride.max())
        self.model.eval()

        # CPU/GPU 预热一次
        dummy = torch.zeros(1, 3, self.imgsz, self.imgsz).to(self.device)
        self.model(dummy)

        # 类别
        with open(self.label_path, encoding='utf-8') as f:
            self.classes = [x.strip() for x in f.readlines()]
        self.colors = [[random.randint(0, 255) for _ in range(3)]
                       for _ in self.classes]

        self.ready.value = True
        print(f"[后台] 模型加载+预热完成，耗时 {time.time()-t0:.2f}s")

    # ---------- 推理 ----------
    def detect(self, srcimg):
        if not self.ready.value:
            # 模型未就绪，返回原图
            return srcimg, [], [], [], 0.0

        h0, w0 = srcimg.shape[:2]
        # letterbox
        img = cv2.resize(srcimg, (self.imgsz, self.imgsz),
                         interpolation=cv2.INTER_LINEAR)
        img = img[:, :, ::-1].transpose(2, 0, 1)  # BGR->RGB, HWC->CHW
        img = np.ascontiguousarray(img)
        img = torch.from_numpy(img).to(self.device)
        img = img.float() / 255.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)

        t0 = time.time()
        with torch.no_grad():
            pred = self.model(img, augment=False)[0]
            pred = non_max_suppression(pred, self.confThreshold,
                                       self.nmsThreshold, agnostic=True)
        cost = time.time() - t0

        det = pred[0]  # batch_size=1
        boxes, confidences, classIds = [], [], []

        if len(det):
            det[:, :4] = scale_coords(img.shape[2:], det[:, :4], srcimg.shape).round()
            for *xyxy, conf, cls in reversed(det):
                x1, y1, x2, y2 = map(int, xyxy)
                boxes.append([x1, y1, x2, y2])
                confidences.append(float(conf))
                classIds.append(int(cls))
                label = f'{self.classes[int(cls)]} {conf:.2f}'
                plot_one_box(xyxy, srcimg, label=label,
                             color=self.colors[int(cls)], line_thickness=2)

        return srcimg, classIds, confidences, boxes, cost

"""
# ----------------- 主程序 -----------------
def main():
    parser = argparse.ArgumentParser(description='YOLOv5-Lite 实时检测')
    parser.add_argument('--model-path', type=str,
                        default=r'E:\机创电控\outcome\第一次结果（0.995,0.544）\weights\best.pt',
                        help='best.pt')
    parser.add_argument('--label-path', type=str,
                        default=r'E:\dachuang\YOLOv5-Lite\shiyong\names1.txt',
                        help='类别文件')
    parser.add_argument('--conf-threshold', type=float, default=0.3)
    parser.add_argument('--nms-threshold',  type=float, default=0.5)
    parser.add_argument('--device', type=str, default='cpu', help='cpu / cuda')
    args = parser.parse_args()

    detector = YOLOv5Lite(args.model_path, args.label_path,
                          confThreshold=args.conf_threshold,
                          nmsThreshold=args.nms_threshold,
                          device=args.device)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return

    print("窗口已启动，模型后台加载中...\n"
          "按空格检测  |  按 q/ESC 退出")
    frame_cnt = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_cnt += 1
        key = cv2.waitKey(1) & 0xFF

        # 空格检测
        if key == ord(' '):
            if detector.ready.value:
                out, ids, confs, boxes, t = detector.detect(frame)
                print(f"推理 {t*1000:.1f} ms | "
                      f"检测 {len(ids)} 目标")
                cv2.imshow("Detection", out)
            else:
                print("模型尚未加载完成，请稍候...")

        elif key == ord('q') or key == 27:
            break

        # 实时画面
        cv2.putText(frame, f"Frame {frame_cnt}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Camera", frame)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
"""