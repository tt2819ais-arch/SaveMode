"""Игра .wordle (Вордли) — угадай слово из 5 букв.

Модель игры (ПО УМОЛЧАНИЮ):
  • Игрок, набравший .wordle в чате, — «загадывающий». Он жмёт инлайн-кнопку
    с deep-link (t.me/<bot>?start=wordle_<id>), открывает ЛИЧКУ с ботом и
    в личке ЗАГАДЫВАЕТ секретное слово из 5 букв (так слово скрыто от соперника).
  • После этого игра активируется в исходном чате, и УГАДЫВАЕТ второй участник
    чата: он просто пишет слова из 5 букв прямо в чат.
  • В Business-чате угадывает собеседник владельца (его сообщения приходят как
    business_message). В обычной личке с ботом (тест-режим) загадывающий может
    угадывать сам — удобно для проверки в одиночку.

Обратная связь по буквам (как в Wordle, с корректной обработкой повторов):
  🟩 буква на своём месте · 🟨 буква есть, но не там · ⬜ буквы нет в слове.

Про цвет кнопок: Telegram Bot API поддерживает поле InlineKeyboardButton.style
(success=зелёная, primary=синяя, danger=красная). Клетки доски раскрашиваем
САМИ КНОПКИ, а не эмодзи-квадраты в тексте:
  • буква на своём месте → style=success (зелёная кнопка), текст = буква;
  • буквы нет в слове    → без style (серая кнопка), текст = буква;
  • буква есть, но не там → жёлтого style в API НЕТ, поэтому это ЕДИНСТВЕННЫЙ
    оставшийся эмодзи-фолбэк: 🟨 рядом с буквой.
Служебная кнопка «Сдаться» — style=danger (красная).
"""
import logging
import uuid
from collections import Counter

from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot import storage
from bot.utils.text_tools import escape

logger = logging.getLogger(__name__)

WORD_LEN = 5
MAX_ATTEMPTS = 6

SQUARE = {"green": "🟩", "yellow": "🟨", "grey": "⬜"}

# Быстрые in-memory индексы (для точных фильтров без обращения к БД):
_awaiting_word: dict[int, str] = {}   # user_id (в личке) -> game_id
_active_chats: dict[int, str] = {}    # chat_id (где угадывают) -> game_id


# ─────────────────────────── ЧИСТАЯ ЛОГИКА ───────────────────────────

def score_guess(secret: str, guess: str) -> list[str]:
    """Оценить догадку по правилам Wordle с корректной обработкой повторов.

    Возвращает список меток длиной len(secret): 'green'/'yellow'/'grey'.
    """
    secret = secret.upper()
    guess = guess.upper()
    n = len(secret)
    result = ["grey"] * len(guess)
    counts = Counter(secret)
    # Первый проход — точные попадания (зелёные).
    for i in range(min(n, len(guess))):
        if guess[i] == secret[i]:
            result[i] = "green"
            counts[guess[i]] -= 1
    # Второй проход — буква есть, но не на месте (жёлтые), с учётом остатка.
    for i in range(len(guess)):
        if result[i] == "green":
            continue
        ch = guess[i]
        if counts.get(ch, 0) > 0:
            result[i] = "yellow"
            counts[ch] -= 1
    return result


def is_win(marks: list[str]) -> bool:
    return bool(marks) and all(m == "green" for m in marks)


def normalize_word(text: str) -> str:
    return (text or "").strip().replace("ё", "е").replace("Ё", "Е").upper()


def validate_word(text: str) -> tuple[bool, str, str]:
    """Проверить слово. Возвращает (ok, normalized, error_ru)."""
    w = (text or "").strip()
    if " " in w:
        return False, "", "Слово должно быть без пробелов."
    if len(w) != WORD_LEN:
        return False, "", f"Нужно ровно {WORD_LEN} букв (у вас {len(w)})."
    # Только буквы (RU или EN), допускаем ё.
    if not all(("A" <= c.upper() <= "Z") or ("А" <= c.upper() <= "Я")
               or c.upper() == "Ё" for c in w):
        return False, "", "Только буквы (русские или английские), без цифр и символов."
    # Один алфавит (не мешать раскладки).
    has_ru = any(("А" <= c.upper() <= "Я") or c.upper() == "Ё" for c in w)
    has_en = any("A" <= c.upper() <= "Z" for c in w)
    if has_ru and has_en:
        return False, "", "Не смешивайте русские и английские буквы в одном слове."
    return True, normalize_word(w), ""


def _looks_like_guess(text: str) -> bool:
    """Быстрая проверка формата догадки для фильтра (без строгой валидации)."""
    ok, _, _ = validate_word(text)
    return ok


# ─────────────────────────── ФИЛЬТРЫ ───────────────────────────

def is_setting_word(msg: Message) -> bool:
    return bool(msg.from_user) and msg.from_user.id in _awaiting_word


def is_guess_context(msg: Message) -> bool:
    return (msg.chat.id in _active_chats and bool(msg.text)
            and _looks_like_guess(msg.text))


# ─────────────────────────── РЕНДЕР ДОСКИ ───────────────────────────

def _cell(ch: str, mark: str) -> InlineKeyboardButton:
    """Клетка доски. Цвет несёт САМА кнопка через style:
      green → style=success (зелёная), текст = буква;
      grey  → без style (серая по умолчанию), текст = буква;
      yellow → жёлтого style в API НЕТ, поэтому единственный эмодзи-фолбэк 🟨.
    """
    if mark == "green":
        return InlineKeyboardButton(text=ch, callback_data="noop",
                                    style="success")
    if mark == "yellow":
        return InlineKeyboardButton(text=f"{ch}🟨", callback_data="noop")
    return InlineKeyboardButton(text=ch, callback_data="noop")


def board_kb(game: dict) -> InlineKeyboardMarkup:
    """Доска как ряды инлайн-кнопок; цвет клетки = цвет кнопки (style)."""
    st = game["state"]
    guesses = st.get("guesses", [])   # список {"word":..., "marks":[...]}
    rows: list[list[InlineKeyboardButton]] = []
    for g in guesses:
        rows.append([_cell(ch, mark)
                     for ch, mark in zip(g["word"], g["marks"])])
    # Пустые оставшиеся ряды.
    used = len(guesses)
    finished = game["status"] == "finished"
    if not finished:
        for _ in range(MAX_ATTEMPTS - used):
            rows.append([InlineKeyboardButton(text="·", callback_data="noop")
                         for _ in range(WORD_LEN)])
        rows.append([InlineKeyboardButton(
            text="Сдаться", callback_data=f"wordle_giveup:{game['game_id']}",
            style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _board_text(game: dict, extra: str = "") -> str:
    st = game["state"]
    used = len(st.get("guesses", []))
    left = MAX_ATTEMPTS - used
    setter = escape(game["player1_name"] or "Игрок")
    head = (f"🟩 <b>Wordle</b> — угадай слово из {WORD_LEN} букв\n"
            f"🔐 Загадал: {setter}\n")
    if game["status"] == "active":
        head += (f"Попыток осталось: <b>{left}</b>\n\n"
                 "Напишите слово из 5 букв прямо в чат.")
    if extra:
        head += f"\n\n{extra}"
    return head


# ─────────────────────────── ПОТОК ИГРЫ ───────────────────────────

def _new_id() -> str:
    return uuid.uuid4().hex[:12]


async def start_wordle(bot: Bot, msg: Message, bc_id, initiator_id: int,
                       initiator_name: str) -> None:
    """.wordle — создать игру и дать deep-link для загадывания слова."""
    game_id = _new_id()
    state = {"secret": "", "guesses": [], "guesser_id": None,
             "dm_selfplay": False}
    await storage.create_game(
        game_id=game_id, game_type="wordle", chat_id=msg.chat.id,
        bc_id=bc_id or "", player1_id=initiator_id,
        player1_name=initiator_name, state=state, message_id=0)
    await storage.update_game(game_id, status="waiting_word")

    try:
        me = await bot.get_me()
        deep = f"https://t.me/{me.username}?start=wordle_{game_id}"
    except Exception:
        deep = ""

    text = (f"🟩 <b>Wordle</b>\n\n"
            f"👤 {escape(initiator_name)} запускает игру!\n\n"
            "Шаг 1: нажми кнопку ниже — откроется личка со мной, "
            "загадай там секретное слово из 5 букв.\n"
            "Шаг 2: соперник угадывает слово прямо в этом чате.")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔐 Загадать слово", url=deep)
        if deep else
        InlineKeyboardButton(text="🔐 Загадать слово",
                             callback_data=f"wordle_setup:{game_id}")
    ]])
    await bot.send_message(chat_id=msg.chat.id, text=text,
                           reply_markup=kb, business_connection_id=bc_id)


async def handle_start_deeplink(bot: Bot, msg: Message, payload: str) -> bool:
    """Обработка /start wordle_<id> в личке — предложить загадать слово."""
    game_id = payload[len("wordle_"):]
    g = await storage.get_game(game_id)
    if not g or g["game_type"] != "wordle":
        await msg.answer("🟩 Эта игра Wordle не найдена или уже завершена.")
        return True
    if g["status"] != "waiting_word":
        await msg.answer("🟩 Слово для этой игры уже загадано.")
        return True
    if msg.from_user.id != g["player1_id"]:
        await msg.answer("🟩 Загадывает слово только тот, кто запустил игру.")
        return True
    _awaiting_word[msg.from_user.id] = game_id
    await msg.answer(
        "🔐 <b>Загадайте секретное слово</b>\n\n"
        f"Напишите слово из <b>{WORD_LEN} букв</b> (русскими или английскими, "
        "без пробелов и цифр). Я его скрою и запущу игру в исходном чате.")
    return True


async def set_secret_word(bot: Bot, msg: Message) -> None:
    """Игрок прислал секретное слово в личке."""
    uid = msg.from_user.id
    game_id = _awaiting_word.get(uid)
    if not game_id:
        return
    ok, word, err = validate_word(msg.text or "")
    if not ok:
        await msg.answer(f"❌ {err}\nПопробуйте ещё раз — слово из {WORD_LEN} букв.")
        return
    g = await storage.get_game(game_id)
    if not g or g["status"] != "waiting_word":
        _awaiting_word.pop(uid, None)
        await msg.answer("🟩 Игра уже недоступна.")
        return
    st = g["state"]
    st["secret"] = word
    # Тест-режим: если игру запустили в личке с ботом (chat_id == загадывающий),
    # разрешаем угадывать самому.
    st["dm_selfplay"] = (g["chat_id"] == g["player1_id"])
    await storage.update_game(game_id, state=st, status="active")
    _awaiting_word.pop(uid, None)
    _active_chats[g["chat_id"]] = game_id

    await msg.answer(
        "✅ Слово загадано! Игра началась в исходном чате.\n"
        + ("Так как игра запущена в личке со мной — можете угадывать сами "
           "прямо здесь." if st["dm_selfplay"] else
           "Соперник угадывает в том чате, где вы набрали .wordle."))
    # Отправить доску в игровой чат.
    g = await storage.get_game(game_id)
    sent = await bot.send_message(
        chat_id=g["chat_id"], text=_board_text(g),
        reply_markup=board_kb(g),
        business_connection_id=(g["bc_id"] or None))
    await storage.update_game(game_id, message_id=sent.message_id)


async def handle_guess(bot: Bot, msg: Message, bc_id, guesser_id: int,
                       guesser_name: str) -> bool:
    """Обработать догадку (5 букв). Возвращает True, если приняли."""
    chat_id = msg.chat.id
    game_id = _active_chats.get(chat_id)
    if not game_id:
        return False
    g = await storage.get_game(game_id)
    if not g or g["status"] != "active":
        _active_chats.pop(chat_id, None)
        return False
    st = g["state"]

    # Кто может угадывать?
    setter_id = g["player1_id"]
    selfplay = st.get("dm_selfplay")
    if not selfplay and guesser_id == setter_id:
        # Загадывающий не угадывает (кроме тест-режима в личке).
        return False
    # Зафиксировать угадывающего (player2) при первой догадке.
    if st.get("guesser_id") is None:
        st["guesser_id"] = guesser_id
        await storage.update_game(
            game_id, player2_id=guesser_id, player2_name=guesser_name)
    elif st["guesser_id"] != guesser_id and not selfplay:
        return False  # угадывает уже другой участник

    ok, word, err = validate_word(msg.text or "")
    if not ok:
        return False

    marks = score_guess(st["secret"], word)
    st.setdefault("guesses", []).append({"word": word, "marks": marks})
    won = is_win(marks)
    used = len(st["guesses"])
    lost = (not won) and used >= MAX_ATTEMPTS
    status = "finished" if (won or lost) else "active"
    await storage.update_game(game_id, state=st, status=status)
    g = await storage.get_game(game_id)

    extra = ""
    if won:
        extra = (f"🏆 <b>Победа!</b> {escape(guesser_name)} угадал слово "
                 f"<b>{escape(st['secret'])}</b> за {used} попыт. (+15 ⭐)")
        await storage.update_score(guesser_id, chat_id, 15)
        _active_chats.pop(chat_id, None)
    elif lost:
        extra = (f"💀 Попытки кончились. Слово было: "
                 f"<b>{escape(st['secret'])}</b>")
        _active_chats.pop(chat_id, None)

    # Обновить доску: пробуем отредактировать, иначе новое сообщение.
    bcid = g["bc_id"] or None
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=g["message_id"],
            text=_board_text(g, extra), reply_markup=board_kb(g),
            business_connection_id=bcid)
    except Exception:
        try:
            sent = await bot.send_message(
                chat_id=chat_id, text=_board_text(g, extra),
                reply_markup=board_kb(g), business_connection_id=bcid)
            await storage.update_game(game_id, message_id=sent.message_id)
        except Exception as e:
            logger.warning("wordle: не смог обновить доску: %s", e)
    return True


async def give_up(bot: Bot, game_id: str, user_id: int) -> tuple[bool, str]:
    """Сдаться. Возвращает (ok, message_ru)."""
    g = await storage.get_game(game_id)
    if not g or g["status"] != "active":
        return False, "Игра уже завершена."
    st = g["state"]
    # Сдаться может любой участник игры.
    if user_id not in (g["player1_id"], st.get("guesser_id")):
        return False, "Вы не участник этой игры."
    await storage.update_game(game_id, status="finished")
    _active_chats.pop(g["chat_id"], None)
    return True, f"🏳 Игра окончена. Слово было: {escape(st['secret'])}"
