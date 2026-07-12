"""Текстовые утилиты: смена раскладки, kawaii, love, экранирование."""
import html
import random

from bot.utils.constants import EN_LAYOUT, RU_LAYOUT


def escape(text: str) -> str:
    """Экранировать HTML-спецсимволы для parse_mode=HTML."""
    return html.escape(text or "")


# --- .sw: смена раскладки ---
_EN2RU = {e: r for e, r in zip(EN_LAYOUT, RU_LAYOUT)}
_RU2EN = {r: e for e, r in zip(EN_LAYOUT, RU_LAYOUT)}


def switch_layout(text: str) -> str:
    """Определить раскладку и сконвертировать RU<->EN."""
    if not text:
        return text
    en_count = sum(1 for c in text if c in _EN2RU)
    ru_count = sum(1 for c in text if c in _RU2EN)
    if en_count >= ru_count:
        # текст набран в EN -> нужен RU
        return "".join(_EN2RU.get(c, c) for c in text)
    else:
        return "".join(_RU2EN.get(c, c) for c in text)


# --- .kawaii ---
_KAWAII_EMOJI = ["✨", "🌸", "💖", "🎀", "💫", "🌟", "🥺", "💕", "🌈", "🍡"]
_KAWAII_FACES = ["(◕‿◕)", "(=^･ω･^=)", "(✿◠‿◠)", "uwu", "owo", "(｡♥‿♥｡)", "ﾉ"]
_KAWAII_MAP = {
    "р": "ｒ", "л": "ｌ", "o": "ㅇ", "l": "ｌ", "r": "ｗ",
}


def kawaii(text: str) -> str:
    """Kawaii-форматирование текста."""
    if not text:
        return text
    words = text.split()
    out = []
    for w in words:
        # мягкая замена r->w для kawaii-эффекта
        w2 = w.replace("r", "w").replace("R", "W")
        out.append(w2)
        if random.random() < 0.4:
            out.append(random.choice(_KAWAII_EMOJI))
    result = " ".join(out)
    result += " " + random.choice(_KAWAII_FACES) + " " + random.choice(_KAWAII_EMOJI)
    return result


# --- .love ---
_LOVE_EMOJI = ["💕", "💖", "❤️", "💗", "💓", "💞", "💘", "😍", "🥰"]


def love(text: str) -> str:
    """Оформить текст сердечками."""
    if not text:
        return text
    words = text.split()
    hearts = "💕"
    out = [f"{hearts}{w}{hearts}" for w in words]
    return f"{random.choice(_LOVE_EMOJI)} " + " ".join(out) + \
           f" {random.choice(_LOVE_EMOJI)}"


# --- Форматирование имени пользователя ---
def format_user(first_name: str, username: str) -> str:
    """Имя (@username) — экранированное."""
    name = escape(first_name or "Пользователь")
    if username:
        return f"{name} (@{escape(username)})"
    return name


def blockquote(text: str) -> str:
    """Обернуть текст в Telegram blockquote."""
    return f"<blockquote>{escape(text)}</blockquote>"
