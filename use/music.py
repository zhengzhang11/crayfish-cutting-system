#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
music.py
在Windows系统中播放音频文件
支持多种音频格式：mp3, wav, etc.
"""
import subprocess
import os
import sys

MP3_PATH = "E:\\balance\\文献\\传感器类\\薛之谦-认真的雪.mp3"

def play_with_windows_media_player():
    """使用Windows Media Player播放"""
    try:
        os.startfile(MP3_PATH)
        print("正在使用默认播放器播放音频...")
    except Exception as e:
        print(f"播放失败：{e}")

def play_with_pygame():
    """使用pygame播放音频"""
    try:
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(MP3_PATH)
        pygame.mixer.music.play()
        print("正在使用pygame播放音频...")
        
        # 等待播放完成
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)
            
    except ImportError:
        print("pygame未安装，请运行：pip install pygame")
    except Exception as e:
        print(f"pygame播放失败：{e}")

def main():
    print("Windows音频播放器")
    print("-" * 30)
    
    # 检查文件是否存在
    if not os.path.exists(MP3_PATH):
        print(f"错误：音频文件不存在 - {MP3_PATH}")
        return
    
    print("选择播放方式：")
    print("1. 使用默认播放器（推荐）")
    print("2. 使用pygame播放")
    
    choice = input("请输入选择 (1 或 2): ").strip()
    
    if choice == "1":
        play_with_windows_media_player()
    elif choice == "2":
        play_with_pygame()
    else:
        print("直接使用默认播放器播放...")
        play_with_windows_media_player()

if __name__ == "__main__":
    main()