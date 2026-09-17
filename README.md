# 🎙️ OpenClaw Skill: AI 驱动型系统音频录制与精准分轨工具箱 (Music Toolkit)

这是一个为 [OpenClaw](https://github.com/openclaw/openclaw) 定制的专属高级音频处理 Skill。本插件旨在提供**纯净的电脑系统声音内录（无外环境噪音）**，并在此基础上集成了基于 PyTorch 深度学习模型的 **AI 音乐结构分析与自动分轨**功能。

无论是录制单首流媒体歌曲、切除网课前后的冗余空白，还是挂机录制一整张专辑并让 AI 自动切成独立的单曲，本工具箱都能完美胜任。

---

## ✨ 核心特性

- **🔊 系统无损内录 (Loopback)**：通过虚拟回环麦克风，直接数字级捕获操作系统输出给扬声器的音频信号，彻底杜绝外部麦克风的物理杂音，支持 48kHz 广播级采样率。
- **✂️ 智能静音裁剪 (Auto Trim)**：内置 VAD（语音活动检测）算法，自动检测并切除音频首尾的死寂片段与轻微底噪，精准保留音频主体。
- **🧠 AI 结构级精准分轨 (AI Split)**：引入 `allin1` 深度学习音乐模型，像人类一样“听懂”音乐结构（前奏 Intro、主歌 Verse、副歌 Chorus、尾奏 Outro），剔除不可预知的尾随杂音，实现像素级的单曲对齐与裁剪。
- **🛡️ 金字塔级容错 (Fallback)**：当遇到极端小众音频导致 AI 模型分析异常时，流水线绝不崩溃，而是自动降级为传统的静音切分模式，确保整轨录制任务安全跑完。

---

## 🛠️ 环境依赖

本 Skill 运行时依赖以下 Python 库（代码内部已通过 `ensure_package` 模块动态检查、锁定版本并自动安装）：

- **音频录制与处理**：`soundcard`, `soundfile`, `pydub`
- **AI 引擎与模型**：`torch`, `allin1`, `madmom`, `Cython`, `setuptools<82`
    > *注：为了确保 `madmom` 的 C 扩展组件顺利编译，代码中锁定了 `setuptools<82` 并优化了国内 PyPI 镜像源下载配置。*

### ⚠️ 系统级依赖 (推荐)
- **FFmpeg 核心组件**：
  若你需要将录制和裁剪好的 WAV 无损音频压缩导出为 **MP3 格式**，`pydub` 底层依赖系统的 FFmpeg。请确保你的操作系统已安装 [FFmpeg](https://ffmpeg.org/download.html)，并将其添加到了系统的环境变量（PATH）中。若未安装，程序会自动输出 WAV 格式。

---

## 📖 命令行参数 (CLI Usage)

你可以通过命令行直接调用 `media_grabber.py`（或你的主脚本）来进行录制。以下是最新的参数支持列表：

| 参数 (短) | 参数 (长) | 类型 | 默认值 | 描述 |
| :--- | :--- | :--- | :--- | :--- |
| **`-t`** | **`--duration`** | `float` | `10.0` | **(必填)** 预计录制总时长（单位：分钟）。 |
| **`-ai`** | **`--ai-split`** | `flag` | `False` | 是否开启 AI 多首歌曲整轨录制并自动精准切割模式。 |
| **`-trim`**| **`--auto-trim`** | `flag` | `False` | 是否自动裁剪单曲前后的静音与杂音。 |
| **`-d`** | **`--save-dir`** | `str` | `record` | 最终单曲的输出保存目录。 |
| **`-p`** | **`--filename-prefix`**| `str` | `None` | 自定义导出的文件名前缀或歌曲标题。 |
| **`-sh`** | **`--silence-thresh`** | `int` | `-45` | 静音分贝阈值 (dBFS)，越小判定越严格。 |
| **`-msl`** | **`--min-silence-len`**| `int` | `1000` | 判定为静音的最短持续时间 (毫秒)。 |

---

## 🚀 典型应用场景与终端示例 (Terminal Usage)

### **在 OpenClaw 聊天中**

你可以直接对你的 Agent 说：

    帮我录音 5 分钟

    录制电脑正在播放的声音，录 3 分钟

    录制系统声音 5 分钟

### 1. 基础录音与裁剪
```bash
python scripts/media_grabber.py -t 5 -trim
python scripts/media_grabber.py -t 5 -p "乌兰巴托的夜" -trim 
python scripts/media_grabber.py -t 5 -d "F:/录制音乐" -trim -ai
python scripts/media_grabber.py -t 10 -trim -ai

