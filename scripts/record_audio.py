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
ensure_package.pip("soundcard")  
ensure_package.pip("pydub", "pydub", "AudioSegment")
import soundcard as sc
import soundfile as sf

logger = LoggerManager.setup_logger(logger_name="music-toolkit")

try:
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent  # 用于检测非静音区间的模块
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

def record_system_audio(duration_min, output_wav="output.wav", output_mp3=None, save_dir=None, 
                                   auto_trim=False, silence_thresh=-45, min_silence_len=1000):
    """
    录制声卡输出的系统声音（支持自动裁剪前后静音）
    
    :param duration_min: 录制时长（分钟）
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
    
    logger.info(f"🎙️ 准备录制系统声音，时长：{duration_min} 分钟 ({duration_sec} 秒)...")

    # 4. 开始录音
    try:
        default_speaker = sc.default_speaker()
        loopback_mic = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)

        with loopback_mic.recorder(samplerate=SAMPLE_RATE) as mic:
            logger.info("🔴 正在录音中...")
            data = mic.record(numframes=SAMPLE_RATE * duration_sec)
            logger.info("⏹️ 录音结束。")

        # 先写入原始 WAV 文件
        sf.write(file=full_wav_path, data=data, samplerate=SAMPLE_RATE)
        
        # 5. ✨ 新增功能：自动裁剪前后静音
        if auto_trim:
            if not PYDUB_AVAILABLE:
                logger.info("⚠️ 缺少 pydub 库，无法执行自动裁剪，保持原样。")
            else:
                logger.info("⏳ 正在分析音频，自动裁剪前后的静音与杂音...")
                # 读取刚录制好的 WAV
                audio = AudioSegment.from_wav(full_wav_path)
                orig_duration = len(audio)  # 原始时长（毫秒）
                
                # 检测所有“非静音”的区间
                # nonsilent_chunks 返回格式如: [[start_1, end_1], [start_2, end_2]]
                nonsilent_chunks = detect_nonsilent(
                    audio, 
                    min_silence_len=min_silence_len, 
                    silence_thresh=silence_thresh
                )
                
                if nonsilent_chunks:
                    # 歌曲真正的开始时间 = 第一个非静音块的起点
                    start_time = nonsilent_chunks[0][0]
                    # 歌曲真正的结束时间 = 最后一个非静音块的终点
                    end_time = nonsilent_chunks[-1][1]
                    
                    # 执行裁剪
                    trimmed_audio = audio[start_time:end_time]
                    
                    # 打印裁剪报告
                    logger.info(f"✂️ 自动裁剪完成：")
                    logger.info(f"   ↳ 切除前端静音: {start_time / 1000:.2f} 秒")
                    logger.info(f"   ↳ 切除后端静音: {(orig_duration - end_time) / 1000:.2f} 秒")
                    logger.info(f"   ↳ 歌曲实际长度: {len(trimmed_audio) / 1000:.2f} 秒")
                    
                    # 将裁剪后的音频覆盖写入 WAV 文件
                    trimmed_audio.export(full_wav_path, format="wav")
                else:
                    logger.info("⚠️ 未在录音中检测到足够大声音的内容，跳过裁剪（可能整段都是静音）。")

        final_file = full_wav_path

        # 6. 音频格式转换 (WAV -> MP3)
        if full_mp3_path:
            if not PYDUB_AVAILABLE:
                return False, "缺少 pydub 库，无法转换为 MP3。"
                
            logger.info("⏳ 正在转换为最终 MP3 格式...")
            try:
                # 重新读取可能已经被裁剪过的 WAV
                audio = AudioSegment.from_wav(full_wav_path)
                audio.export(full_mp3_path, format="mp3", bitrate="192k")
                logger.info(f"✅ MP3 转换成功: {full_mp3_path}")
                final_file = full_mp3_path
            except FileNotFoundError:
                return False, "转换失败：系统中未找到 FFmpeg。"

        return True, os.path.abspath(final_file)

    except Exception as e:
        error_msg = f"录音或处理过程中发生异常: {str(e)}"
        logger.info(f"❌ {error_msg}")
        return False, error_msg