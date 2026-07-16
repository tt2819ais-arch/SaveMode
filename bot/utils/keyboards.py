"""Построение inline-клавиатур."""
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.constants import (
    COMMANDS, get_commands_by_category, get_command_index, button_label,
)

# Маркер «сюда нажимать» — зелёный кружок внутри подписи кнопки.
GREEN = "🟢 "


def connection_kb() -> InlineKeyboardMarkup:
    """Кнопка 'Команды и функционал' при подключении."""
    kb = InlineKeyboardBuilder()
    kb.button(text="Команды и функционал", callback_data="cmd_menu")
    return kb.as_markup()


def _command_grid(builder: InlineKeyboardBuilder, active_cmd: str | None):
    """Заполнить builder плиткой кнопок команд (рядами по 3).

    Кнопка активной команды помечается зелёным кружком 🟢 (обновляется
    динамически через edit_message_reply_markup).
    """
    for name, _short, _full, _cat in COMMANDS:
        idx = get_command_index(name)
        label = button_label(name)
        if active_cmd == name:
            label = GREEN + label
        builder.button(text=label, callback_data=f"cmd:{idx}")
    builder.adjust(3)


def main_menu_kb(is_owner: bool = False,
                 active_cmd: str | None = None) -> InlineKeyboardMarkup:
    """Плоское меню-грид всех команд (стиль референса).

    active_cmd — команда, помеченная зелёным маркером 🟢 «сюда нажимать».
    """
    kb = InlineKeyboardBuilder()
    _command_grid(kb, active_cmd)
    tail = InlineKeyboardBuilder()
    if is_owner:
        tail.button(text="Админ-панель", callback_data="admin_menu")
    tail.button(text="‹ Назад", callback_data="cmd_welcome")
    tail.adjust(1)
    kb.attach(tail)
    return kb.as_markup()


# Совместимость: category_kb больше не используется в новом меню, но
# оставлена как тонкая обёртка (плоский грид), чтобы не ломать вызовы.
def category_kb(cat_key: str) -> InlineKeyboardMarkup:  # pragma: no cover
    return main_menu_kb()


def command_detail_kb(index: int) -> InlineKeyboardMarkup:
    """Клавиатура под описанием команды: тот же грид с 🟢 на активной."""
    active = COMMANDS[index][0]
    return main_menu_kb(active_cmd=active)


def onboarding_kb(bot_username: str) -> InlineKeyboardMarkup:
    """Кнопки под /start (как в референсе)."""
    kb = InlineKeyboardBuilder()
    uname = f"@{bot_username}" if bot_username else ""
    if uname:
        kb.row(InlineKeyboardButton(
            text="Скопировать юзернейм",
            copy_text=CopyTextButton(text=uname)))
    kb.row(InlineKeyboardButton(text="💬 Диалоги", callback_data="dialogs"))
    kb.row(InlineKeyboardButton(
        text="📝 Редактирование профиля", callback_data="profile_edit"))
    kb.row(InlineKeyboardButton(
        text="❓ Описание команд", callback_data="cmd_menu"))
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
