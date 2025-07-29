# app.py
from flask import Flask, Response
from flask_cors import CORS
import cv2

app = Flask(__name__)
CORS(app)          # 允许跨域，方便前端直接嵌入
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Windows 用 CAP_DSHOW 更快
# Linux 直接 cv2.VideoCapture(0)

def gen_frames():
    while True:
        success, frame = cap.read()
        if not success:
            break
        # 可在此处做图像处理，例如：
        # frame = cv2.flip(frame, 1)
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    # 返回 multipart/x-mixed-replace 流
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    # 一个极简页面，也可换成你自己的 index.html
    return '''
    <h1>USB 摄像头实时流</h1>
    <img src="/video_feed" width="640" height="480"/>
    '''

if __name__ == '__main__':
    # threaded=True 让多客户端同时观看
    app.run(host='0.0.0.0', port=5000, threaded=True)