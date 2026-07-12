"""Игровые команды и логика: .ttt, .duel, .dice, .flip, .bw.

Игры двухпользовательские: один запускает через .команду,
второй жмёт «Принять». Ходы по очереди через inline-кнопки.
Ставки — игровые очки (⭐), НЕ реальные Telegram Stars.
"""
import uuid
import random

from aiogram import Bot
from aiogram.types import Message

from bot import storage
from bot.utils import keyboards
from bot.utils.text_tools import escape

# Ставки на игры (игровые очки)
STAKES = {"ttt": 10, "duel": 15, "dice": 5, "flip": 5, "bw": 10}

GAME_TITLES = {
    "ttt": "❌⭕ Крестики-нолики",
    "duel": "⚔️ Дуэль",
    "dice": "🎲 Кубик",
    "flip": "🪙 Монетка",
    "bw": "🎨 Закрась поле",
}


def _new_game_id() -> str:
    return uuid.uuid4().hex[:12]


def _initial_state(game_type: str) -> dict:
    if game_type == "ttt":
        return {"board": [""] * 9, "turn": "X"}
    if game_type == "bw":
        return {"board": [0] * 25}
    if game_type == "duel":
        return {"hp1": 100, "hp2": 100, "round": 1,
                "action1": None, "action2": None}
    if game_type == "dice":
        return {"roll1": None, "roll2": None}
    if game_type == "flip":
        return {"choice1": None, "result": None}
    return {}


async def start_game(bot: Bot, msg: Message, game_type: str,
                     bc_id: str, player_id: int, player_name: str) -> None:
    """Запустить игру — отправить приглашение."""
    game_id = _new_game_id()
    state = _initial_state(game_type)
    stake = STAKES.get(game_type, 5)
    title = GAME_TITLES.get(game_type, "Игра")

    text = (
        f"{title}\n\n"
        f"👤 Игрок: {escape(player_name)}\n"
        f"⭐ Ставка: {stake} очков (игровые)\n\n"
        f"Второй игрок — нажмите «Принять игру»!"
    )
    sent = await bot.send_message(
        chat_id=msg.chat.id,
        text=text,
        reply_markup=keyboards.game_invite_kb(game_id),
        business_connection_id=bc_id,
    )
    await storage.create_game(
        game_id=game_id, game_type=game_type, chat_id=msg.chat.id,
        bc_id=bc_id, player1_id=player_id, player1_name=player_name,
        state=state, message_id=sent.message_id,
    )


# --- Логика победы для крестики-нолики ---
_WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]


def ttt_winner(board: list) -> str:
    """Вернуть 'X'/'O' если есть победитель, иначе ''."""
    for a, b, c in _WIN_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return ""


def ttt_full(board: list) -> bool:
    return all(cell for cell in board)


# --- Логика дуэли ---
def resolve_duel_round(a1: str, a2: str) -> tuple[int, int, str]:
    """
    Разрешить раунд дуэли.
    Возвращает (урон игроку1, урон игроку2, описание).
    """
    def damage(attacker_action, defender_action):
        if attacker_action != "attack":
            return 0
        base = random.randint(20, 35)
        if defender_action == "defend":
            return int(base * 0.3)
        if defender_action == "dodge":
            return 0 if random.random() < 0.5 else base
        return base

    dmg_to_2 = damage(a1, a2)  # игрок1 атакует игрока2
    dmg_to_1 = damage(a2, a1)  # игрок2 атакует игрока1

    labels = {"attack": "⚔️ Атака", "defend": "🛡 Защита", "dodge": "💨 Уклонение"}
    desc = f"Игрок 1: {labels[a1]} | Игрок 2: {labels[a2]}"
    return dmg_to_1, dmg_to_2, desc
