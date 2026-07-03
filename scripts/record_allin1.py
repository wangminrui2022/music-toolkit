#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Skill Name: music-toolkit
Author: 王岷瑞 / https://github.com/wangminrui2022
License: Apache License
Description: AI 智能专辑分轨录制系统 (Music Toolkit Pro) 说明
普通的录音切歌工具只能死板地依靠“静音段”来切歌，遇到歌曲开头有前奏淡入、尾部有掌声或淡出时往往切不准。
而这段代码引入了深度学习音频模型 allin1（基于 PyTorch），能够像人类音乐家一样听懂音乐的结构（哪里是前奏、哪里是副歌、哪里是副歌结束），从而实现像素级、结构级的精准分轨。
[ 1. 声卡长录音 ] ──> 录制整张专辑/长歌单 (生成临时大 WAV)
       │
[ 2. VAD 静音粗切 ] ──> 依靠静音间隙切成独立的音频块 (两端故意多留 1 秒缓冲)
       │
[ 3. AI 结构特征分析 ] ──> 调用 allin1 模型，识别 Intro, Verse, Chorus, Outro
       │
[ 4. 像素级对齐裁剪 ] ──> 剔除杂音与死寂缓冲，锁定真正的核心音乐边界
       │
[ 5. 成品导出与清理 ] ──> 导出高品质单曲 (MP3/WAV)，自动销毁所有临时文件
"""

import os
import math 
from config import MODEL_DIR, SKILL_ROOT, VENV_DIR
from logger_manager import LoggerManager
import ensure_package
ensure_package.pip("numpy -i https://pypi.tuna.tsinghua.edu.cn/simple")
ensure_package.pip("Cython -i https://pypi.tuna.tsinghua.edu.cn/simple")
ensure_package.pip("setuptools<82 -i https://pypi.tuna.tsinghua.edu.cn/simple")
ensure_package.pip("torch")  
ensure_package.pip("allin1")  
ensure_package.pip("soundcard")  
ensure_package.pip("pydub", "pydub", "AudioSegment")
ensure_package.pip("madmom -i https://pypi.tuna.tsinghua.edu.cn/simple")
import allin1
import soundcard as sc
import soundfile as sf
from pydub import AudioSegment
from pydub.silence import split_on_silence

logger = LoggerManager.setup_logger(logger_name="music-toolkit")

# ✨ 核心：引入 allin1 音乐结构分析模型
try:
    ALLIN1_AVAILABLE = True
except ImportError:
    ALLIN1_AVAILABLE = False

def record_and_ai_precise_split(duration_min, save_dir="record/ai_songs", output_format="mp3"):
    """
    使用 AI 混合流水线：声卡录音 -> 基础粗切 -> AI深度分析结构 -> 像素级精准裁剪单曲
    """

    # 1. 创建目录与准备临时文件
    os.makedirs(save_dir, exist_ok=True)
    temp_long_wav = os.path.join(save_dir, "temp_album_recording.wav")

    duration_sec = math.ceil(float(duration_min) * 60)
    SAMPLE_RATE = 48000 
    
    # 2. 声卡录音部分
    print(f"🎙️ [AI 专辑模式] 开始录制声卡输出，计划录制：{duration_min} 分钟...")
    try:
        default_speaker = sc.default_speaker()
        loopback_mic = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)

        with loopback_mic.recorder(samplerate=SAMPLE_RATE) as mic:
            print("🔴 正在录制中，请保持歌曲连续播放...")
            data = mic.record(numframes=SAMPLE_RATE * duration_sec)
            print("⏹️ 录音时间到，结束录制。")

        sf.write(file=temp_long_wav, data=data, samplerate=SAMPLE_RATE)

        # 3. 第一阶段：使用静音检测进行【粗略切分】
        print("⏳ 正在进行第一阶段：VAD/静音粗略切分...")
        large_audio = AudioSegment.from_wav(temp_long_wav)
        coarse_chunks = split_on_silence(
            large_audio,
            min_silence_len=1500,  # 歌曲间隙不低于 1.5 秒
            silence_thresh=-45,
            keep_silence=1000      # 前后多留 1 秒缓冲，留给 AI 去做精准切边
        )

        print(f"📋 粗切完成！共抓取到 {len(coarse_chunks)} 个音频块。开始调用 AI 进行精准对齐...")

        if len(coarse_chunks) == 0:
            return False, "未检测到任何歌曲，请检查电脑是否有声音输出或调整分贝阈值。"

        # 4. 第二阶段：循环每个音频块，利用 AI 进行【结构级精准裁剪】
        for i, chunk in enumerate(coarse_chunks):
            temp_chunk_path = os.path.join(save_dir, f"temp_coarse_{i}.wav")
            chunk.export(temp_chunk_path, format="wav")
            
            try:
                print(f"🧠 AI 正在深度分析第 {i+1}/{len(coarse_chunks)} 首歌的音乐结构...")
                # 调用 allin1 模型进行分析
                result = allin1.analyze(temp_chunk_path)
                
                # result.segments 包含了这首歌所有的结构片段，例如：
                # [Segment(start=0.0, end=1.2, label='start'), Segment(start=1.2, end=15.0, label='intro')...]
                music_start = 0.0
                music_end = len(chunk) / 1000.0 # 默认终点
                
                # 定义代表歌曲真正内容的有效核心结构标签
                valid_labels = {'intro', 'verse', 'chorus', 'bridge', 'theme', 'transition', 'outro'}
                
                # 寻找 AI 认定的真正音乐开始位置（跳过前面的纯静音或 start 空白块）
                for seg in result.segments:
                    if seg.label in valid_labels:
                        music_start = seg.start
                        break
                        
                # 寻找 AI 认定的真正音乐结束位置（裁掉后面的尾部杂音/静音块）
                for seg in reversed(result.segments):
                    if seg.label in valid_labels:
                        music_end = seg.end
                        break
                
                print(f"   🎯 AI 对齐成功！精准定位：核心音乐自 {music_start:.2f}秒 开始，至 {music_end:.2f}秒 结束。")
                
                # 根据 AI 给出的秒数戳裁剪 pydub 对象的音频（毫秒单位）
                precise_chunk = chunk[int(music_start * 1000) : int(music_end * 1000)]
                
                # 5. 导出最终成品
                song_name = f"ai_track_{i+1:02d}.{output_format}"
                output_path = os.path.join(save_dir, song_name)
                
                precise_chunk.export(output_path, format=output_format, bitrate="192k" if output_format=="mp3" else None)
                print(f"   ✅ 精准单曲已保存: {song_name}")
                
            except Exception as ai_err:
                # 强壮的容错机制：如果某首歌 AI 模型分析报错或不适用，直接降级用粗切版本保存，不中断程序
                print(f"   ⚠️ 第 {i+1} 首歌 AI 分析异常 ({str(ai_err)})，已降级使用基础切分版本。")
                song_name = f"fallback_track_{i+1:02d}.{output_format}"
                output_path = os.path.join(save_dir, song_name)
                chunk.export(output_path, format=output_format)
                
            finally:
                # 及时清理粗切的临时单曲文件
                if os.path.exists(temp_chunk_path):
                    os.remove(temp_chunk_path)

        # 6. 彻底清理大录音临时文件
        if os.path.exists(temp_long_wav):
            os.remove(temp_long_wav)

        return True, f"全部切歌完成！共生成 {len(coarse_chunks)} 首 AI 精准单曲，保存在：{save_dir}"

    except Exception as e:
        return False, f"流水线运行失败: {str(e)}"
