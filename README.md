# astrbot_plugin_mimo_tts

接入小米 MiMo V2.5 TTS 系列模型的 AstrBot 插件，支持基础 TTS、音色设计、音色克隆三种模式。

## 支持平台

- OneBot v11 (aiocqhttp)

## 支持模型

| 模型 | 说明 |
|------|------|
| `mimo-v2.5-tts` | 基础 TTS，支持音色选择、风格指令、方言/风格标签 |
| `mimo-v2.5-tts-voicedesign` | 音色设计，通过自然语言描述自定义音色 |
| `mimo-v2.5-tts-voiceclone` | 音色克隆，上传参考音频克隆音色 |

## 指令

| 指令 | 说明 |
|------|------|
| `/tts <文本>` | 将文本合成为语音消息发送 |
| `/tts_model` | 查看当前模型和可用模型列表 |
| `/tts_model <序号>` | 切换 TTS 模型 (1/2/3) |

## 配置说明

### 基础配置

| 配置项 | 说明 |
|--------|------|
| `api_key` | MiMo 平台 API Key (必填) |
| `api_base` | API 地址，默认 `https://api.xiaomimimo.com/v1` |
| `model` | TTS 模型，默认 `mimo-v2.5-tts` |
| `audio_format` | 音频格式，支持 `wav` / `mp3` |

### 基础 TTS 配置 (mimo-v2.5-tts)

| 配置项 | 说明 |
|--------|------|
| `voice` | 音色名称，默认 `mimo_default` |
| `style_prompt` | 风格指令，自然语言控制语音风格 (user message) |
| `dialect` | 方言/风格标签，如 `东北话`、`开心` |

### 音色设计配置 (mimo-v2.5-tts-voicedesign)

| 配置项 | 说明 |
|--------|------|
| `voice_design_presets` | 音色描述预设列表，可添加多个预设，同时只启用一个 |

每个预设包含：
- **预设名称**: 用于标识的名称
- **音色描述**: 自然语言描述音色特征，如 `a young male tone`
- **启用**: 勾选启用该预设 (同时只生效一个)

### 音色克隆配置 (mimo-v2.5-tts-voiceclone)

| 配置项 | 说明 |
|--------|------|
| `clone_ref_audio` | 上传参考音频文件 (支持 mp3/wav，最大 10MB) |

### 自动语音配置

| 配置项 | 说明 |
|--------|------|
| `auto_tts_on_llm` | LLM 回复自动转语音的概率 (0=关闭, 1=全部, 0.5=约一半) |
| `voice_only` | 开启后自动语音时只发送语音，去掉文本 |

## 使用示例

```
# 基础文本转语音
/tts 你好，今天天气怎么样？

# 查看可用模型
/tts_model

# 切换到音色设计模型
/tts_model 2

# 切换到音色克隆模型
/tts_model 3
```

## 依赖

- `httpx`
