# -*- coding: utf-8 -*-
import cv2
import numpy as np
import time
from ultralytics import YOLO
import argparse


class YOLOv11Seg:
    """
    基于 ultralytics.YOLO 进行实例分割推理
    对外接口保持不变:
    detect(srcimg) -> (out_img, classIds, confidences, boxes, cost_time)
    """
    def __init__(self,
                 model_path,
                 label_path,
                 confThreshold=0.5,
                 nmsThreshold=0.45,
                 device='cpu'):
        # 1. 加载官方 YOLO 实例分割模型
        self.model = YOLO("driver/bestseg.pt")
        self.device = device                # cpu / cuda
        # 2. 读类别
        with open(label_path, encoding='utf-8') as f:
            self.classes = [x.strip() for x in f.readlines()]

        self.confThreshold = confThreshold
        self.nmsThreshold = nmsThreshold

    # -----------------------------------------------------------
    def detect(self, srcimg):
        """
        推理单张图，返回与原脚本一致的 5 个值。
        out_img 使用 Ultralytics 自带 results.plot() 绘制
        """
        t1 = time.time()
        results = self.model.predict(
            srcimg,
            conf=self.confThreshold,
            iou=self.nmsThreshold,
            device=self.device,
            verbose=False
        )[0]
        t2 = time.time()

        # ---------- 提取与原脚本一致的数据 ----------
        boxes_xyxy, confidences, classIds = [], [], []
        if results.boxes is not None:
            for box in results.boxes.data.cpu().numpy():
                x1, y1, x2, y2, conf, cls = box[:6]
                boxes_xyxy.append([int(x1), int(y1), int(x2), int(y2)])
                confidences.append(float(conf))
                classIds.append(int(cls))

        # ---------- 关键：用官方 results.plot() ----------
        out_img = results.plot()       # 直接返回带框、带掩码的 BGR 图像

        # ---------- 新增：生成详细的坐标信息 ----------
        h, w = srcimg.shape[:2]
        coord_info_lines = []
        
        if results.masks is not None:
            for idx, contour in enumerate(results.masks.xy):
                # contour: shape (N,2)  float32 像素坐标
                norm_pts = contour / np.array([[w, h]])  # (N,2) / (1,2) -> 归一化
                cls_id = classIds[idx]
                
                # 添加类别和点数信息
                coord_info_lines.append(f"[{self.classes[cls_id]}] {len(norm_pts)}个点:")
                
                # 每行显示一个坐标点
                for i, (x_norm, y_norm) in enumerate(norm_pts):
                    coord_info_lines.append(f"  {i+1:2d}: ({x_norm:.4f}, {y_norm:.4f})")
                
                coord_info_lines.append("----")  # 分隔符
        else:
            coord_info_lines.append("无分割掩码")
            
        info_feature = f"推理耗时: {int((t2-t1)*1000)} ms\n类别置信度:\n"
        info_feature += "\n".join([f"{self.classes[c]}: {conf:.2f}" for c, conf in zip(classIds, confidences)])
        info_axis = "\n".join(coord_info_lines)
        return out_img, info_feature, info_axis

"""
# ----------------- 主程序 -----------------
def main():
    parser = argparse.ArgumentParser(description='YOLOv5-Lite PyTorch 推理')
    parser.add_argument('--model-path', type=str,
                        default="C:\\Users\\86180\\runs\\segment\\train2\\weights\\best.onnx",
                        help='训练完成 best.pt')
    parser.add_argument('--label-path', type=str,
                        default='E:\\dachuang\\YOLOv5-Lite\\shiyong\\names2.txt',
                        help='类别文件')
    parser.add_argument('--conf-threshold', type=float, default=0.45)
    parser.add_argument('--nms-threshold', type=float, default=0.5)
    parser.add_argument('--device', type=str, default='cpu', help='cpu / 0 / 0,1,2,3')

    args = parser.parse_args()

    detector = YOLOv11Seg(args.model_path, args.label_path,
                          confThreshold=args.conf_threshold,
                          nmsThreshold=args.nms_threshold,
                          device=args.device)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        key = cv2.waitKey(1) & 0xFF

        if key == ord(' '):
            out_img, classIds, confs, boxes, t = detector.detect(frame)
            print(f"推理时间: {int(t*1000)} ms")
            if len(classIds) == 0:
                print("未找到目标")
            else:
                for cls, conf in zip(classIds, confs):
                    print(f"类别: {detector.classes[cls]}, 置信度 {conf:.2f}")
            cv2.imshow("Inference Result", out_img)

        elif key == ord('q'):
            break

        cv2.imshow("Camera Stream", frame)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
"""