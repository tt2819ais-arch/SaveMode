"""Антискам-анализ входящих business-сообщений (best-effort)."""
import re

from bot.utils.constants import SCAM_PATTERNS, SCAM_BOT_PATTERNS

# Подозрительные ссылки
_SUSPICIOUS_LINK_RE = re.compile(
    r"(t\.me/[a-zA-Z0-9_]+\?start=|bit\.ly/|tinyurl\.com/|"
    r"claim|airdrop|free-?stars|free-?premium|wallet-?connect)",
    re.IGNORECASE,
)


def check_scam(text: str, username: str = "") -> tuple[bool, str]:
    """
    Проверить сообщение на признаки скама.
    Возвращает (is_scam, reason).
    Честная эвристика — не 100% защита.
    """
    if not text and not username:
        return False, ""

    low = (text or "").lower()

    # 1. Проверка по скам-паттернам текста
    for pattern in SCAM_PATTERNS:
        if pattern.lower() in low:
            return True, f"Обнаружена подозрительная фраза: «{pattern}»"

    # 2. Проверка username отправителя
    if username:
        uname_low = username.lower()
        for bp in SCAM_BOT_PATTERNS:
            if bp in uname_low:
                return True, f"Подозрительный username бота: @{username}"

    # 3. Проверка подозрительных ссылок
    if text:
        m = _SUSPICIOUS_LINK_RE.search(text)
        if m:
            return True, f"Подозрительная ссылка/паттерн: «{m.group(0)}»"

    # 4. Комбинация «подарок» + «звёзды/stars» + призыв
    if ("подар" in low or "gift" in low) and \
       ("star" in low or "звёзд" in low or "звезд" in low) and \
       ("отправ" in low or "send" in low or "перевед" in low):
        return True, "Возможная схема кражи подарков/звёзд"

    return False, ""
