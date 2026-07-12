"""Построение inline-клавиатур."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.constants import (
    COMMANDS, CATEGORIES, get_commands_by_category, get_command_index,
)


def connection_kb() -> InlineKeyboardMarkup:
    """Кнопка 'Команды и функционал' при подключении."""
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Команды и функционал", callback_data="cmd_menu")
    return kb.as_markup()


def main_menu_kb(is_owner: bool = False) -> InlineKeyboardMarkup:
    """Главное меню категорий."""
    kb = InlineKeyboardBuilder()
    grouped = get_commands_by_category()
    for cat_key, cat_title in CATEGORIES.items():
        count = len(grouped.get(cat_title, []))
        kb.button(text=f"{cat_title} ({count})", callback_data=f"cat:{cat_key}")
    if is_owner:
        kb.button(text="🛠 Админ-панель", callback_data="admin_menu")
    kb.adjust(1)
    return kb.as_markup()


def category_kb(cat_key: str) -> InlineKeyboardMarkup:
    """Список команд в категории."""
    kb = InlineKeyboardBuilder()
    cat_title = CATEGORIES.get(cat_key, "")
    grouped = get_commands_by_category()
    cmds = grouped.get(cat_title, [])
    for cmd in cmds:
        idx = get_command_index(cmd[0])
        kb.button(text=cmd[0], callback_data=f"cmd:{idx}")
    kb.adjust(3)
    kb.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="cmd_home"))
    return kb.as_markup()


def command_detail_kb(index: int) -> InlineKeyboardMarkup:
    """Клавиатура для детального описания команды с зацикленной навигацией."""
    total = len(COMMANDS)
    prev_idx = (index - 1) % total
    next_idx = (index + 1) % total
    cat_key = COMMANDS[index][3]
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"cmd:{prev_idx}"),
        InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="noop"),
        InlineKeyboardButton(text="След. ➡️", callback_data=f"cmd:{next_idx}"),
    )
    kb.row(
        InlineKeyboardButton(text="⬅️ К категории", callback_data=f"cat:{cat_key}"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="cmd_home"),
    )
    return kb.as_markup()


# --- Админ-панель ---
def admin_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Список пользователей", callback_data="admin_users")
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    kb.button(text="📢 Рассылка всем", callback_data="admin_broadcast")
    kb.button(text="✉️ Написать пользователю", callback_data="admin_dm")
    kb.button(text="🏠 Главное меню", callback_data="cmd_home")
    kb.adjust(1)
    return kb.as_markup()


def admin_back_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад в админ-панель", callback_data="admin_menu")
    return kb.as_markup()


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Отправить всем", callback_data="admin_bc_confirm")
    kb.button(text="❌ Отмена", callback_data="admin_menu")
    kb.adjust(1)
    return kb.as_markup()


# --- Игры ---
def game_invite_kb(game_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принять игру", callback_data=f"game_accept:{game_id}")
    kb.button(text="❌ Отменить", callback_data=f"game_cancel:{game_id}")
    kb.adjust(1)
    return kb.as_markup()


def ttt_kb(game_id: str, board: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    symbols = {"": "·", "X": "❌", "O": "⭕"}
    for i in range(9):
        kb.button(text=symbols.get(board[i], "·"),
                  callback_data=f"ttt:{game_id}:{i}")
    kb.adjust(3)
    return kb.as_markup()


def duel_kb(game_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⚔️ Атака", callback_data=f"duel:{game_id}:attack")
    kb.button(text="🛡 Защита", callback_data=f"duel:{game_id}:defend")
    kb.button(text="💨 Уклонение", callback_data=f"duel:{game_id}:dodge")
    kb.adjust(3)
    return kb.as_markup()


def dice_kb(game_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎲 Бросить кубик", callback_data=f"dice:{game_id}:roll")
    return kb.as_markup()


def flip_kb(game_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🦅 Орёл", callback_data=f"flip:{game_id}:heads")
    kb.button(text="🪙 Решка", callback_data=f"flip:{game_id}:tails")
    kb.adjust(2)
    return kb.as_markup()


def bw_kb(game_id: str, board: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    symbols = {0: "⬜", 1: "🟦", 2: "🟥"}
    for i in range(25):
        kb.button(text=symbols.get(board[i], "⬜"),
                  callback_data=f"bw:{game_id}:{i}")
    kb.adjust(5)
    return kb.as_markup()


def fv_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🐿 Бурундук", callback_data="fv:chipmunk")
    kb.button(text="👹 Демон", callback_data="fv:demon")
    kb.button(text="🐌 Медленно", callback_data="fv:slow")
    kb.button(text="⚡ Быстро", callback_data="fv:fast")
    kb.button(text="🌀 Эхо", callback_data="fv:echo")
    kb.button(text="🤖 Робот", callback_data="fv:robot")
    kb.adjust(3)
    return kb.as_markup()
