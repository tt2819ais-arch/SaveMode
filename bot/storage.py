"""SQLite-хранилище сообщений для восстановления удалённых."""
import json
import aiosqlite
from typing import Optional

from bot.config import DB_PATH


async def init_db() -> None:
    """Создать таблицы, если их нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                business_connection_id TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                from_user_id INTEGER,
                from_first_name TEXT DEFAULT '',
                from_username TEXT DEFAULT '',
                text TEXT DEFAULT '',
                caption TEXT DEFAULT '',
                content_type TEXT DEFAULT 'text',
                media_file_id TEXT DEFAULT '',
                raw_json TEXT DEFAULT '{}',
                date INTEGER DEFAULT 0,
                local_path TEXT DEFAULT '',
                PRIMARY KEY (business_connection_id, chat_id, message_id)
            )
        """)
        # Миграция для старых БД: добавить local_path, если его нет.
        try:
            await db.execute("ALTER TABLE messages ADD COLUMN local_path TEXT DEFAULT ''")
        except Exception:
            pass  # колонка уже существует
        await db.execute("""
            CREATE TABLE IF NOT EXISTS connections (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                user_first_name TEXT DEFAULT '',
                user_username TEXT DEFAULT '',
                is_enabled INTEGER DEFAULT 1,
                date INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS afk_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS game_sessions (
                game_id TEXT PRIMARY KEY,
                game_type TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                bc_id TEXT NOT NULL,
                player1_id INTEGER NOT NULL,
                player1_name TEXT DEFAULT '',
                player2_id INTEGER,
                player2_name TEXT DEFAULT '',
                state TEXT DEFAULT '{}',
                status TEXT DEFAULT 'waiting',
                message_id INTEGER,
                current_turn INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                points INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, chat_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                owner_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT DEFAULT '',
                PRIMARY KEY (owner_id, key)
            )
        """)
        await db.commit()


async def set_setting(owner_id: int, key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (owner_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(owner_id, key) DO UPDATE SET value=excluded.value",
            (owner_id, key, value))
        await db.commit()


async def get_setting(owner_id: int, key: str, default: str = "") -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT value FROM settings WHERE owner_id=? AND key=?",
            (owner_id, key))
        row = await cur.fetchone()
        return row[0] if row else default


async def get_recent_chats(limit: int = 10) -> list[tuple]:
    """Список недавних отслеживаемых чатов: (имя, число сообщений)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(NULLIF(from_first_name, ''), 'Чат ' || chat_id) "
            "AS name, COUNT(*) AS cnt FROM messages "
            "GROUP BY chat_id ORDER BY MAX(date) DESC LIMIT ?", (limit,))
        return [(r[0], r[1]) for r in await cur.fetchall()]


async def save_message(
    bc_id: str, chat_id: int, message_id: int,
    from_user_id: int, from_first_name: str, from_username: str,
    text: str, caption: str, content_type: str,
    media_file_id: str, raw_json: str, date: int,
    local_path: str = ""
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO messages
            (business_connection_id, chat_id, message_id, from_user_id,
             from_first_name, from_username, text, caption, content_type,
             media_file_id, raw_json, date, local_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (bc_id, chat_id, message_id, from_user_id,
              from_first_name, from_username, text, caption,
              content_type, media_file_id, raw_json, date, local_path))
        await db.commit()


async def get_messages(bc_id: str, chat_id: int, message_ids: list[int]) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" * len(message_ids))
        cursor = await db.execute(f"""
            SELECT * FROM messages
            WHERE business_connection_id = ?
              AND chat_id = ?
              AND message_id IN ({placeholders})
        """, [bc_id, chat_id] + message_ids)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_message(bc_id: str, chat_id: int, message_id: int) -> Optional[dict]:
    msgs = await get_messages(bc_id, chat_id, [message_id])
    return msgs[0] if msgs else None


async def save_connection(conn_id: str, user_id: int,
                          first_name: str, username: str,
                          is_enabled: bool, date: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO connections
            (id, user_id, user_first_name, user_username, is_enabled, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (conn_id, user_id, first_name, username,
              1 if is_enabled else 0, date))
        await db.commit()


async def get_connection(conn_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM connections WHERE id = ?", (conn_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_owner_id_for_connection(conn_id: str) -> Optional[int]:
    conn = await get_connection(conn_id)
    return conn["user_id"] if conn else None


async def list_connections() -> list[dict]:
    """Все подключения (для админ-панели)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM connections ORDER BY date DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_connection_by_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM connections WHERE user_id = ? ORDER BY date DESC LIMIT 1",
            (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_connection_by_username(username: str) -> Optional[dict]:
    username = username.lstrip("@").lower()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM connections WHERE LOWER(user_username) = ? "
            "ORDER BY date DESC LIMIT 1", (username,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_stats() -> dict:
    """Статистика для админ-панели."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        total = await (await db.execute(
            "SELECT COUNT(*) c FROM connections")).fetchone()
        active = await (await db.execute(
            "SELECT COUNT(*) c FROM connections WHERE is_enabled = 1")).fetchone()
        msgs = await (await db.execute(
            "SELECT COUNT(*) c FROM messages")).fetchone()
        games = await (await db.execute(
            "SELECT COUNT(*) c FROM game_sessions")).fetchone()
        return {
            "total_connections": total["c"],
            "active_connections": active["c"],
            "stored_messages": msgs["c"],
            "total_games": games["c"],
        }


async def set_afk(user_id: int, reason: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO afk_users (user_id, reason, enabled)
            VALUES (?, ?, 1)
        """, (user_id, reason))
        await db.commit()


async def remove_afk(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM afk_users WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_afk(user_id: int) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT reason FROM afk_users WHERE user_id = ? AND enabled = 1",
            (user_id,))
        row = await cursor.fetchone()
        return row["reason"] if row else None


async def update_score(user_id: int, chat_id: int, delta: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT points FROM scores WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id))
        row = await cursor.fetchone()
        current = row["points"] if row else 0
        new_val = current + delta
        await db.execute("""
            INSERT OR REPLACE INTO scores (user_id, chat_id, points)
            VALUES (?, ?, ?)
        """, (user_id, chat_id, new_val))
        await db.commit()
        return new_val


async def get_score(user_id: int, chat_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT points FROM scores WHERE user_id = ? AND chat_id = ?",
            (user_id, chat_id))
        row = await cursor.fetchone()
        return row["points"] if row else 0


# --- Game sessions ---

async def create_game(game_id: str, game_type: str, chat_id: int,
                      bc_id: str, player1_id: int, player1_name: str,
                      state: dict, message_id: int = 0) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO game_sessions
            (game_id, game_type, chat_id, bc_id, player1_id, player1_name,
             state, status, message_id, current_turn)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'waiting', ?, ?)
        """, (game_id, game_type, chat_id, bc_id, player1_id, player1_name,
              json.dumps(state), message_id, player1_id))
        await db.commit()


async def get_game(game_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM game_sessions WHERE game_id = ?", (game_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["state"] = json.loads(d["state"])
        return d


async def update_game(game_id: str, **kwargs) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        sets = []
        vals = []
        for k, v in kwargs.items():
            if k == "state":
                v = json.dumps(v)
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(game_id)
        await db.execute(
            f"UPDATE game_sessions SET {', '.join(sets)} WHERE game_id = ?",
            vals)
        await db.commit()
