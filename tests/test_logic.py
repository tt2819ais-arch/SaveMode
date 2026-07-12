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
    assert len(COMMANDS) == 23
    # все имена уникальны и начинаются с точки
    names = [c[0] for c in COMMANDS]
    assert len(set(names)) == 23
    assert all(n.startswith(".") for n in names)
    # индексация работает
    assert get_command_index(".help") >= 0
    assert get_command_index(".nonexistent") == -1
    # запрещённые команды отсутствуют
    for banned in (".crash", ".spam", ".zaebu", ".dox", ".clone", ".mute"):
        assert banned not in names
    grouped = get_commands_by_category()
    assert sum(len(v) for v in grouped.values()) == 23


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
