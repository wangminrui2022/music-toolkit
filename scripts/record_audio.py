#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Skill Name: music-toolkit
Author: 王岷瑞 / https://github.com/wangminrui2022
License: Apache License
Description: 该脚本提供了一个核心函数 record_system_audio，用于捕获电脑系统内部正在播放的声音（内录）。
它支持自动切除录音前后的静音片段，并能将录音结果无损保存为 WAV 格式或压缩保存为标准 MP3 格式。
核心特性
真实内录 (Loopback)：绕过外部麦克风，直接数字级捕获扬声器输出的音频，无外环境杂音。
智能裁剪 (Auto Trim)：自动检测并切除音频首尾的静音/轻微底噪，精准保留歌曲或人声主体。
多格式导出：支持导出高质量无损 WAV (48kHz) 以及压缩 MP3 (192kbps)。
健壮性设计：内置动态依赖检查与容错机制，防止因缺少第三方库或外部组件（如 FFmpeg）导致程序崩溃。

"""

import os
import math 
from config import MODEL_DIR, SKILL_ROOT, VENV_DIR
from logger_manager import LoggerManager
import ensure_package

# 自动确保依赖库已安装
ensure_package.pip("soundcard")  
ensure_package.pip("pydub", "pydub", "AudioSegment")
ensure_package.pip("pynput")  # ✨ 新增：用于监听鼠标和键盘事件

import soundcard as sc
import soundfile as sf
import gradient_overlay
import numpy as np  # ✨ 新增：soundcard 返回的是 numpy 数组，需要用它来拼接音频
from pynput import keyboard  # ✨ 新增：导入监听器

logger = LoggerManager.setup_logger(logger_name="music-toolkit")

try:
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent  # 用于检测非静音区间的模块
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

is_recording = False
recording_thread = None

def record_system_audio(duration_min, output_wav="output.wav", output_mp3=None, save_dir=None, 
                        auto_trim=False, silence_thresh=-45, min_silence_len=1000):
    """
    录制声卡输出的系统声音（支持自动裁剪前后静音，支持鼠标点击或键入ESC提前终止）
    
    :param duration_min: 最大录制时长（分钟）
    :param output_wav: 保存的 WAV 文件名
    :param output_mp3: 保存的 MP3 文件名
    :param save_dir: 保存目录
    :param auto_trim: 是否开启自动裁剪前后静音/杂音的功能
    :param silence_thresh: 静音阈值（单位：dBFS）。越小越严格，-45 到 -50 适合录制歌曲。
    :param min_silence_len: 判定为静音的最短时间（单位：毫秒），默认 1000ms（1秒）
    """
    # 1. 参数类型检查与转换
    try:
        duration_min = float(duration_min)
    except ValueError:
        error_msg = f"输入的时长 '{duration_min}' 不是一个有效的数字！"
        logger.info(f"❌ 错误：{error_msg}")
        return False, error_msg

    # 2. 处理保存目录
    if save_dir is None:
        save_dir = os.path.join(os.getcwd(), "record")
    os.makedirs(save_dir, exist_ok=True)

    full_wav_path = os.path.join(save_dir, output_wav)
    full_mp3_path = os.path.join(save_dir, output_mp3) if output_mp3 else None

    # 3. 计算录制秒数
    duration_sec = math.ceil(duration_min * 60)
    SAMPLE_RATE = 48000 
    
    logger.info(f"🎙️ 准备录制系统声音，最大时长：{duration_min} 分钟 ({duration_sec} 秒)...")
    logger.info("💡 提示：录音期间随时【按下 ESC 键】可提前结束录音。")
    gradient_overlay.safe_sleep(0.5)
    gradient_overlay.update_overlay_text(f"🎙️ 准备录制系统声音 ({duration_sec}秒)...")
    gradient_overlay.safe_sleep(0.5)

    # 4. 开始录音
    try:
        default_speaker = sc.default_speaker()
        loopback_mic = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)

        gradient_overlay.safe_sleep(0.5)
        gradient_overlay.update_overlay_text("🔴 录音中... (按ESC键停止)")
        gradient_overlay.safe_sleep(0.5)
        
        # --- ✨ 设置终止录音的控制开关和监听器 ---
        # 通过环境变量 MUSIC_TOOLKIT_NO_KB=1 可禁用键盘监听（避免误触 ESC）
        stop_recording = False
        key_listener = None
        if os.environ.get("MUSIC_TOOLKIT_NO_KB") != "1":
            def on_press(key):
                nonlocal stop_recording
                if key == keyboard.Key.esc:
                    logger.info("⌨️ 检测到按下ESC键，正在终止录音...")
                    stop_recording = True
                    return False  # 停止键盘监听
            # 启动后台异步监听
            key_listener = keyboard.Listener(on_press=on_press)
            key_listener.start()
        else:
            logger.info("⌨️ 键盘监听已禁用 (MUSIC_TOOLKIT_NO_KB=1)")
        # ---------------------------------------------

        chunks = []
        frames_recorded = 0
        total_frames = SAMPLE_RATE * duration_sec
        # 每次读取 0.1 秒的音频帧数 (48000 * 0.1 = 4800)
        chunk_frames = int(SAMPLE_RATE * 0.1) 

        with loopback_mic.recorder(samplerate=SAMPLE_RATE) as mic:
            logger.info("🔴 正在录音中...")
            
            # ✨ 将单次阻塞录音改为分块循环录音
            while frames_recorded < total_frames and not stop_recording:
                remaining_frames = total_frames - frames_recorded
                current_chunk = min(chunk_frames, remaining_frames)
                
                # 录制一小段
                chunk_data = mic.record(numframes=current_chunk)
                chunks.append(chunk_data)
                frames_recorded += current_chunk

            logger.info("⏹️ 录音结束。")

        # 确保销毁监听器，释放系统资源
        if key_listener is not None:
            key_listener.stop()

        # 如果没有录制到数据，直接返回
        if not chunks:
            return False, "未录制到任何音频数据。"

        # 将所有录制的小音频块拼接到一起
        data = np.concatenate(chunks, axis=0)

        gradient_overlay.safe_sleep(0.5)
        gradient_overlay.update_overlay_text("⏹️ 录音结束。")
        gradient_overlay.safe_sleep(0.5)

        # 先写入原始 WAV 文件
        sf.write(file=full_wav_path, data=data, samplerate=SAMPLE_RATE)
        
        # 5. ✨ 自动裁剪前后静音 (保持原逻辑不变)
        if auto_trim:
            if not PYDUB_AVAILABLE:
                logger.info("⚠️ 缺少 pydub 库，无法执行自动裁剪，保持原样。")
            else:
                logger.info("⏳ 正在分析音频，自动裁剪前后的静音与杂音...")
                audio = AudioSegment.from_wav(full_wav_path)
                orig_duration = len(audio)
                
                nonsilent_chunks = detect_nonsilent(
                    audio, 
                    min_silence_len=min_silence_len, 
                    silence_thresh=silence_thresh
                )
                
                if nonsilent_chunks:
                    start_time = nonsilent_chunks[0][0]
                    end_time = nonsilent_chunks[-1][1]
                    
                    trimmed_audio = audio[start_time:end_time]
                    
                    logger.info(f"✂️ 自动裁剪完成：")
                    logger.info(f"   ↳ 切除前端静音: {start_time / 1000:.2f} 秒")
                    logger.info(f"   ↳ 切除后端静音: {(orig_duration - end_time) / 1000:.2f} 秒")
                    logger.info(f"   ↳ 歌曲实际长度: {len(trimmed_audio) / 1000:.2f} 秒")
                    gradient_overlay.safe_sleep(0.5)
                    gradient_overlay.update_overlay_text("✂️ 自动裁剪完成")  
                    gradient_overlay.safe_sleep(0.5)                                 
                    trimmed_audio.export(full_wav_path, format="wav")
                else:
                    logger.info("⚠️ 未在录音中检测到足够大声音的内容，跳过裁剪。")

        final_file = full_wav_path

        # 6. 音频格式转换 (WAV -> MP3) (保持原逻辑不变)
        if full_mp3_path:
            if not PYDUB_AVAILABLE:
                return False, "缺少 pydub 库，无法转换为 MP3。"
                
            logger.info("⏳ 正在转换为最终 MP3 格式...")
            try:
                audio = AudioSegment.from_wav(full_wav_path)
                audio.export(full_mp3_path, format="mp3", bitrate="192k")
                logger.info(f"✅ MP3 转换成功: {full_mp3_path}")
                gradient_overlay.safe_sleep(0.5)
                gradient_overlay.update_overlay_text("✅ MP3 转换成功") 
                gradient_overlay.safe_sleep(0.5)   
                final_file = full_mp3_path
            except FileNotFoundError:
                return False, "转换失败：系统中未找到 FFmpeg。"

        return True, os.path.abspath(final_file)

    except Exception as e:
        error_msg = f"录音或处理过程中发生异常: {str(e)}"
        logger.info(f"❌ {error_msg}")
        return False, error_msg