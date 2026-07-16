"""Админ-панель владельца: /admin, /start, рассылка, DM пользователю.

Все админ-функции строго ограничены OWNER_ID (server-side проверка).
"""
import asyncio
import logging

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message

from bot import storage
from bot.config import OWNER_ID
from bot.utils import keyboards
from bot.utils.text_tools import escape

logger = logging.getLogger(__name__)
router = Router(name="admin")

# Простое состояние админа в памяти: {owner_id: state}
_admin_state: dict = {}
# Отложенный текст рассылки: {owner_id: text}
_pending_broadcast: dict = {}


def set_admin_state(owner_id: int, state: str | None):
    if state is None:
        _admin_state.pop(owner_id, None)
    else:
        _admin_state[owner_id] = state


def get_admin_state(owner_id: int) -> str | None:
    return _admin_state.get(owner_id)


def get_pending_broadcast(owner_id: int) -> str | None:
    return _pending_broadcast.get(owner_id)


async def do_broadcast(bot: Bot, text: str) -> tuple[int, int]:
    """Разослать текст всем подключённым пользователям."""
    conns = await storage.list_connections()
    seen = set()
    sent = failed = 0
    for c in conns:
        uid = c["user_id"]
        if uid in seen:
            continue
        seen.add(uid)
        try:
            await bot.send_message(
                uid,
                f"📢 <b>Сообщение от администратора SaveMOD</b>\n\n{escape(text)}",
                parse_mode="HTML")
            sent += 1
        except Exception as e:
            logger.info("Broadcast не доставлен %s: %s", uid, e)
            failed += 1
        await asyncio.sleep(0.05)  # мягкий rate-limit
    _pending_broadcast.pop(OWNER_ID, None)
    return sent, failed


# ── /start ──
@router.message(Command("start"))
async def cmd_start(msg: Message, bot: Bot):
    # Deep-link для Wordle: /start wordle_<game_id>
    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("wordle_"):
        from bot.handlers import wordle
        await wordle.handle_start_deeplink(bot, msg, parts[1])
        return

    from bot.utils.constants import ONBOARDING_TEXT
    try:
        me = await bot.get_me()
        uname = me.username or ""
    except Exception:
        uname = ""
    await msg.answer(
        ONBOARDING_TEXT, reply_markup=keyboards.onboarding_kb(uname),
        parse_mode="HTML")


# ── /admin ──
@router.message(Command("admin"))
async def cmd_admin(msg: Message):
    if msg.from_user.id != OWNER_ID:
        await msg.answer("⛔ Эта команда доступна только владельцу бота.")
        return
    await msg.answer(
        "🛠 <b>Админ-панель SaveMOD</b>\n\nВыберите действие:",
        reply_markup=keyboards.admin_menu_kb(), parse_mode="HTML")


# ── /help ──
@router.message(Command("help"))
async def cmd_help_slash(msg: Message):
    from bot.utils.constants import menu_text
    is_owner = msg.from_user.id == OWNER_ID
    await msg.answer(
        menu_text(),
        reply_markup=keyboards.main_menu_kb(is_owner=is_owner),
        parse_mode="HTML")


# ── Точка-команды в ЛИЧКЕ бота (тест-режим без Business Mode) ──
# Регистрируется РАНЬШЕ общего перехватчика текста ниже.
@router.message(F.chat.type == "private", F.text.startswith("."))
async def on_private_dot_command(msg: Message, bot: Bot):
    from bot.handlers import commands as cmd_handlers
    # bc_id=None → тест-режим: результат отправляется обычным сообщением.
    await cmd_handlers.dispatch_command(bot, msg, None, msg.from_user.id)


@router.message(F.chat.type == "private", F.caption.startswith("."))
async def on_private_dot_caption(msg: Message, bot: Bot):
    from bot.handlers import commands as cmd_handlers
    await cmd_handlers.dispatch_command(bot, msg, None, msg.from_user.id)


# ── Wordle: приём секретного слова в личке (любой игрок) ──
# Точные фильтры срабатывают только когда игрок реально в контексте Wordle,
# поэтому обычные сообщения владельца (рассылка/DM) не перехватываются.
from bot.handlers import wordle as _wordle


@router.message(F.chat.type == "private", _wordle.is_setting_word)
async def on_wordle_set_word(msg: Message, bot: Bot):
    await _wordle.set_secret_word(bot, msg)


@router.message(_wordle.is_guess_context)
async def on_wordle_guess(msg: Message, bot: Bot):
    name = (msg.from_user.first_name if msg.from_user else "Игрок") or "Игрок"
    await _wordle.handle_guess(
        bot, msg, None, msg.from_user.id, name)


# ── Приём текста для рассылки / DM (только владелец, в личке бота) ──
@router.message(F.chat.type == "private", F.text)
async def on_owner_private_text(msg: Message, bot: Bot):
    if msg.from_user.id != OWNER_ID:
        return
    state = get_admin_state(OWNER_ID)
    if state == "await_broadcast":
        _pending_broadcast[OWNER_ID] = msg.text
        set_admin_state(OWNER_ID, None)
        preview = msg.text[:300]
        await msg.answer(
            "📢 <b>Подтвердите рассылку</b>\n\n"
            f"Текст:\n{escape(preview)}\n\n"
            "Отправить всем подключённым пользователям?",
            reply_markup=keyboards.broadcast_confirm_kb(), parse_mode="HTML")
        return
    if state == "await_dm":
        set_admin_state(OWNER_ID, None)
        if "|" not in msg.text:
            await msg.answer(
                "❌ Неверный формат. Используйте:\n"
                "<code>id_или_@username | текст</code>",
                reply_markup=keyboards.admin_back_kb(), parse_mode="HTML")
            return
        target_raw, text = msg.text.split("|", 1)
        target_raw = target_raw.strip()
        text = text.strip()
        # Найти пользователя
        conn = None
        if target_raw.startswith("@"):
            conn = await storage.get_connection_by_username(target_raw)
            target_id = conn["user_id"] if conn else None
        elif target_raw.isdigit():
            target_id = int(target_raw)
            conn = await storage.get_connection_by_user(target_id)
        else:
            target_id = None
        if not target_id:
            await msg.answer(
                "❌ Пользователь не найден среди подключённых.",
                reply_markup=keyboards.admin_back_kb())
            return
        try:
            await bot.send_message(
                target_id,
                f"✉️ <b>Сообщение от администратора SaveMOD</b>\n\n{escape(text)}",
                parse_mode="HTML")
            await msg.answer(
                f"✅ Сообщение отправлено пользователю <code>{target_id}</code>.",
                reply_markup=keyboards.admin_back_kb(), parse_mode="HTML")
        except Exception as e:
            await msg.answer(
                f"❌ Не удалось отправить: {escape(str(e))}\n"
                "(возможно, пользователь заблокировал бота)",
                reply_markup=keyboards.admin_back_kb(), parse_mode="HTML")
        return
