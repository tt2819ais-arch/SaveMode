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
# Premium-глифы для kawaii-декора (случайный вариант на каждый показ).
_KAWAII_GLYPHS = ["✨", "🌸", "💗", "🎀", "🌟", "🥺", "💕", "🦋", "🌺"]
_KAWAII_FACES = ["(◕‿◕)", "(=^･ω･^=)", "(✿◠‿◠)", "uwu", "owo", "(｡♥‿♥｡)", "ﾉ"]


def kawaii(text: str) -> str:
    """Kawaii-форматирование текста (HTML, с premium-эмодзи).

    Возвращает HTML-строку: текст экранируется, эмодзи — premium <tg-emoji>.
    Отправлять с parse_mode="HTML".
    """
    if not text:
        return text
    from bot.utils.premium_emoji import pe

    def _emo() -> str:
        return pe(random.choice(_KAWAII_GLYPHS))

    words = text.split()
    out = []
    for w in words:
        # мягкая замена r->w для kawaii-эффекта
        w2 = w.replace("r", "w").replace("R", "W")
        out.append(escape(w2))
        if random.random() < 0.4:
            out.append(_emo())
    face = random.choice(_KAWAII_FACES)
    result = " ".join(out)
    result += " " + escape(face) + " " + _emo()
    return result


# --- .love ---
_LOVE_EMOJI = ["💕", "💖", "❤️", "💗", "💓", "💞", "💘", "😍", "🥰"]


def love(text: str) -> str:
    """Оформить текст премиум-сердечками (HTML).

    Каждое слово обрамляется случайным premium-сердечком, поэтому результат
    отправляется с parse_mode="HTML" (см. cmd_love). Текст экранируется.
    """
    if not text:
        return text
    from bot.utils.premium_emoji import pe_random
    words = text.split()
    out = [f"{pe_random('love')}{escape(w)}{pe_random('love')}" for w in words]
    return f"{pe_random('love')} " + " ".join(out) + f" {pe_random('love')}"


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


# --- .short: экстрактивный пересказ ---
import re as _re

_STOPWORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а",
    "то", "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же",
    "вы", "за", "бы", "по", "только", "ее", "мне", "было", "вот", "от",
    "меня", "еще", "нет", "о", "из", "ему", "теперь", "когда", "даже",
    "ну", "вдруг", "ли", "если", "уже", "или", "ни", "быть", "был", "него",
    "до", "вас", "нибудь", "опять", "уж", "вам", "ведь", "там", "потом",
    "себя", "ничего", "ей", "может", "они", "тут", "где", "есть", "надо",
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "is", "are",
    "was", "were", "it", "this", "that", "for", "with", "as", "at", "by",
}


def summarize(text: str, max_sentences: int = 3) -> str:
    """Экстрактивный пересказ: выбрать самые «весомые» предложения.

    Простой частотный алгоритм (без внешних зависимостей): считаем
    частоту значимых слов и выбираем предложения с наибольшим весом,
    сохраняя исходный порядок.
    """
    if not text or not text.strip():
        return ""
    # Разбиваем на предложения
    sentences = _re.split(r"(?<=[.!?…])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= max_sentences:
        return text.strip()

    # Частоты слов
    words = _re.findall(r"\w+", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w in _STOPWORDS or len(w) < 3:
            continue
        freq[w] = freq.get(w, 0) + 1
    if not freq:
        return " ".join(sentences[:max_sentences])
    maxf = max(freq.values())
    for w in freq:
        freq[w] /= maxf  # нормализация

    # Скоринг предложений
    scored = []
    for i, s in enumerate(sentences):
        sw = _re.findall(r"\w+", s.lower())
        if not sw:
            continue
        score = sum(freq.get(w, 0) for w in sw) / (len(sw) ** 0.5)
        scored.append((score, i, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    chosen = sorted(scored[:max_sentences], key=lambda x: x[1])
    return " ".join(s for _, _, s in chosen)
