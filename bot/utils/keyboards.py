"""Построение inline-клавиатур."""
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.constants import (
    COMMANDS, get_commands_by_category, get_command_index, button_label,
)

# Реальные цвета кнопок Telegram Bot API (поле InlineKeyboardButton.style).
# success = зелёная, primary = синяя, danger = красная.
SUCCESS = "success"   # 🟢 «сюда нажимать» / подтвердить
PRIMARY = "primary"   # 🔵 нейтральная навигация
DANGER = "danger"     # 🔴 отмена / отключить / деструктив


def connection_kb() -> InlineKeyboardMarkup:
    """Кнопка 'Команды и функционал' при подключении (синяя навигация)."""
    kb = InlineKeyboardBuilder()
    kb.button(text="Команды и функционал", callback_data="cmd_menu",
              style=PRIMARY)
    return kb.as_markup()


def _command_grid(builder: InlineKeyboardBuilder, active_cmd: str | None):
    """Заполнить builder плиткой кнопок команд (рядами по 3).

    Кнопка активной команды красится в зелёный (style="success") —
    настоящий цвет фона, «сюда нажимать». Обновляется динамически через
    edit_message_reply_markup. Остальные кнопки — стандартного цвета,
    чтобы был один зелёный акцент, а не «радуга» (UX-совет из статьи).
    """
    for name, _short, _full, _cat in COMMANDS:
        idx = get_command_index(name)
        label = button_label(name)
        style = SUCCESS if active_cmd == name else None
        builder.button(text=label, callback_data=f"cmd:{idx}", style=style)
    builder.adjust(3)


def main_menu_kb(is_owner: bool = False,
                 active_cmd: str | None = None) -> InlineKeyboardMarkup:
    """Плоское меню-грид всех команд (стиль референса).

    active_cmd — команда, покрашенная в зелёный (success) «сюда нажимать».
    Навигация («Назад», «Админ-панель») — синяя (primary).
    """
    kb = InlineKeyboardBuilder()
    _command_grid(kb, active_cmd)
    tail = InlineKeyboardBuilder()
    if is_owner:
        tail.button(text="Админ-панель", callback_data="admin_menu",
                    style=PRIMARY)
    tail.button(text="‹ Назад", callback_data="cmd_welcome", style=PRIMARY)
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
    kb.row(InlineKeyboardButton(text="Диалоги", callback_data="dialogs"))
    kb.row(InlineKeyboardButton(
        text="Редактирование профиля", url="tg://settings/edit"))
    kb.row(InlineKeyboardButton(
        text="Описание команд", callback_data="cmd_menu", style=PRIMARY))
    return kb.as_markup()


# --- Админ-панель ---
def admin_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Список пользователей", callback_data="admin_users")
    kb.button(text="Статистика", callback_data="admin_stats")
    kb.button(text="Рассылка всем", callback_data="admin_broadcast")
    kb.button(text="Написать пользователю", callback_data="admin_dm")
    kb.button(text="Главное меню", callback_data="cmd_home", style=PRIMARY)
    kb.adjust(1)
    return kb.as_markup()


def admin_back_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Назад в админ-панель", callback_data="admin_menu",
              style=PRIMARY)
    return kb.as_markup()


def broadcast_confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Отправить всем", callback_data="admin_bc_confirm",
              style=SUCCESS)
    kb.button(text="Отмена", callback_data="admin_menu", style=DANGER)
    kb.adjust(1)
    return kb.as_markup()


# --- Игры ---
def game_invite_kb(game_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Принять игру", callback_data=f"game_accept:{game_id}",
              style=SUCCESS)
    kb.button(text="Отменить", callback_data=f"game_cancel:{game_id}",
              style=DANGER)
    kb.adjust(1)
    return kb.as_markup()


def ttt_kb(game_id: str, board: list) -> InlineKeyboardMarkup:
    # X = красная (danger), O = синяя (primary), пустая = нейтральная.
    kb = InlineKeyboardBuilder()
    symbols = {"": "·", "X": "X", "O": "O"}
    styles = {"X": DANGER, "O": PRIMARY}
    for i in range(9):
        v = board[i]
        kb.button(text=symbols.get(v, "·"),
                  callback_data=f"ttt:{game_id}:{i}",
                  style=styles.get(v))
    kb.adjust(3)
    return kb.as_markup()


def duel_kb(game_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Атака", callback_data=f"duel:{game_id}:attack")
    kb.button(text="Защита", callback_data=f"duel:{game_id}:defend")
    kb.button(text="Уклонение", callback_data=f"duel:{game_id}:dodge")
    kb.adjust(3)
    return kb.as_markup()


def dice_kb(game_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Бросить кубик", callback_data=f"dice:{game_id}:roll",
              style=SUCCESS)
    return kb.as_markup()


def flip_kb(game_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Орёл", callback_data=f"flip:{game_id}:heads")
    kb.button(text="Решка", callback_data=f"flip:{game_id}:tails")
    kb.adjust(2)
    return kb.as_markup()


def bw_kb(game_id: str, board: list) -> InlineKeyboardMarkup:
    # Клетки красим НАТИВНЫМ style, без эмодзи:
    #   0 = не закрашено → нейтральная (без style)
    #   1 = игрок 1      → синяя (primary)
    #   2 = игрок 2      → красная (danger)
    kb = InlineKeyboardBuilder()
    styles = {1: PRIMARY, 2: DANGER}
    for i in range(25):
        kb.button(text="·", callback_data=f"bw:{game_id}:{i}",
                  style=styles.get(board[i]))
    kb.adjust(5)
    return kb.as_markup()


def fv_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Бурундук", callback_data="fv:chipmunk")
    kb.button(text="Демон", callback_data="fv:demon")
    kb.button(text="Медленно", callback_data="fv:slow")
    kb.button(text="Быстро", callback_data="fv:fast")
    kb.button(text="Эхо", callback_data="fv:echo")
    kb.button(text="Робот", callback_data="fv:robot")
    kb.adjust(3)
    return kb.as_markup()
