#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web.py  与 PyQt 对接版本
新增一个可选参数 gui_callback(text:str) 用于流式/状态推送
"""
import time
import platform
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import pyperclip


# -------------- 以下与原文件完全一致 --------------
def minimize_firefox():
    """Linux：瞬间最小化当前 Selenium Firefox 主窗口"""
    import subprocess
    try:
        wid = subprocess.check_output(
            ['xdotool', 'search', '--sync', '--onlyvisible', '--name', 'Mozilla']
        ).strip().split()[0]
        subprocess.run(['xdotool', 'windowminimize', wid],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


class KimiBot:
    def __init__(self,
                 geckodriver_path: str = "driver/geckodriver.exe",
                 gui_callback=None):
        self.geckodriver_path = geckodriver_path
        self.gui_callback = gui_callback  # <-- 新增
        self.driver = None
        self.setup_browser()

    # ----------------- 浏览器初始化 -----------------
    def setup_browser(self) -> None:
        if self.gui_callback:
            self.gui_callback("页面加载中，输入框搜索中")

        options = Options()
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=100,100")
        service = Service(self.geckodriver_path)
        self.driver = webdriver.Firefox(service=service, options=options)
        self.driver.set_window_position(-9000, -9000)
        self.driver.get("https://kimi.moonshot.cn/")
        minimize_firefox()
        try:
            WebDriverWait(self.driver, 30).until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//div[@contenteditable="true"]')
                )
            )
            if self.gui_callback:
                self.gui_callback("Kimi 页面加载完成，输入框已就绪")
            else:
                print("[INFO] Kimi 页面加载完成，输入框已就绪")
        except Exception as e:
            if self.gui_callback:
                self.gui_callback(f"[ERROR] 输入框加载失败: {e}")
            else:
                print(f"[ERROR] 输入框加载失败: {e}")
            self.quit_browser()
            raise

    # ----------------- 公共 helper -----------------
    def _current_answer_count(self) -> int:
        return len(self.driver.find_elements(By.CSS_SELECTOR, ".markdown"))

    def _wait_for_new_answer(self, old_count: int, timeout: int = 60) -> None:
        WebDriverWait(self.driver, timeout).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, ".markdown")) > old_count
        )

    def _wait_streaming_done(self, answer_index: int) -> str:
        selector = f"(//div[@class='markdown'])[{answer_index}]"
        last_len = 0
        stable_since = None
        last_content = ""
        
        while True:
            try:
                node = self.driver.find_element(By.XPATH, selector)
                current_content = node.text
                cur_len = len(current_content)
                
                # 如果内容有变化，实时推送完整内容
                if current_content != last_content and self.gui_callback:
                    self.gui_callback(current_content)  # 推送完整内容
                    last_content = current_content
                
                # 检查是否稳定（内容不再变化）
                if cur_len == last_len and cur_len > 0:
                    if stable_since is None:
                        stable_since = time.time()
                    elif time.time() - stable_since >= 2.0:  # 延长稳定时间确保完整
                        # 最后再推送一次确保完整
                        if self.gui_callback:
                            self.gui_callback(current_content)
                        return current_content
                else:
                    last_len = cur_len
                    stable_since = None
                time.sleep(0.2)  # 缩短轮询间隔
            except Exception:
                return last_content if last_content else ""

    # ----------------- 发送消息 -----------------
    def send_message(self, message: str) -> str:
        try:
            old_cnt = self._current_answer_count()

            input_box = self.driver.find_element(
                By.XPATH, '//div[@contenteditable="true"]'
            )
            input_box.click()
            input_box.send_keys(Keys.CONTROL + "a")
            input_box.send_keys(Keys.DELETE)

            pyperclip.copy(message)
            paste_key = Keys.COMMAND if platform.system() == "Darwin" else Keys.CONTROL
            ActionChains(self.driver).key_down(paste_key).send_keys("v").key_up(
                paste_key
            ).perform()
            time.sleep(0.2)
            input_box.send_keys(Keys.ENTER)

            self._wait_for_new_answer(old_cnt)
            if self.gui_callback:
                self.gui_callback("思考中")  # 状态提示
            return self._wait_streaming_done(old_cnt + 1)
        except Exception as e:
            if self.gui_callback:
                self.gui_callback(f"[ERROR] 发送/获取回复失败: {e}")
            else:
                print(f"[ERROR] 发送/获取回复失败: {e}")
            return ""

    # ----------------- 退出 -----------------
    def quit_browser(self) -> None:
        if self.driver:
            self.driver.quit()
            if not self.gui_callback:
                print("[INFO] 浏览器已关闭")


# -------------- 语音播报函数保持不变 --------------
import pygame
import tempfile
import os

def speak(text: str) -> None:
    """使用 Windows SAPI 语音合成 + pygame 播放"""
    if not text.strip():
        return
    try:
        import win32com.client
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Rate = 2
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_wav_path = temp_file.name
        file_stream = win32com.client.Dispatch("SAPI.SpFileStream")
        file_stream.Open(temp_wav_path, 3)
        old_output = speaker.AudioOutputStream
        speaker.AudioOutputStream = file_stream
        speaker.Speak(text)
        speaker.AudioOutputStream = old_output
        file_stream.Close()
        pygame.mixer.music.load(temp_wav_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)
        try:
            os.unlink(temp_wav_path)
        except:
            pass
    except ImportError:
        print("[警告] 需要安装 pywin32: pip install pywin32")
    except Exception as e:
        print(f"[错误] 语音播放失败: {e}")