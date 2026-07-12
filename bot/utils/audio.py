"""Обработка аудио через ffmpeg: голосовые эффекты для .fv.

Голосовые Telegram — OGG/Opus. Обрабатываем через ffmpeg и отдаём
обратно в OGG/Opus, чтобы получилось валидное voice-сообщение.
Требуется установленный ffmpeg (в Dockerfile ставится автоматически;
в Termux: pkg install ffmpeg).
"""
import asyncio
import logging
import os
import shutil
import tempfile

logger = logging.getLogger(__name__)

# Аудио-фильтры ffmpeg для каждого эффекта.
# asetrate меняет высоту тона (pitch), atempo компенсирует/меняет темп.
EFFECTS: dict[str, str] = {
    # Высокий «мультяшный» голос (бурундук) — вверх по тону, темп сохранён
    "chipmunk": "asetrate=48000*1.4,aresample=48000,atempo=0.72",
    # Низкий «демонический» голос — вниз по тону
    "demon": "asetrate=48000*0.72,aresample=48000,atempo=1.38",
    # Замедление
    "slow": "atempo=0.72",
    # Ускорение
    "fast": "atempo=1.5",
    # Эхо
    "echo": "aecho=0.8:0.88:60:0.4",
    # Металлический «робот»
    "robot": ("afftfilt=real='hypot(re,im)*sin(0)':"
              "imag='hypot(re,im)*cos(0)':win_size=512:overlap=0.75"),
}

EFFECT_NAMES: dict[str, str] = {
    "chipmunk": "🐿 Бурундук",
    "demon": "👹 Демон",
    "slow": "🐌 Медленно",
    "fast": "⚡ Быстро",
    "echo": "🌀 Эхо",
    "robot": "🤖 Робот",
}


def ffmpeg_available() -> bool:
    """Проверить, установлен ли ffmpeg."""
    return shutil.which("ffmpeg") is not None


async def process_voice(input_bytes: bytes, effect: str) -> bytes | None:
    """
    Применить голосовой эффект к OGG/Opus-байтам.
    Возвращает обработанные OGG/Opus-байты или None при ошибке.
    """
    af = EFFECTS.get(effect)
    if not af:
        logger.warning("Неизвестный эффект: %s", effect)
        return None
    if not ffmpeg_available():
        logger.warning("ffmpeg не найден в системе")
        return None

    in_path = out_path = None
    try:
        with tempfile.NamedTemporaryFile(
                suffix=".ogg", delete=False) as fin:
            fin.write(input_bytes)
            in_path = fin.name
        out_path = in_path + ".out.ogg"

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", in_path,
            "-af", af,
            "-c:a", "libopus", "-b:a", "32k",
            out_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            logger.warning("ffmpeg вернул код %s: %s",
                           proc.returncode,
                           (stderr or b"").decode("utf-8", "replace")[:300])
            return None
        with open(out_path, "rb") as f:
            return f.read()
    except asyncio.TimeoutError:
        logger.warning("ffmpeg превысил таймаут обработки")
        return None
    except Exception as e:
        logger.warning("Ошибка обработки голоса: %s", e)
        return None
    finally:
        for p in (in_path, out_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
