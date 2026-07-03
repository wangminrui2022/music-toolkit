#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Skill Name: music-toolkit
Author: 王岷瑞 / https://github.com/wangminrui2022
License: Apache License
Description: 模块说明：音乐录制工具命令行入口 (music-toolkit)
该脚本是 "AI 驱动型系统音频录制与精准切歌工具" 的主入口文件（CLI）。它负责运行环境的自动化检查与修复、解析用户输入的命令行参数，并最终调用底层核心音频模块执行录制任务。
运行环境自动化管理
依赖检测与安装：运行前自动检查并使用 pip 安装 requests、ffmpeg-downloader 和 pydub 等必要第三方库。
Python 与虚拟环境校验：调用 env_manager 确保 Python 版本合规并正确加载虚拟环境（Venv）。
FFmpeg 自动化无感配置 (ensure_ffmpeg)
自动检测系统是否存在 FFmpeg 核心组件。
若未检测到，脚本会自动判断当前操作系统（Windows/Linux/macOS），并调用 ffdl 自动下载对应的便携版（免去手动配置环境变量的麻烦）。
修复了传统的交互式确认，通过代码注入 Y\n 实现完全自动化无人值守安装。
命令行交互接口 (CLI)
提供丰富的参数配置（如录音时长、保存路径、自动裁剪、静音阈值等），方便用户通过终端或外部脚本进行调用。
音频录制调度
解析参数后，将参数校验并下发给 record_audio.record_system_audio 核心函数，执行实际的系统声音捕获、格式转换（WAV/MP3）以及后期去静音裁剪。
"""

import os
import argparse
import subprocess
import env_manager
from datetime import datetime
from config import MODEL_DIR, SKILL_ROOT, VENV_DIR
from logger_manager import LoggerManager
import record_audio
#import record_allin1
import ensure_package
ensure_package.pip("requests")
ensure_package.pip("ffmpeg-downloader")
ensure_package.pip("pydub", "pydub", "AudioSegment")
from pydub import AudioSegment
import ffmpeg_downloader as ffdl
import importlib
import re

logger = LoggerManager.setup_logger(logger_name="music-toolkit")

def ensure_ffmpeg():
    """自动检测 + 下载 ffmpeg（已彻底修复 --quiet 错误 + 更稳定）"""
    # 关键修复：判断 None + 移除 --quiet
    if ffdl.ffmpeg_path is None or not os.path.exists(ffdl.ffmpeg_path):
        logger.info("⚠️  未检测到 ffmpeg，正在自动下载便携版到本地（只需一次，约 100-200MB）...")
        logger.info("   下载来源：Windows=gyan.dev | Linux=johnvansickle | macOS=evermeet")
        
        # 🔥 关键：自动输入 Y（默认 yes），彻底无交互
        logger.info("   自动确认下载中...")
        subprocess.run(["ffdl", "install"], input="Y\n", text=True, check=True)
        
        # 下载完后刷新模块
        importlib.reload(ffdl)
        
        logger.info("✅ 下载 + 安装完成！") 
        #C:\Users\Administrator\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin

    # 添加到 PATH + 强制 pydub 使用
    ffdl.add_path()
    AudioSegment.converter = ffdl.ffmpeg_path

    logger.info(f"✅ ffmpeg 已就绪 → {ffdl.ffmpeg_path}")
    return True

if __name__ == "__main__":
    env_manager.check_python_version()
    env_manager.setup_venv()    
    ensure_ffmpeg()

    parser = argparse.ArgumentParser(description="AI 驱动型系统音频录制与精准切歌工具")
    parser.add_argument("-t", "--duration", type=str, default=10.0, required=True, help="预计录制总时长（分钟）")
    #parser.add_argument("-ai", "--ai-split", action="store_true", help="是否开启 AI 多首歌曲录制并自动精准切割模式")
    parser.add_argument("-d", "--save-dir", type=str, default="record", help="单曲输出目录")
    parser.add_argument("-p", "--filename-prefix", type=str, default=None, help="文件名前缀")
    parser.add_argument("-trim", "--auto-trim", action="store_true", help="是否自动裁剪歌曲前后的静音/杂音")
    parser.add_argument("-sh", "--silence-thresh", type=int, default=-45, help="静音分贝阈值 (dBFS)，默认 -45")
    parser.add_argument("-msl", "--min-silence-len", type=int, default=1000, help="判定为静音的最短时间 (毫秒)")

    args = parser.parse_args()
    
    duration_min=args.duration
    if re.fullmatch(r"\d+(\.\d+)?", duration_min) and float(duration_min) > 0:
        filename=args.filename_prefix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if filename is None:
            output_wav = f"{timestamp}.wav"
            output_mp3 = f"{timestamp}.mp3"
        else:
            output_wav = f"{filename}.wav"
            output_mp3 = f"{filename}.mp3"
        
        #执行哪种录制流程
        # if args.ai_split:#执行录制多首并由 AI 切割的逻辑
        #     success, msg = record_allin1.record_and_ai_precise_split(
        #         duration_min=float(duration_min),
        #         save_dir=args.save_dir)              
        # else:
        success, result = record_audio.record_system_audio(
        duration_min=float(duration_min), 
        output_wav=output_wav,
        output_mp3=output_mp3,
        save_dir=args.save_dir,
        auto_trim=args.auto_trim,
        silence_thresh=args.silence_thresh,
        min_silence_len=args.min_silence_len)
        logger.info(f"✅ success → {result}")
    else:
        logger.info(f"\n❌ 录音 -u 必须输入整数：{duration_min}")