"""Транскрибация голосовых (STT) — опционально через OpenAI Whisper API.

Работает ТОЛЬКО если задан OPENAI_API_KEY в окружении. Это честно
опциональная возможность: без ключа .short показывает длительность и
пересказ текстовых сообщений, но не расшифровывает аудио.

Альтернатива без внешних сервисов — локальный openai-whisper или
faster-whisper, но они тяжёлые для телефона/слабого VPS, поэтому вынесены
в опцию, а не в обязательную зависимость.
"""
import logging

import aiohttp

from bot.config import OPENAI_API_KEY

logger = logging.getLogger(__name__)


def stt_available() -> bool:
    return bool(OPENAI_API_KEY)


async def transcribe(audio_bytes: bytes, filename: str = "voice.ogg") -> str | None:
    """Расшифровать аудио через OpenAI Whisper API. None при ошибке/без ключа."""
    if not OPENAI_API_KEY:
        return None
    url = "https://api.openai.com/v1/audio/transcriptions"
    try:
        form = aiohttp.FormData()
        form.add_field("file", audio_bytes, filename=filename,
                       content_type="audio/ogg")
        form.add_field("model", "whisper-1")
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        async with aiohttp.ClientSession() as s:
            async with s.post(url, data=form, headers=headers,
                              timeout=aiohttp.ClientTimeout(total=120)) as r:
                if r.status != 200:
                    body = await r.text()
                    logger.warning("STT API %s: %s", r.status, body[:200])
                    return None
                data = await r.json()
                return data.get("text")
    except Exception as e:
        logger.warning("Ошибка транскрибации: %s", e)
        return None
