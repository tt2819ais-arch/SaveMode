"""Юнит-тесты логики SaveMOD (без сети/Telegram).

Запуск: python -m pytest tests/ -q   (или просто python tests/test_logic.py)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("BOT_TOKEN", "dummy")
os.environ.setdefault("OWNER_ID", "111")
os.environ.setdefault("DB_PATH", "/tmp/savemod_test.db")

from bot.utils.text_tools import (
    switch_layout, kawaii, love, blockquote, summarize, format_user, escape,
)
from bot.handlers.antiscam import check_scam
from bot.handlers.games import ttt_winner, ttt_full, resolve_duel_round, STAKES
from bot.utils.audio import EFFECTS, EFFECT_NAMES
from bot.utils.constants import COMMANDS, get_command_index, get_commands_by_category


def test_switch_layout():
    assert switch_layout("ghbdtn") == "привет"
    assert switch_layout("руддщ") == "hello"
    assert switch_layout("") == ""
    # обратимость на смешанных не гарантируется, но не должно падать
    switch_layout("Привет World 123")


def test_kawaii_love():
    assert kawaii("hello world")  # непустой
    assert love("я тебя люблю")
    assert "💕" in love("тест")


def test_blockquote_escape():
    assert blockquote("<b>x</b>") == "<blockquote>&lt;b&gt;x&lt;/b&gt;</blockquote>"
    assert escape("a<b>&c") == "a&lt;b&gt;&amp;c"
    assert "@user" in format_user("Имя", "user")
    assert format_user("Имя", "") == "Имя"


def test_summarize():
    long = ("Погода сегодня отличная. Мы пошли гулять в парк. "
            "В парке было много людей. Погода была тёплая и солнечная. "
            "Дети играли на площадке. Вечером мы вернулись домой уставшие.")
    s = summarize(long, 2)
    assert s and len(s) < len(long)
    # короткий текст возвращается как есть
    short = "Привет."
    assert summarize(short, 3) == short


def test_check_scam():
    assert check_scam("отправь сид-фразу срочно")[0] is True
    assert check_scam("привет, как дела?")[0] is False
    assert check_scam("вы выиграли приз, заберите подарок")[0] is True
    assert check_scam("", "gift_bot")[0] is True
    assert check_scam("отправь подарок stars для проверки")[0] is True
    assert check_scam("нормальное сообщение про звёзды на небе")[0] is False


def test_ttt():
    assert ttt_winner(["X", "X", "X", "", "", "", "", "", ""]) == "X"
    assert ttt_winner(["O", "", "", "O", "", "", "O", "", ""]) == "O"
    assert ttt_winner(["X", "O", "X", "O", "X", "O", "O", "X", "O"]) == ""
    assert ttt_full(["X"] * 9) is True
    assert ttt_full(["X", ""] + ["O"] * 7) is False


def test_duel():
    d1, d2, desc = resolve_duel_round("attack", "attack")
    assert d1 >= 0 and d2 >= 0 and desc
    d1, d2, _ = resolve_duel_round("defend", "defend")
    assert d1 == 0 and d2 == 0  # никто не атакует


def test_stakes_and_effects():
    assert set(STAKES) == {"ttt", "duel", "dice", "flip", "bw"}
    assert set(EFFECTS) == set(EFFECT_NAMES)
    assert "chipmunk" in EFFECTS and "robot" in EFFECTS


def test_commands_registry():
    assert len(COMMANDS) == 35
    # все имена уникальны и начинаются с точки
    names = [c[0] for c in COMMANDS]
    assert len(set(names)) == 35
    assert all(n.startswith(".") for n in names)
    # индексация работает
    assert get_command_index(".help") >= 0
    assert get_command_index(".nonexistent") == -1
    # запрещённые команды отсутствуют (HARD RULE)
    for banned in (".crash", ".spam", ".zaebu", ".dox", ".clone", ".mute",
                   ".troll"):
        assert banned not in names
    # новые инструменты присутствуют
    for tool in (".qr", ".tr", ".calc", ".pass", ".mock", ".rev", ".roll",
                 ".pick", ".count", ".b64", ".spoiler"):
        assert tool in names
    grouped = get_commands_by_category()
    assert sum(len(v) for v in grouped.values()) == 35


def test_category_distribution():
    grouped = get_commands_by_category()
    expected = {"messages": 6, "tools": 11, "games": 6,
                "processing": 10, "other": 2}
    for key, exp in expected.items():
        assert len(grouped.get(key, [])) == exp, (key, len(grouped.get(key, [])))


def test_flat_menu_structure():
    """Новое плоское меню: кнопка на каждую команду + маркер 🟢 + 'Назад'."""
    from bot.utils import keyboards
    from bot.utils.constants import menu_text, button_label
    kb = keyboards.main_menu_kb(is_owner=False)
    cmd_btns = [b for row in kb.inline_keyboard for b in row
                if b.callback_data and b.callback_data.startswith("cmd:")]
    # По кнопке на каждую команду
    assert len(cmd_btns) == len(COMMANDS)
    labels = [b.text for row in kb.inline_keyboard for b in row]
    # Есть кнопка 'Назад', нет счётчиков '(0)'
    assert any("Назад" in l for l in labels)
    assert "(0)" not in " ".join(labels)
    # Активная команда красится в зелёный (реальный style="success").
    kb2 = keyboards.main_menu_kb(active_cmd=".qr")
    active_btns = [b for row in kb2.inline_keyboard for b in row
                   if b.callback_data == f"cmd:{get_command_index('.qr')}"]
    assert active_btns and active_btns[0].style == "success"
    # Прочие команды — без стиля (один зелёный акцент, а не «радуга»).
    others = [b for row in kb2.inline_keyboard for b in row
              if b.callback_data and b.callback_data.startswith("cmd:")
              and b.callback_data != f"cmd:{get_command_index('.qr')}"]
    assert all(b.style is None for b in others)
    # Навигация «Назад» — синяя (primary).
    nav = [b for row in kb2.inline_keyboard for b in row
           if b.callback_data == "cmd_welcome"]
    assert nav and nav[0].style == "primary"
    # menu_text перечисляет категории и команды
    mt = menu_text()
    assert "Инструменты" in mt and ".qr" in mt
    assert "Нажми на кнопку" in mt
    # admin-кнопка только для владельца
    kb_owner = keyboards.main_menu_kb(is_owner=True)
    assert any((b.callback_data == "admin_menu")
               for row in kb_owner.inline_keyboard for b in row)


def test_wordle_scoring():
    from bot.handlers.wordle import (
        score_guess, is_win, validate_word, normalize_word,
    )
    # Точное совпадение → всё зелёное
    assert score_guess("ЗАМОК", "ЗАМОК") == ["green"] * 5
    assert is_win(score_guess("ЗАМОК", "ЗАМОК"))
    # Полностью мимо (нет пересечения букв)
    assert score_guess("ФЫВАП", "ЮБЬДЖ") == ["grey"] * 5
    # Классический EN пример с дублями:
    # secret ALLOY, guess LOLLY:
    #  L(0): в слове есть L, но позиция 0 = A → yellow (1 L доступна)
    #  O(1): в слове есть O (поз3), но здесь поз1 → yellow
    #  L(2): вторая L — в ALLOY только одна L осталась? ALLOY имеет L на поз1,2.
    #        secret=ALLOY: A L L O Y. guess=LOLLY: L O L L Y
    marks = score_guess("ALLOY", "LOLLY")
    #  поз0 L vs A: L есть (2 шт) → yellow
    #  поз1 O vs L: O есть (поз3) → yellow
    #  поз2 L vs L: green
    #  поз3 L vs O: осталась 1 L (2-1зел-1жёлт=0) → grey
    #  поз4 Y vs Y: green
    assert marks == ["yellow", "yellow", "green", "grey", "green"], marks
    # Дубли в догадке при одной букве в слове:
    # secret CIGAR, guess AGAIN → буквы A(поз3),I(поз1),G(поз2)
    m2 = score_guess("CIGAR", "AGAIN")
    # A: в CIGAR одна A (поз3). guess A на поз0 → yellow, вторая A поз2 → grey
    assert m2[0] == "yellow" and m2[2] == "grey", m2
    assert not is_win(m2)
    # Валидация
    ok, w, _ = validate_word("привет")  # 6 букв
    assert not ok
    ok, w, _ = validate_word("замок")
    assert ok and w == "ЗАМОК"
    ok, w, _ = validate_word("hello")
    assert ok and w == "HELLO"
    ok, _, _ = validate_word("прив1")  # цифра
    assert not ok
    ok, _, _ = validate_word("abвгд")  # смешанные алфавиты
    assert not ok
    # ё → е нормализация
    assert normalize_word("ёжикЁ") == "ЕЖИКЕ"


def test_wordle_cell_colors():
    """Клетки доски раскрашены style'ом; жёлтый — единственный эмодзи-фолбэк."""
    from bot.handlers.wordle import _cell, board_kb
    g = _cell("П", "green")
    assert g.text == "П" and g.style == "success"      # зелёная кнопка, без эмодзи
    grey = _cell("Ы", "grey")
    assert grey.text == "Ы" and getattr(grey, "style", None) is None  # серая, без эмодзи
    y = _cell("В", "yellow")
    assert y.text == "В🟨" and getattr(y, "style", None) is None       # только жёлтый — эмодзи
    # «Сдаться» без декоративного флага, красная
    game = {"state": {"guesses": [{"word": "ПРИВЕ", "marks":
            ["green", "grey", "yellow", "grey", "green"]}]},
            "status": "active", "game_id": "g1"}
    kb = board_kb(game)
    surrender = kb.inline_keyboard[-1][0]
    assert surrender.text == "Сдаться" and surrender.style == "danger"


async def _resolve_owner_flow():
    """Регресс на 'после редеплоя .команды/уведомления молчат'.

    Запись подключения стирается на эфемерном хосте → get_connection=None.
    _resolve_owner должен вернуть OWNER_ID (фолбэк), а не None.
    """
    test_db = "/tmp/savemod_test.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    from bot import storage
    from bot.handlers.business import _resolve_owner
    from bot.config import OWNER_ID
    await storage.init_db()

    class _FakeBot:
        async def get_business_connection(self, bc_id):
            raise RuntimeError("no network in test")

    bot = _FakeBot()
    # запись отсутствует → фолбэк на OWNER_ID (не None!)
    owner = await _resolve_owner("bc_missing", bot)
    assert owner == OWNER_ID and owner, owner
    # запись есть → берём из неё
    await storage.save_connection("bc_ok", 999, "N", "n", True, 1)
    assert await _resolve_owner("bc_ok", bot) == 999
    os.remove(test_db)


def test_resolve_owner_fallback():
    asyncio.run(_resolve_owner_flow())


def test_edit_diff():
    """Регресс на 'изменённое сообщение не сохраняет'."""
    from bot.handlers.business import edit_diff
    # правка собеседника с реальным изменением → уведомляем
    assert edit_diff("привет", "пока", from_user_id=222, owner_id=111) == ("привет", "пока")
    # правка самого владельца → не уведомляем
    assert edit_diff("привет", "пока", from_user_id=111, owner_id=111) is None
    # текст не изменился → не уведомляем
    assert edit_diff("привет", "привет", from_user_id=222, owner_id=111) is None
    # нет старого текста → не уведомляем
    assert edit_diff("", "новое", from_user_id=222, owner_id=111) is None


async def _storage_flow():
    # уникальная БД для теста
    test_db = "/tmp/savemod_test.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    from bot import storage
    await storage.init_db()
    # connections
    await storage.save_connection("bc1", 111, "Test", "testuser", True, 1700000000)
    assert (await storage.get_connection("bc1"))["user_id"] == 111
    assert (await storage.get_connection_by_username("@TestUser"))["user_id"] == 111
    assert len(await storage.list_connections()) == 1
    # messages
    await storage.save_message("bc1", 5, 10, 222, "Bob", "bob", "hi", "",
                               "text", "", "{}", 1700000001)
    m = await storage.get_message("bc1", 5, 10)
    assert m["text"] == "hi"
    ms = await storage.get_messages("bc1", 5, [10, 999])
    assert len(ms) == 1
    # view-once / медиа с локальным кэшем
    await storage.save_message("bc1", 5, 11, 222, "Bob", "bob", "", "📷",
                               "photo", "FILEID", '{"view_once": true}',
                               1700000002, local_path="/tmp/vo_test.jpg")
    m2 = await storage.get_message("bc1", 5, 11)
    assert m2["local_path"] == "/tmp/vo_test.jpg"
    assert m2["content_type"] == "photo"
    # afk
    await storage.set_afk(111, "sleeping")
    assert await storage.get_afk(111) == "sleeping"
    await storage.remove_afk(111)
    assert await storage.get_afk(111) is None
    # scores
    v = await storage.update_score(111, 5, 10)
    assert v == 10
    assert await storage.get_score(111, 5) == 10
    # games
    await storage.create_game("g1", "ttt", 5, "bc1", 111, "A",
                              {"board": [""] * 9}, 42)
    g = await storage.get_game("g1")
    assert g["status"] == "waiting" and g["state"]["board"] == [""] * 9
    await storage.update_game("g1", status="active", current_turn=111)
    assert (await storage.get_game("g1"))["status"] == "active"
    # stats
    st = await storage.get_stats()
    assert st["total_connections"] == 1 and st["total_games"] == 1
    os.remove(test_db)


def test_storage():
    asyncio.run(_storage_flow())


def test_button_styles_valid():
    """Все style у кнопок — только допустимые значения Bot API."""
    from bot.utils import keyboards
    valid = {"success", "primary", "danger", None}
    kbs = [
        keyboards.main_menu_kb(is_owner=True, active_cmd=".calc"),
        keyboards.connection_kb(),
        keyboards.onboarding_kb("MaksimkaXyila_bot"),
        keyboards.admin_menu_kb(),
        keyboards.broadcast_confirm_kb(),
        keyboards.game_invite_kb("g1"),
        keyboards.dice_kb("g1"),
        keyboards.command_detail_kb(0),
    ]
    for kb in kbs:
        for row in kb.inline_keyboard:
            for b in row:
                assert getattr(b, "style", None) in valid, (b.text, b.style)
    # Подтверждение рассылки: success + danger.
    bc = keyboards.broadcast_confirm_kb()
    styles = [b.style for row in bc.inline_keyboard for b in row]
    assert "success" in styles and "danger" in styles
    # Приглашение в игру: accept=success, cancel=danger.
    gi = keyboards.game_invite_kb("g1")
    gstyles = [b.style for row in gi.inline_keyboard for b in row]
    assert "success" in gstyles and "danger" in gstyles


def test_button_style_serializes():
    """style реально попадает в JSON-разметку для Telegram."""
    import json
    from bot.utils import keyboards
    kb = keyboards.main_menu_kb(active_cmd=".calc")
    payload = json.dumps(kb.model_dump(exclude_none=True))
    assert '"style": "success"' in payload
    assert '"style": "primary"' in payload


def test_buttons_no_decorative_emoji():
    """Меню/админ/навигация/игровые-экшены — чистый текст, без эмодзи.

    Смысл несёт цвет (style), а не декоративный эмодзи. Клетки-состояния
    игр (ttt/bw/wordle) — это контент, их не проверяем здесь.
    """
    import re
    from bot.utils import keyboards
    emoji_re = re.compile(
        "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
        "\u2190-\u21FF\u2B00-\u2BFF\uFE0F\u2705\u274C\u2699]")
    kbs = [
        keyboards.main_menu_kb(is_owner=True, active_cmd=".calc"),
        keyboards.connection_kb(),
        keyboards.onboarding_kb("MaksimkaXyila_bot"),
        keyboards.admin_menu_kb(),
        keyboards.admin_back_kb(),
        keyboards.broadcast_confirm_kb(),
        keyboards.game_invite_kb("g1"),
        keyboards.dice_kb("g1"),
        keyboards.flip_kb("g1"),
        keyboards.duel_kb("g1"),
        keyboards.fv_kb(),
    ]
    for kb in kbs:
        for row in kb.inline_keyboard:
            for b in row:
                assert not emoji_re.search(b.text), f"эмодзи в кнопке: {b.text!r}"


def test_profile_edit_url_button():
    """Кнопка 'Редактирование профиля' — URL на tg://settings/edit."""
    from bot.utils import keyboards
    kb = keyboards.onboarding_kb("MaksimkaXyila_bot")
    btns = [b for row in kb.inline_keyboard for b in row
            if "Редактирование профиля" in b.text]
    assert btns and btns[0].url == "tg://settings/edit"
    # старый callback profile_edit больше не используется
    assert all(getattr(b, "callback_data", None) != "profile_edit"
               for row in kb.inline_keyboard for b in row)


def test_tools_calc():
    from bot.utils import tools
    assert tools.calc("(2+3)*4 / 2") == 10
    assert tools.calc("2**8") == 256
    assert tools.calc("sqrt(144)") == 12
    assert tools.calc("10 % 3") == 1
    assert tools.calc("abs(-5) + round(2.4)") == 7
    # опасные конструкции запрещены
    for bad in ("__import__('os')", "open('x')", "a = 1", "os.system('x')"):
        try:
            tools.calc(bad)
            assert False, f"должно было упасть: {bad}"
        except Exception:
            pass


def test_tools_password():
    from bot.utils import tools
    p = tools.gen_password(20)
    assert len(p) == 20
    assert any(c.isdigit() for c in p) and any(c.isupper() for c in p)
    assert len(tools.gen_password(2)) == 4       # нижняя граница
    assert len(tools.gen_password(999)) == 128    # верхняя граница
    assert tools.gen_password(16) != tools.gen_password(16)  # случайность


def test_tools_text():
    from bot.utils import tools
    assert tools.mock_case("abcd") == "aBcD"
    assert tools.reverse_text("привет") == "тевирп"
    assert tools.b64("e", "hi") == "aGk="
    assert tools.b64("d", "aGk=") == "hi"
    try:
        tools.b64("d", "!!!notbase64!!!")
        assert False
    except Exception:
        pass


def test_tools_roll_pick_count():
    from bot.utils import tools
    for _ in range(50):
        out = tools.roll("6")
        num = int(out.split("<b>")[1].split("</b>")[0])
        assert 1 <= num <= 6
    assert "=" in tools.roll("3d6")
    assert tools.pick("a | b | c") in ("a", "b", "c")
    try:
        tools.pick("только один")
        assert False
    except Exception:
        pass
    stats = tools.count_text("hello world\nfoo")
    assert "Слов: <b>3</b>" in stats
    assert "Строк: <b>2</b>" in stats


def test_tools_tr_args():
    from bot.utils import tools
    assert tools.parse_tr_args("en привет") == ("en", "привет")
    assert tools.parse_tr_args("hello world") == ("ru", "hello world")
    assert tools.parse_tr_args("de Hallo Welt") == ("de", "Hallo Welt")


def test_tools_qr():
    from bot.utils import tools
    png = tools.make_qr_png("https://t.me/test")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"   # PNG-заголовок
    assert len(png) > 100


def test_autodelete_set_logic():
    """EDIT_IN_PLACE команды не должны авто-удаляться."""
    from bot.handlers.commands import EDIT_IN_PLACE_COMMANDS
    assert ".kawaii" in EDIT_IN_PLACE_COMMANDS
    assert ".calc" in EDIT_IN_PLACE_COMMANDS
    # команды с отдельным выводом НЕ в списке (их триггер удаляется)
    assert ".qr" not in EDIT_IN_PLACE_COMMANDS
    assert ".nk" not in EDIT_IN_PLACE_COMMANDS


if __name__ == "__main__":
    passed = 0
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"✅ {name}")
                passed += 1
            except Exception as e:
                print(f"❌ {name}: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
