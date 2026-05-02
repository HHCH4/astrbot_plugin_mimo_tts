import base64
import random
from pathlib import Path

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import EventMessageType
from astrbot.api.message_components import Record
from astrbot.api import logger
from astrbot.core.star.filter.command import GreedyStr
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path

from .mimo_client import MiMoAPIError, MiMoTTSClient

_MODELS = [
    ("mimo-v2.5-tts", "基础 TTS (音色/风格/方言)"),
    ("mimo-v2.5-tts-voicedesign", "音色设计 (自定义音色描述)"),
    ("mimo-v2.5-tts-voiceclone", "音色克隆 (参考音频)"),
]


class Main(star.Star):
    def __init__(self, context: star.Context, config: dict) -> None:
        super().__init__(context, config)
        self.config = config
        self.client = MiMoTTSClient(
            api_key=config.get("api_key", ""),
            api_base=config.get("api_base", "https://api.xiaomimimo.com/v1"),
        )
        self.clone_ref_b64 = self._load_ref_audio(
            config.get("clone_ref_audio", [])
        )

    async def initialize(self) -> None:
        # 校验音色预设：同时只允许一个 active
        self._validate_presets()
        logger.info("MiMo TTS plugin initialized. Model: %s", self.config.get("model", "mimo-v2.5-tts"))

    def _validate_presets(self) -> None:
        presets = self.config.get("voice_design_presets", [])
        if not presets:
            return
        active_indices = [
            i for i, p in enumerate(presets)
            if isinstance(p, dict) and p.get("active")
        ]
        if len(active_indices) > 1:
            # 保留第一个 active，将其余的关闭
            for idx in active_indices[1:]:
                presets[idx]["active"] = False
            logger.warning(
                "MiMo TTS: 检测到多个音色预设同时启用，已自动关闭多余的，仅保留第 %d 个",
                active_indices[0] + 1,
            )

    async def terminate(self) -> None:
        await self.client.close()

    def _load_ref_audio(self, files: list) -> str:
        if not files:
            return ""
        rel_path = files[0]
        full_path = Path(get_astrbot_plugin_data_path()) / self.name / rel_path
        if not full_path.exists():
            logger.warning("MiMo TTS: clone ref audio not found: %s", full_path)
            return ""
        data = full_path.read_bytes()
        if len(data) > 10 * 1024 * 1024:
            logger.warning("MiMo TTS: clone ref audio exceeds 10MB limit")
            return ""
        mime = "audio/wav" if full_path.suffix.lower() == ".wav" else "audio/mpeg"
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    def _get_model(self) -> str:
        return self.config.get("model", "mimo-v2.5-tts")

    def _get_audio_format(self) -> str:
        return self.config.get("audio_format", "wav")

    def _get_voice_desc(self) -> str:
        presets = self.config.get("voice_design_presets", [])
        if not presets:
            return "a young male tone"
        for p in presets:
            if isinstance(p, dict) and p.get("active"):
                return p.get("desc", "a young male tone")
        first = presets[0]
        return first.get("desc", "a young male tone") if isinstance(first, dict) else "a young male tone"

    @filter.command("tts_model")
    @filter.event_message_type(EventMessageType.ALL)
    async def cmd_tts_model(self, event: AstrMessageEvent, index: str = "") -> None:
        index = index.strip()
        current = self._get_model()
        if not index:
            lines = ["当前模型: " + current, "", "可用模型:"]
            for i, (m, desc) in enumerate(_MODELS, 1):
                mark = " ✓" if m == current else ""
                lines.append(f"  {i}. {m} — {desc}{mark}")
            lines.append("")
            lines.append("切换: /tts_model <序号>")
            event.set_result(event.plain_result("\n".join(lines)))
            return

        if not index.isdigit() or int(index) < 1 or int(index) > len(_MODELS):
            event.set_result(event.plain_result(
                f"无效序号: {index}，请输入 1-{len(_MODELS)}"
            ))
            return

        model_name = _MODELS[int(index) - 1][0]
        self.config["model"] = model_name
        event.set_result(event.plain_result(f"TTS 模型已切换为: {model_name}"))

    @filter.command("tts")
    @filter.event_message_type(EventMessageType.ALL)
    async def cmd_tts(self, event: AstrMessageEvent, text: GreedyStr) -> None:
        try:
            audio_path = await self.client.synthesize(
                text=text,
                model=self._get_model(),
                audio_format=self._get_audio_format(),
                voice=self.config.get("voice", "mimo_default"),
                style=self.config.get("style_prompt", ""),
                dialect=self.config.get("dialect", ""),
                voice_desc=self._get_voice_desc(),
                ref_audio_b64=self.clone_ref_b64,
            )
            event.set_result(
                event.chain_result([Record(file=audio_path, url=audio_path)])
            )
        except MiMoAPIError as e:
            logger.error("MiMo TTS error: %s", e)
            event.set_result(event.plain_result(f"TTS 失败: {e}"))
        except Exception as e:
            logger.error("MiMo TTS unexpected error: %s", e)
            event.set_result(event.plain_result(f"TTS 异常: {e}"))

    @filter.on_llm_response()
    async def auto_tts(self, event: AstrMessageEvent, response) -> None:
        weight = float(self.config.get("auto_tts_on_llm", 0.0))
        if weight <= 0:
            return
        if weight < 1 and random.random() > weight:
            return
        if not response.result_chain:
            return

        plain_texts = []
        for comp in response.result_chain.chain:
            if comp.type.value == "Plain" and hasattr(comp, "text") and len(comp.text) > 1:
                plain_texts.append(comp.text)

        if not plain_texts:
            return

        full_text = "\n".join(plain_texts)
        try:
            audio_path = await self.client.synthesize(
                text=full_text,
                model=self._get_model(),
                audio_format=self._get_audio_format(),
                voice=self.config.get("voice", "mimo_default"),
                style=self.config.get("style_prompt", ""),
                dialect=self.config.get("dialect", ""),
                voice_desc=self._get_voice_desc(),
                ref_audio_b64=self.clone_ref_b64,
            )
            if self.config.get("voice_only"):
                response.result_chain.chain = [
                    comp for comp in response.result_chain.chain
                    if comp.type.value != "Plain"
                ]
            response.result_chain.chain.append(
                Record(file=audio_path, url=audio_path, text=full_text)
            )
        except Exception as e:
            logger.error("MiMo auto TTS error: %s", e)
