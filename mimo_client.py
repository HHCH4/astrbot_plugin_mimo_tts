import base64
import re
import uuid
from pathlib import Path

import httpx

from astrbot.core.utils.astrbot_path import get_astrbot_temp_path


class MiMoAPIError(Exception):
    pass


class MiMoTTSClient:
    def __init__(self, api_key: str, api_base: str, timeout: int = 30) -> None:
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_url(self) -> str:
        if self.api_base.endswith("/chat/completions"):
            return self.api_base
        return self.api_base + "/chat/completions"

    def _build_payload(
        self,
        text: str,
        model: str,
        audio_format: str,
        voice: str = "mimo_default",
        style: str = "",
        dialect: str = "",
        voice_desc: str = "",
        ref_audio_b64: str = "",
    ) -> dict:
        if model == "mimo-v2.5-tts":
            return self._payload_basic_tts(text, audio_format, voice, style, dialect)
        elif model == "mimo-v2.5-tts-voicedesign":
            return self._payload_voice_design(text, audio_format, voice_desc)
        elif model == "mimo-v2.5-tts-voiceclone":
            return self._payload_voice_clone(text, audio_format, ref_audio_b64)
        else:
            raise MiMoAPIError(f"Unknown model: {model}")

    def _payload_basic_tts(
        self, text: str, audio_format: str, voice: str, style: str, dialect: str
    ) -> dict:
        messages: list[dict[str, str]] = []
        # user message: natural language style control (optional)
        if style.strip():
            messages.append({"role": "user", "content": style.strip()})
        # assistant message: (tag)text
        has_tag = bool(re.match(r"^[(\（\[【].+?[)\）\]】]", text))
        if dialect.strip() and not has_tag:
            text = f"({dialect.strip()}){text}"
        messages.append({"role": "assistant", "content": text})
        return {
            "model": "mimo-v2.5-tts",
            "messages": messages,
            "audio": {"format": audio_format, "voice": voice},
        }

    def _payload_voice_design(
        self, text: str, audio_format: str, voice_desc: str
    ) -> dict:
        return {
            "model": "mimo-v2.5-tts-voicedesign",
            "messages": [
                {"role": "user", "content": voice_desc or "a young male tone"},
                {"role": "assistant", "content": text},
            ],
            "audio": {"format": audio_format},
        }

    def _payload_voice_clone(
        self, text: str, audio_format: str, ref_audio_b64: str
    ) -> dict:
        if not ref_audio_b64:
            raise MiMoAPIError(
                "VoiceClone requires reference audio. "
                "Upload an audio file in 'clone_ref_audio' config."
            )
        return {
            "model": "mimo-v2.5-tts-voiceclone",
            "messages": [
                {"role": "user", "content": ""},
                {"role": "assistant", "content": text},
            ],
            "audio": {"format": audio_format, "voice": ref_audio_b64},
        }

    async def synthesize(
        self,
        text: str,
        model: str,
        audio_format: str,
        voice: str = "mimo_default",
        style: str = "",
        dialect: str = "",
        voice_desc: str = "",
        ref_audio_b64: str = "",
    ) -> str:
        payload = self._build_payload(
            text, model, audio_format, voice, style, dialect, voice_desc, ref_audio_b64
        )
        response = await self.client.post(
            self._build_url(),
            headers=self._build_headers(),
            json=payload,
        )
        try:
            response.raise_for_status()
        except Exception as exc:
            error_text = response.text[:1024]
            raise MiMoAPIError(
                f"MiMo TTS API request failed: HTTP {response.status_code}, response: {error_text}"
            ) from exc

        data = response.json()
        choices = data.get("choices") or []
        first_choice = choices[0] if choices else {}
        message = first_choice.get("message", {})
        audio_data = message.get("audio", {}).get("data")
        if not audio_data:
            raise MiMoAPIError(f"MiMo TTS API returned no audio payload: {data}")

        temp_dir = Path(get_astrbot_temp_path())
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_path = temp_dir / f"mimo_tts_{uuid.uuid4().hex[:8]}.{audio_format}"
        output_path.write_bytes(base64.b64decode(audio_data))
        return str(output_path)

    async def close(self) -> None:
        await self.client.aclose()
