"""Обработчики Business Mode: подключение, сообщения, удаление, редактирование."""
import json
import logging
import os
import time

from aiogram import Router, Bot, F
from aiogram.types import (
    BusinessConnection, Message, BusinessMessagesDeleted, FSInputFile,
)

from bot import storage
from bot.config import DB_PATH, OWNER_ID
from bot.utils import keyboards
from bot.utils.constants import connection_text
from bot.utils.text_tools import escape, format_user, blockquote
from bot.handlers.antiscam import check_scam
from bot.handlers import commands as cmd_handlers

logger = logging.getLogger(__name__)
router = Router(name="business")


async def _resolve_owner(bc_id: str, bot: Bot) -> int:
    """Определить владельца бизнес-подключения, с фолбэком на OWNER_ID.

    ВАЖНО: Telegram шлёт business_connection ТОЛЬКО один раз (при подключении)
    и НЕ повторяет его при рестарте бота. На эфемерных хостах SQLite-база
    стирается при каждом редеплое → запись подключения теряется → без фолбэка
    owner_id=None и .команды/уведомления об удалении/правках молча не работают.
    Т.к. это персональный бот одного владельца — OWNER_ID авторитетен.
    Дополнительно самовосстанавливаем запись подключения из Telegram.
    """
    conn = await storage.get_connection(bc_id)
    if conn:
        return conn["user_id"]
    # Запись потеряна (редеплой) — восстанавливаем из Telegram и падаем на OWNER_ID
    try:
        bc = await bot.get_business_connection(bc_id)
        user = bc.user
        await storage.save_connection(
            conn_id=bc_id, user_id=user.id,
            first_name=user.first_name or "", username=user.username or "",
            is_enabled=getattr(bc, "is_enabled", True), date=int(time.time()),
        )
        logger.info("Запись подключения %s самовосстановлена (user=%s)",
                    bc_id, user.id)
        return user.id
    except Exception as e:
        logger.warning("Не удалось восстановить подключение %s: %s "
                       "(фолбэк на OWNER_ID)", bc_id, e)
        return OWNER_ID


async def _maybe_autodelete(bot: Bot, msg: Message, bc_id: str,
                            owner_id: int) -> None:
    """Удалить сообщение-триггер команды владельца, если включено авто-удаление.

    Пропускаем команды, которые редактируют исходное сообщение результатом
    (иначе удалится и результат). Работает только в business-чате (bc_id).
    """
    if not bc_id:
        return
    raw = msg.text or msg.caption or ""
    cmd = raw.split(maxsplit=1)[0].lower() if raw else ""
    if cmd in cmd_handlers.EDIT_IN_PLACE_COMMANDS:
        return
    try:
        enabled = await storage.get_setting(owner_id, "autodelete", "1")
        if enabled != "1":
            return
        await bot.delete_business_messages(
            business_connection_id=bc_id, message_ids=[msg.message_id])
    except Exception as e:
        logger.debug("Авто-удаление команды не удалось: %s", e)

# Папка для кэша медиа (нужна для одноразовых / view-once фото и видео —
# их файлы самоуничтожаются, поэтому скачиваем байты сразу при получении).
MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)) or ".", "media")
os.makedirs(MEDIA_DIR, exist_ok=True)
# Не качаем слишком большие файлы (Bot API отдаёт до 20 МБ).
_MAX_DOWNLOAD = 20 * 1024 * 1024

_EXT = {
    "photo": "jpg", "video": "mp4", "voice": "ogg", "video_note": "mp4",
    "audio": "mp3", "document": "bin", "animation": "mp4", "sticker": "webp",
}


def edit_diff(old_text: str, new_text: str,
              from_user_id: int, owner_id: int):
    """Решение об уведомлении о правке (чистая функция для тестов).

    Возвращает (old, new) если нужно уведомить владельца, иначе None.
    Правки самого владельца игнорируем; уведомляем только при реальном
    изменении текста собеседника.
    """
    if owner_id and from_user_id == owner_id:
        return None
    if old_text and old_text != new_text:
        return (old_text, new_text)
    return None


def _is_view_once(msg: Message) -> bool:
    """Best-effort определение одноразового (view-once) медиа."""
    # Разные версии Bot API/aiogram по-разному сигналят о self-destruct.
    for attr in ("photo", "video", "voice", "video_note"):
        obj = getattr(msg, attr, None)
        if obj is not None and getattr(msg, "has_media_spoiler", False):
            return True
    # ttl-поля, если присутствуют в сыром объекте
    return bool(getattr(msg, "ttl_seconds", None))


async def _download_media(bot: Bot, ctype: str, file_id: str,
                          bc_id: str, chat_id: int, message_id: int) -> str:
    """Скачать медиа-байты в локальный кэш. Возвращает путь или ''.

    Критично для одноразовых фото/видео: их file_id перестаёт работать
    после просмотра/самоуничтожения, поэтому сохраняем содержимое сразу.
    """
    if not file_id or ctype in ("text", "other"):
        return ""
    try:
        tf = await bot.get_file(file_id)
        if (getattr(tf, "file_size", 0) or 0) > _MAX_DOWNLOAD:
            return ""
        ext = _EXT.get(ctype, "bin")
        safe_bc = (bc_id or "dm").replace("/", "_")[:40]
        fname = f"{safe_bc}_{chat_id}_{message_id}.{ext}"
        path = os.path.join(MEDIA_DIR, fname)
        await bot.download_file(tf.file_path, path)
        return path
    except Exception as e:
        logger.warning("Не удалось скачать медиа (%s): %s", ctype, e)
        return ""


def _content_info(msg: Message) -> tuple[str, str, str]:
    """Определить тип контента, текст/описание и file_id."""
    if msg.text:
        return "text", msg.text, ""
    if msg.photo:
        return "photo", msg.caption or "📷 Фото", msg.photo[-1].file_id
    if msg.video:
        return "video", msg.caption or "🎥 Видео", msg.video.file_id
    if msg.voice:
        return "voice", "🎤 Голосовое сообщение", msg.voice.file_id
    if msg.video_note:
        return "video_note", "⭕ Видеокружок", msg.video_note.file_id
    if msg.audio:
        return "audio", msg.caption or "🎵 Аудио", msg.audio.file_id
    if msg.document:
        return "document", msg.caption or "📄 Документ", msg.document.file_id
    if msg.sticker:
        return "sticker", f"🎫 Стикер {msg.sticker.emoji or ''}", msg.sticker.file_id
    if msg.animation:
        return "animation", msg.caption or "🎬 GIF", msg.animation.file_id
    return "other", "📎 Сообщение", ""


# ── business_connection ──
@router.business_connection()
async def on_business_connection(conn: BusinessConnection, bot: Bot):
    user = conn.user
    is_enabled = getattr(conn, "is_enabled", True)
    await storage.save_connection(
        conn_id=conn.id, user_id=user.id,
        first_name=user.first_name or "", username=user.username or "",
        is_enabled=is_enabled, date=int(time.time()),
    )
    logger.info("business_connection %s user=%s enabled=%s",
                conn.id, user.id, is_enabled)
    try:
        if is_enabled:
            await bot.send_message(
                chat_id=user.id, text=connection_text(),
                reply_markup=keyboards.connection_kb(),
            )
        else:
            await bot.send_message(
                chat_id=user.id,
                text="❌ SaveMOD отключён. Вы можете подключить его "
                     "снова в любой момент через настройки Telegram Business.",
            )
    except Exception as e:
        logger.warning("Не удалось отправить уведомление о подключении: %s", e)


# ── business_message ──
@router.business_message()
async def on_business_message(msg: Message, bot: Bot):
    bc_id = msg.business_connection_id
    logger.info("📥 business_message получен: chat=%s msg_id=%s bc=%s",
                msg.chat.id, msg.message_id, bc_id)
    owner_id = await _resolve_owner(bc_id, bot)

    ctype, text_or_desc, file_id = _content_info(msg)
    frm = msg.from_user
    fu_id = frm.id if frm else 0
    fu_first = (frm.first_name if frm else "") or ""
    fu_user = (frm.username if frm else "") or ""

    # Одноразовые (view-once) фото/видео/голосовые: скачиваем байты СРАЗУ,
    # пока файл не самоуничтожился. Для остальных медиа тоже кэшируем —
    # это делает восстановление удалённых надёжным (file_id может протухнуть).
    local_path = ""
    if file_id and ctype not in ("text", "other"):
        local_path = await _download_media(
            bot, ctype, file_id, bc_id, msg.chat.id, msg.message_id)

    # Сохраняем сообщение для восстановления при удалении
    try:
        await storage.save_message(
            bc_id=bc_id, chat_id=msg.chat.id, message_id=msg.message_id,
            from_user_id=fu_id, from_first_name=fu_first, from_username=fu_user,
            text=msg.text or "", caption=msg.caption or "",
            content_type=ctype, media_file_id=file_id,
            raw_json=json.dumps({
                "date": msg.date.timestamp() if msg.date else 0,
                "view_once": _is_view_once(msg),
            }),
            date=int(time.time()), local_path=local_path,
        )
    except Exception as e:
        logger.error("Ошибка сохранения сообщения: %s", e)

    # Антискам — проверяем ВХОДЯЩИЕ (не от владельца)
    if owner_id and fu_id != owner_id and msg.text:
        is_scam, reason = check_scam(msg.text, fu_user)
        if is_scam:
            try:
                await bot.send_message(
                    chat_id=owner_id,
                    text=(
                        "🚨 <b>ВНИМАНИЕ: Подозрительное сообщение!</b>\n\n"
                        f"От: {format_user(fu_first, fu_user)}\n"
                        f"Причина: {escape(reason)}\n\n"
                        "Текст сообщения:\n"
                        f"{blockquote(msg.text[:500])}\n\n"
                        "⚠️ Это автоматическое предупреждение (best-effort). "
                        "Будьте осторожны с подозрительными ссылками и запросами."
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning("Ошибка отправки антискам-уведомления: %s", e)

    # Роутинг команд — только сообщения от владельца, начинающиеся с точки
    is_owner_msg = owner_id and fu_id == owner_id
    if msg.text and msg.text.startswith(".") and is_owner_msg:
        await cmd_handlers.dispatch_command(bot, msg, bc_id, owner_id)
        await _maybe_autodelete(bot, msg, bc_id, owner_id)
        return

    # Wordle: догадка собеседника в активной игре этого чата.
    from bot.handlers import wordle
    if msg.text and msg.chat.id in wordle._active_chats and wordle._looks_like_guess(msg.text):
        handled = await wordle.handle_guess(
            bot, msg, bc_id, fu_id, fu_first or "Игрок")
        if handled:
            return

    # Если контент от владельца — точка-команда с медиа (например .check с фото)
    if msg.caption and msg.caption.startswith(".") and is_owner_msg:
        await cmd_handlers.dispatch_command(bot, msg, bc_id, owner_id)
        await _maybe_autodelete(bot, msg, bc_id, owner_id)
        return

    # AFK-автоответ: если владелец в AFK и пишет НЕ владелец
    if owner_id and fu_id != owner_id:
        afk_reason = await storage.get_afk(owner_id)
        if afk_reason is not None:
            await cmd_handlers.maybe_afk_reply(bot, msg, bc_id, afk_reason)


# ── edited_business_message ──
@router.edited_business_message()
async def on_edited_business_message(msg: Message, bot: Bot):
    bc_id = msg.business_connection_id
    logger.info("✏️ edited_business_message: chat=%s msg_id=%s bc=%s",
                msg.chat.id, msg.message_id, bc_id)
    owner_id = await _resolve_owner(bc_id, bot)
    if not owner_id:
        return

    frm = msg.from_user
    fu_id = frm.id if frm else 0
    fu_first = (frm.first_name if frm else "") or ""
    fu_user = (frm.username if frm else "") or ""

    # Не уведомляем о правках самого владельца
    old = await storage.get_message(bc_id, msg.chat.id, msg.message_id)
    new_text = msg.text or msg.caption or "[медиа]"
    old_text = ""
    if old:
        old_text = old["text"] or old["caption"] or "[медиа]"

    diff = edit_diff(old_text, new_text, fu_id, owner_id)
    if diff:
        was, now = diff
        try:
            await bot.send_message(
                chat_id=owner_id,
                text=(
                    f"✏️ {format_user(fu_first, fu_user)} "
                    "отредактировал сообщение.\n\n"
                    f"{blockquote(was)}\n"
                    "⇩⇩⇩\n"
                    f"{blockquote(now)}"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning("Ошибка отправки уведомления о правке: %s", e)

    # Обновляем сохранённую версию
    ctype, _, file_id = _content_info(msg)
    try:
        await storage.save_message(
            bc_id=bc_id, chat_id=msg.chat.id, message_id=msg.message_id,
            from_user_id=fu_id, from_first_name=fu_first, from_username=fu_user,
            text=msg.text or "", caption=msg.caption or "",
            content_type=ctype, media_file_id=file_id,
            raw_json="{}", date=int(time.time()),
        )
    except Exception as e:
        logger.error("Ошибка обновления сообщения: %s", e)


# ── deleted_business_messages ──
@router.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted, bot: Bot):
    bc_id = event.business_connection_id
    logger.info("🗑 deleted_business_messages: chat=%s ids=%s bc=%s",
                event.chat.id, list(event.message_ids), bc_id)
    owner_id = await _resolve_owner(bc_id, bot)
    if not owner_id:
        return

    chat_id = event.chat.id
    msg_ids = list(event.message_ids)
    saved = await storage.get_messages(bc_id, chat_id, msg_ids)
    saved_map = {m["message_id"]: m for m in saved}

    for mid in msg_ids:
        m = saved_map.get(mid)
        if not m:
            try:
                await bot.send_message(
                    chat_id=owner_id,
                    text=(f"🗑 Удалено сообщение (ID: {mid}) — содержимое "
                          "недоступно (бот не видел это сообщение)."),
                )
            except Exception:
                pass
            continue

        # Не уведомляем об удалении собственных сообщений владельца
        header = (
            "🗑 <b>Это сообщение было удалено</b>\n"
            f"{format_user(m['from_first_name'], m['from_username'])}\n\n"
        )
        ctype = m["content_type"]
        file_id = m["media_file_id"]
        body = m["text"] or m["caption"] or ""
        # Для одноразовых/удалённых медиа file_id часто уже мёртв —
        # берём локально сохранённые байты, если есть.
        lp = m.get("local_path") or ""
        src = FSInputFile(lp) if lp and os.path.exists(lp) else file_id
        vo = ""
        try:
            vo = "🔥 (одноразовое) " if json.loads(
                m.get("raw_json") or "{}").get("view_once") else ""
        except Exception:
            vo = ""
        header = header.replace("🗑 <b>Это сообщение было удалено</b>",
                                f"🗑 <b>{vo}Это сообщение было удалено</b>")

        try:
            if ctype == "text":
                await bot.send_message(
                    chat_id=owner_id,
                    text=header + escape(body),
                    parse_mode="HTML",
                )
            elif ctype == "photo" and src:
                await bot.send_photo(owner_id, src,
                                     caption=header + escape(m["caption"] or ""),
                                     parse_mode="HTML")
            elif ctype == "video" and src:
                await bot.send_video(owner_id, src,
                                     caption=header + escape(m["caption"] or ""),
                                     parse_mode="HTML")
            elif ctype == "voice" and src:
                await bot.send_voice(owner_id, src,
                                     caption=header, parse_mode="HTML")
            elif ctype == "video_note" and src:
                await bot.send_message(owner_id, header + "⭕ Видеокружок",
                                       parse_mode="HTML")
                await bot.send_video_note(owner_id, src)
            elif ctype == "audio" and src:
                await bot.send_audio(owner_id, src,
                                     caption=header, parse_mode="HTML")
            elif ctype == "document" and src:
                await bot.send_document(owner_id, src,
                                        caption=header, parse_mode="HTML")
            elif ctype == "sticker" and src:
                await bot.send_message(owner_id, header + escape(body),
                                       parse_mode="HTML")
                await bot.send_sticker(owner_id, src)
            elif ctype == "animation" and src:
                await bot.send_animation(owner_id, src,
                                         caption=header, parse_mode="HTML")
            else:
                await bot.send_message(owner_id, header + escape(body or "📎 Медиа"),
                                       parse_mode="HTML")
        except Exception as e:
            logger.warning("Ошибка отправки удалённого сообщения: %s", e)
            try:
                await bot.send_message(
                    chat_id=owner_id,
                    text=header + escape(body or "[медиа недоступно]"),
                    parse_mode="HTML",
                )
            except Exception:
                pass
