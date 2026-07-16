"""Обработчики inline-кнопок: меню, навигация, игры, fv."""
import logging
import random

from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery

from bot import storage
from bot.config import OWNER_ID
from bot.utils import keyboards
from bot.utils.constants import (
    COMMANDS, CONNECTION_TEXT, menu_text, strip_lead_emoji,
)
from bot.utils.text_tools import escape
from bot.handlers import games

logger = logging.getLogger(__name__)
router = Router(name="callbacks")


# ── noop (счётчик) ──
@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


# ── Меню команд (плоский грид, как в референсе) ──
@router.callback_query(F.data == "cmd_menu")
@router.callback_query(F.data == "cmd_home")
async def cb_menu(cb: CallbackQuery):
    is_owner = cb.from_user.id == OWNER_ID
    text = menu_text()
    kb = keyboards.main_menu_kb(is_owner=is_owner)
    try:
        await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()


# ── Назад к приветствию/подключению ──
@router.callback_query(F.data == "cmd_welcome")
async def cb_welcome(cb: CallbackQuery):
    try:
        await cb.message.edit_text(
            CONNECTION_TEXT, reply_markup=keyboards.connection_kb(),
            parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("cmd:"))
async def cb_command_detail(cb: CallbackQuery):
    try:
        idx = int(cb.data.split(":", 1)[1])
    except ValueError:
        await cb.answer("Действие устарело", show_alert=True)
        return
    if not (0 <= idx < len(COMMANDS)):
        await cb.answer("Команда не найдена", show_alert=True)
        return
    name, short, full, cat = COMMANDS[idx]
    # Показываем описание + грид с 🟢 «сюда нажимать» на текущей команде.
    body = strip_lead_emoji(full)
    try:
        await cb.message.edit_text(
            body,
            reply_markup=keyboards.command_detail_kb(idx),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await cb.answer()


# ── Кнопки онбординга ──
@router.callback_query(F.data == "dialogs")
async def cb_dialogs(cb: CallbackQuery):
    if cb.from_user.id != OWNER_ID:
        await cb.answer("Доступно только владельцу.", show_alert=True)
        return
    rows = await storage.get_recent_chats(limit=10)
    if not rows:
        text = ("💬 <b>Диалоги</b>\n\nПока нет сохранённых сообщений. "
                "Подключите бота в Business-режиме — и здесь появятся "
                "чаты, за которыми он следит.")
    else:
        lines = ["💬 <b>Отслеживаемые диалоги</b>\n"]
        for name, cnt in rows:
            lines.append(f"• {escape(name or 'Без имени')} — {cnt} сообщ.")
        text = "\n".join(lines)
    try:
        await cb.message.edit_text(
            text, reply_markup=keyboards.connection_kb(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "profile_edit")
async def cb_profile_edit(cb: CallbackQuery):
    text = (
        "📝 <b>Как подключить бота (редактирование профиля)</b>\n\n"
        "1. Откройте <b>Настройки Telegram</b>.\n"
        "2. Раздел <b>«Telegram для бизнеса»</b> "
        "(Settings → Telegram Business).\n"
        "3. Пункт <b>«Чат-боты»</b> (Chatbots).\n"
        "4. Вставьте скопированный <b>@username</b> бота.\n"
        "5. Дайте все разрешения на работу с сообщениями.\n\n"
        "<i>Нужен Telegram Premium. Прямой ссылки на этот экран Telegram "
        "не предоставляет — поэтому открываем настройки вручную.</i>")
    try:
        await cb.message.edit_text(
            text, reply_markup=keyboards.connection_kb(), parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()


# ── Админ-панель ──
def _require_owner(cb: CallbackQuery) -> bool:
    return cb.from_user.id == OWNER_ID


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(cb: CallbackQuery):
    if not _require_owner(cb):
        await cb.answer("⛔ Доступ только для владельца", show_alert=True)
        return
    try:
        await cb.message.edit_text(
            "🛠 <b>Админ-панель SaveMOD</b>\n\nВыберите действие:",
            reply_markup=keyboards.admin_menu_kb(),
            parse_mode="HTML",
        )
    except Exception:
        await cb.message.answer(
            "🛠 <b>Админ-панель SaveMOD</b>\n\nВыберите действие:",
            reply_markup=keyboards.admin_menu_kb(),
            parse_mode="HTML",
        )
    await cb.answer()


@router.callback_query(F.data == "admin_users")
async def cb_admin_users(cb: CallbackQuery):
    if not _require_owner(cb):
        await cb.answer("⛔ Доступ только для владельца", show_alert=True)
        return
    conns = await storage.list_connections()
    if not conns:
        text = "👥 <b>Пользователи</b>\n\nПока никто не подключил бота."
    else:
        text = f"👥 <b>Подключённые пользователи ({len(conns)})</b>\n\n"
        from datetime import datetime
        for c in conns[:50]:
            status = "🟢" if c["is_enabled"] else "🔴"
            uname = f"@{escape(c['user_username'])}" if c["user_username"] else "—"
            dt = datetime.fromtimestamp(c["date"]).strftime("%d.%m.%Y") \
                if c["date"] else "?"
            text += (f"{status} {escape(c['user_first_name'] or 'Без имени')} "
                     f"({uname})\n   🆔 <code>{c['user_id']}</code> · {dt}\n")
    try:
        await cb.message.edit_text(
            text, reply_markup=keyboards.admin_back_kb(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(cb: CallbackQuery):
    if not _require_owner(cb):
        await cb.answer("⛔ Доступ только для владельца", show_alert=True)
        return
    st = await storage.get_stats()
    text = (
        "📊 <b>Статистика SaveMOD</b>\n\n"
        f"👥 Всего подключений: {st['total_connections']}\n"
        f"🟢 Активных: {st['active_connections']}\n"
        f"🔴 Отключённых: {st['total_connections'] - st['active_connections']}\n"
        f"💾 Сохранено сообщений: {st['stored_messages']}\n"
        f"🎮 Сыграно игр: {st['total_games']}\n"
    )
    try:
        await cb.message.edit_text(
            text, reply_markup=keyboards.admin_back_kb(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(cb: CallbackQuery):
    if not _require_owner(cb):
        await cb.answer("⛔ Доступ только для владельца", show_alert=True)
        return
    from bot.handlers.admin import set_admin_state
    set_admin_state(OWNER_ID, "await_broadcast")
    try:
        await cb.message.edit_text(
            "📢 <b>Рассылка всем пользователям</b>\n\n"
            "Отправьте мне текст сообщения, которое нужно разослать "
            "всем подключённым пользователям.\n\n"
            "Для отмены нажмите «Назад».",
            reply_markup=keyboards.admin_back_kb(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "admin_dm")
async def cb_admin_dm(cb: CallbackQuery):
    if not _require_owner(cb):
        await cb.answer("⛔ Доступ только для владельца", show_alert=True)
        return
    from bot.handlers.admin import set_admin_state
    set_admin_state(OWNER_ID, "await_dm")
    try:
        await cb.message.edit_text(
            "✉️ <b>Сообщение пользователю</b>\n\n"
            "Отправьте в формате:\n"
            "<code>id_или_@username | текст сообщения</code>\n\n"
            "Например:\n"
            "<code>123456789 | Привет!</code>\n"
            "<code>@username | Как дела?</code>\n\n"
            "Для отмены нажмите «Назад».",
            reply_markup=keyboards.admin_back_kb(), parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data == "admin_bc_confirm")
async def cb_admin_bc_confirm(cb: CallbackQuery, bot: Bot):
    if not _require_owner(cb):
        await cb.answer("⛔ Доступ только для владельца", show_alert=True)
        return
    from bot.handlers.admin import do_broadcast, get_pending_broadcast
    text = get_pending_broadcast(OWNER_ID)
    if not text:
        await cb.answer("Нет текста для рассылки", show_alert=True)
        return
    await cb.message.edit_text("📢 Рассылка запущена…")
    sent, failed = await do_broadcast(bot, text)
    await cb.message.answer(
        f"📢 <b>Рассылка завершена</b>\n\n"
        f"✅ Доставлено: {sent}\n"
        f"❌ Не доставлено (блок/ошибка): {failed}",
        reply_markup=keyboards.admin_back_kb(), parse_mode="HTML")
    await cb.answer()


# ── Голосовые эффекты (.fv) ──
@router.callback_query(F.data.startswith("fv:"))
async def cb_fv(cb: CallbackQuery, bot: Bot):
    import io
    from aiogram.types import BufferedInputFile
    from bot.utils.audio import process_voice, ffmpeg_available, EFFECT_NAMES
    from bot.handlers.commands import fv_pending

    effect = cb.data.split(":", 1)[1]
    ename = EFFECT_NAMES.get(effect, effect)
    file_id = fv_pending.get(cb.from_user.id)
    if not file_id:
        await cb.answer(
            "Голосовое не найдено. Ответьте на голосовое командой .fv заново.",
            show_alert=True)
        return
    if not ffmpeg_available():
        await cb.answer(
            "ffmpeg не установлен на сервере — обработка недоступна.",
            show_alert=True)
        return
    await cb.answer(f"Обрабатываю: {ename}…")
    try:
        tf = await bot.get_file(file_id)
        buf = io.BytesIO()
        await bot.download_file(tf.file_path, buf)
        result = await process_voice(buf.getvalue(), effect)
    except Exception as e:
        logger.warning("fv download/process error: %s", e)
        result = None
    if not result:
        await cb.message.answer(
            "🎤 Не удалось обработать голосовое. Попробуйте другой эффект "
            "или другое сообщение.")
        return
    fv_pending.pop(cb.from_user.id, None)
    try:
        await bot.send_voice(
            cb.from_user.id,
            BufferedInputFile(result, "voice.ogg"),
            caption=f"🎤 Голос с эффектом: {ename}")
    except Exception as e:
        logger.warning("fv send_voice error: %s", e)
        await cb.message.answer("🎤 Обработал, но не смог отправить результат.")


# ══════════ WORDLE ══════════

@router.callback_query(F.data.startswith("wordle_giveup:"))
async def cb_wordle_giveup(cb: CallbackQuery, bot: Bot):
    from bot.handlers import wordle
    game_id = cb.data.split(":", 1)[1]
    ok, text = await wordle.give_up(bot, game_id, cb.from_user.id)
    if not ok:
        await cb.answer(text, show_alert=True)
        return
    try:
        g = await storage.get_game(game_id)
        await cb.message.edit_text(
            wordle._board_text(g, "🏳 " + text),
            reply_markup=wordle.board_kb(g), parse_mode="HTML")
    except Exception:
        try:
            await cb.message.answer(text, parse_mode="HTML")
        except Exception:
            pass
    await cb.answer()


@router.callback_query(F.data.startswith("wordle_setup:"))
async def cb_wordle_setup(cb: CallbackQuery):
    # Фолбэк, если deep-link недоступен (нет username у бота).
    await cb.answer(
        "Откройте личку со мной и отправьте команду /start "
        f"wordle_{cb.data.split(':', 1)[1]}, затем загадайте слово.",
        show_alert=True)


# ══════════ ИГРЫ ══════════

@router.callback_query(F.data.startswith("game_cancel:"))
async def cb_game_cancel(cb: CallbackQuery):
    game_id = cb.data.split(":", 1)[1]
    g = await storage.get_game(game_id)
    if not g:
        await cb.answer("Игра не найдена", show_alert=True)
        return
    if cb.from_user.id != g["player1_id"]:
        await cb.answer("Отменить может только создатель игры", show_alert=True)
        return
    await storage.update_game(game_id, status="cancelled")
    try:
        await cb.message.edit_text("❌ Игра отменена.")
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("game_accept:"))
async def cb_game_accept(cb: CallbackQuery, bot: Bot):
    game_id = cb.data.split(":", 1)[1]
    g = await storage.get_game(game_id)
    if not g:
        await cb.answer("Игра не найдена или устарела", show_alert=True)
        return
    if g["status"] != "waiting":
        await cb.answer("Игра уже началась или завершена", show_alert=True)
        return
    if cb.from_user.id == g["player1_id"]:
        await cb.answer("Нельзя играть с самим собой!", show_alert=True)
        return

    p2_name = cb.from_user.first_name or "Игрок 2"
    await storage.update_game(
        game_id, player2_id=cb.from_user.id, player2_name=p2_name,
        status="active", current_turn=g["player1_id"])
    g = await storage.get_game(game_id)
    await _render_game(cb, bot, g, first=True)
    await cb.answer("Игра началась!")


async def _render_game(cb, bot, g, first=False):
    gt = g["game_type"]
    if gt == "ttt":
        await _render_ttt(cb, g)
    elif gt == "bw":
        await _render_bw(cb, g)
    elif gt == "duel":
        await _render_duel(cb, g)
    elif gt == "dice":
        await _render_dice_start(cb, g)
    elif gt == "flip":
        await _render_flip_start(cb, g)


# ── Крестики-нолики ──
async def _render_ttt(cb, g):
    state = g["state"]
    turn_id = g["current_turn"]
    turn_name = g["player1_name"] if turn_id == g["player1_id"] else g["player2_name"]
    sym = "❌" if turn_id == g["player1_id"] else "⭕"
    text = (f"❌⭕ <b>Крестики-нолики</b>\n\n"
            f"❌ {escape(g['player1_name'])}  vs  ⭕ {escape(g['player2_name'])}\n\n"
            f"Ход: {escape(turn_name)} ({sym})")
    try:
        await cb.message.edit_text(
            text, reply_markup=keyboards.ttt_kb(g["game_id"], state["board"]),
            parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("ttt:"))
async def cb_ttt(cb: CallbackQuery):
    _, game_id, cell = cb.data.split(":")
    cell = int(cell)
    g = await storage.get_game(game_id)
    if not g or g["status"] != "active":
        await cb.answer("Игра завершена!", show_alert=True)
        return
    if cb.from_user.id not in (g["player1_id"], g["player2_id"]):
        await cb.answer("Вы не участник этой игры", show_alert=True)
        return
    if cb.from_user.id != g["current_turn"]:
        await cb.answer("Сейчас не ваш ход!", show_alert=True)
        return
    state = g["state"]
    board = state["board"]
    if board[cell]:
        await cb.answer("Клетка занята!", show_alert=True)
        return
    sym = "X" if cb.from_user.id == g["player1_id"] else "O"
    board[cell] = sym

    winner = games.ttt_winner(board)
    if winner:
        wid = g["player1_id"] if winner == "X" else g["player2_id"]
        wname = g["player1_name"] if winner == "X" else g["player2_name"]
        await storage.update_game(game_id, state=state, status="finished")
        await storage.update_score(wid, g["chat_id"], games.STAKES["ttt"])
        try:
            await cb.message.edit_text(
                f"🏆 <b>Победил {escape(wname)}!</b> (+{games.STAKES['ttt']} ⭐)\n\n"
                f"Поле:\n{_ttt_ascii(board)}", parse_mode="HTML")
        except Exception:
            pass
        await cb.answer("Победа!")
        return
    if games.ttt_full(board):
        await storage.update_game(game_id, state=state, status="finished")
        try:
            await cb.message.edit_text("🤝 <b>Ничья!</b>\n\n" + _ttt_ascii(board),
                                       parse_mode="HTML")
        except Exception:
            pass
        await cb.answer("Ничья!")
        return

    next_turn = g["player2_id"] if cb.from_user.id == g["player1_id"] \
        else g["player1_id"]
    await storage.update_game(game_id, state=state, current_turn=next_turn)
    g = await storage.get_game(game_id)
    await _render_ttt(cb, g)
    await cb.answer()


def _ttt_ascii(board):
    sym = {"": "·", "X": "❌", "O": "⭕"}
    rows = []
    for i in range(0, 9, 3):
        rows.append("".join(sym[board[j]] for j in range(i, i + 3)))
    return "\n".join(rows)


# ── Закрась поле ──
async def _render_bw(cb, g):
    state = g["state"]
    turn_id = g["current_turn"]
    turn_name = g["player1_name"] if turn_id == g["player1_id"] else g["player2_name"]
    color = "🟦" if turn_id == g["player1_id"] else "🟥"
    c1 = state["board"].count(1)
    c2 = state["board"].count(2)
    text = (f"🎨 <b>Закрась поле</b>\n\n"
            f"🟦 {escape(g['player1_name'])}: {c1}  |  "
            f"🟥 {escape(g['player2_name'])}: {c2}\n\n"
            f"Ход: {escape(turn_name)} ({color})")
    try:
        await cb.message.edit_text(
            text, reply_markup=keyboards.bw_kb(g["game_id"], state["board"]),
            parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("bw:"))
async def cb_bw(cb: CallbackQuery):
    _, game_id, cell = cb.data.split(":")
    cell = int(cell)
    g = await storage.get_game(game_id)
    if not g or g["status"] != "active":
        await cb.answer("Игра завершена!", show_alert=True)
        return
    if cb.from_user.id not in (g["player1_id"], g["player2_id"]):
        await cb.answer("Вы не участник этой игры", show_alert=True)
        return
    if cb.from_user.id != g["current_turn"]:
        await cb.answer("Сейчас не ваш ход!", show_alert=True)
        return
    state = g["state"]
    board = state["board"]
    if board[cell]:
        await cb.answer("Клетка занята!", show_alert=True)
        return
    val = 1 if cb.from_user.id == g["player1_id"] else 2
    board[cell] = val

    if all(board):
        c1 = board.count(1)
        c2 = board.count(2)
        if c1 > c2:
            wname, wid = g["player1_name"], g["player1_id"]
        elif c2 > c1:
            wname, wid = g["player2_name"], g["player2_id"]
        else:
            wname, wid = None, None
        await storage.update_game(game_id, state=state, status="finished")
        if wid:
            await storage.update_score(wid, g["chat_id"], games.STAKES["bw"])
            res = f"🏆 Победил {escape(wname)}! (+{games.STAKES['bw']} ⭐)"
        else:
            res = "🤝 Ничья!"
        try:
            await cb.message.edit_text(
                f"🎨 <b>Игра окончена</b>\n\n"
                f"🟦 {c1}  |  🟥 {c2}\n\n{res}", parse_mode="HTML")
        except Exception:
            pass
        await cb.answer()
        return

    next_turn = g["player2_id"] if cb.from_user.id == g["player1_id"] \
        else g["player1_id"]
    await storage.update_game(game_id, state=state, current_turn=next_turn)
    g = await storage.get_game(game_id)
    await _render_bw(cb, g)
    await cb.answer()


# ── Дуэль ──
async def _render_duel(cb, g):
    state = g["state"]
    text = (f"⚔️ <b>Дуэль</b> — Раунд {state['round']}\n\n"
            f"❤️ {escape(g['player1_name'])}: {state['hp1']} HP\n"
            f"❤️ {escape(g['player2_name'])}: {state['hp2']} HP\n\n"
            "Оба игрока выбирают действие:")
    try:
        await cb.message.edit_text(
            text, reply_markup=keyboards.duel_kb(g["game_id"]), parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("duel:"))
async def cb_duel(cb: CallbackQuery):
    _, game_id, action = cb.data.split(":")
    g = await storage.get_game(game_id)
    if not g or g["status"] != "active":
        await cb.answer("Игра завершена!", show_alert=True)
        return
    uid = cb.from_user.id
    if uid not in (g["player1_id"], g["player2_id"]):
        await cb.answer("Вы не участник этой игры", show_alert=True)
        return
    state = g["state"]
    is_p1 = uid == g["player1_id"]
    if is_p1 and state.get("action1"):
        await cb.answer("Вы уже выбрали, ждём соперника", show_alert=True)
        return
    if not is_p1 and state.get("action2"):
        await cb.answer("Вы уже выбрали, ждём соперника", show_alert=True)
        return
    if is_p1:
        state["action1"] = action
    else:
        state["action2"] = action

    if state["action1"] and state["action2"]:
        d1, d2, desc = games.resolve_duel_round(
            state["action1"], state["action2"])
        state["hp1"] = max(0, state["hp1"] - d1)
        state["hp2"] = max(0, state["hp2"] - d2)
        state["action1"] = None
        state["action2"] = None
        state["round"] += 1

        if state["hp1"] <= 0 or state["hp2"] <= 0:
            if state["hp1"] <= 0 and state["hp2"] <= 0:
                res = "🤝 Оба пали — ничья!"
                wid = None
            elif state["hp2"] <= 0:
                res = f"🏆 Победил {escape(g['player1_name'])}!"
                wid = g["player1_id"]
            else:
                res = f"🏆 Победил {escape(g['player2_name'])}!"
                wid = g["player2_id"]
            await storage.update_game(game_id, state=state, status="finished")
            if wid:
                await storage.update_score(wid, g["chat_id"], games.STAKES["duel"])
                res += f" (+{games.STAKES['duel']} ⭐)"
            try:
                await cb.message.edit_text(
                    f"⚔️ <b>Дуэль окончена</b>\n\n{escape(desc)}\n\n{res}",
                    parse_mode="HTML")
            except Exception:
                pass
            await cb.answer()
            return
        await storage.update_game(game_id, state=state)
        g = await storage.get_game(game_id)
        await _render_duel(cb, g)
        await cb.answer(f"Раунд разрешён! {desc}")
    else:
        await storage.update_game(game_id, state=state)
        await cb.answer("Выбор принят, ждём соперника…")


# ── Кубик ──
async def _render_dice_start(cb, g):
    text = (f"🎲 <b>Кубик</b>\n\n"
            f"{escape(g['player1_name'])} vs {escape(g['player2_name'])}\n\n"
            "Оба нажмите «Бросить кубик»!")
    try:
        await cb.message.edit_text(
            text, reply_markup=keyboards.dice_kb(g["game_id"]), parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("dice:"))
async def cb_dice(cb: CallbackQuery):
    _, game_id, _action = cb.data.split(":")
    g = await storage.get_game(game_id)
    if not g or g["status"] != "active":
        await cb.answer("Игра завершена!", show_alert=True)
        return
    uid = cb.from_user.id
    if uid not in (g["player1_id"], g["player2_id"]):
        await cb.answer("Вы не участник этой игры", show_alert=True)
        return
    state = g["state"]
    is_p1 = uid == g["player1_id"]
    if is_p1 and state.get("roll1") is not None:
        await cb.answer("Вы уже бросили!", show_alert=True)
        return
    if not is_p1 and state.get("roll2") is not None:
        await cb.answer("Вы уже бросили!", show_alert=True)
        return
    roll = random.randint(1, 6)
    if is_p1:
        state["roll1"] = roll
    else:
        state["roll2"] = roll
    await cb.answer(f"Вам выпало: {roll}")

    if state["roll1"] is not None and state["roll2"] is not None:
        r1, r2 = state["roll1"], state["roll2"]
        if r1 > r2:
            wname, wid = g["player1_name"], g["player1_id"]
        elif r2 > r1:
            wname, wid = g["player2_name"], g["player2_id"]
        else:
            wname, wid = None, None
        await storage.update_game(game_id, state=state, status="finished")
        if wid:
            await storage.update_score(wid, g["chat_id"], games.STAKES["dice"])
            res = f"🏆 Победил {escape(wname)}! (+{games.STAKES['dice']} ⭐)"
        else:
            res = "🤝 Ничья!"
        try:
            await cb.message.edit_text(
                f"🎲 <b>Результат</b>\n\n"
                f"{escape(g['player1_name'])}: 🎲 {r1}\n"
                f"{escape(g['player2_name'])}: 🎲 {r2}\n\n{res}",
                parse_mode="HTML")
        except Exception:
            pass
    else:
        await storage.update_game(game_id, state=state)


# ── Монетка ──
async def _render_flip_start(cb, g):
    text = (f"🪙 <b>Монетка</b>\n\n"
            f"{escape(g['player1_name'])}, выберите сторону:")
    try:
        await cb.message.edit_text(
            text, reply_markup=keyboards.flip_kb(g["game_id"]), parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("flip:"))
async def cb_flip(cb: CallbackQuery):
    _, game_id, choice = cb.data.split(":")
    g = await storage.get_game(game_id)
    if not g or g["status"] != "active":
        await cb.answer("Игра завершена!", show_alert=True)
        return
    if cb.from_user.id != g["player1_id"]:
        await cb.answer("Сторону выбирает создатель игры", show_alert=True)
        return
    result = random.choice(["heads", "tails"])
    names = {"heads": "🦅 Орёл", "tails": "🪙 Решка"}
    if choice == result:
        wname, wid = g["player1_name"], g["player1_id"]
    else:
        wname, wid = g["player2_name"], g["player2_id"]
    await storage.update_game(game_id, status="finished")
    await storage.update_score(wid, g["chat_id"], games.STAKES["flip"])
    try:
        await cb.message.edit_text(
            f"🪙 <b>Результат</b>\n\n"
            f"Выпало: {names[result]}\n\n"
            f"🏆 Победил {escape(wname)}! (+{games.STAKES['flip']} ⭐)",
            parse_mode="HTML")
    except Exception:
        pass
    await cb.answer()
