"""Обработчики Business Mode: подключение, сообщения, удаление, редактирование."""
import json
import logging
import time

from aiogram import Router, Bot, F
from aiogram.types import (
    BusinessConnection, Message, BusinessMessagesDeleted,
)

from bot import storage
from bot.utils import keyboards
from bot.utils.constants import CONNECTION_TEXT
from bot.utils.text_tools import escape, format_user, blockquote
from bot.handlers.antiscam import check_scam
from bot.handlers import commands as cmd_handlers

logger = logging.getLogger(__name__)
router = Router(name="business")


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
                chat_id=user.id, text=CONNECTION_TEXT,
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
    conn = await storage.get_connection(bc_id)
    owner_id = conn["user_id"] if conn else None

    ctype, text_or_desc, file_id = _content_info(msg)
    frm = msg.from_user
    fu_id = frm.id if frm else 0
    fu_first = (frm.first_name if frm else "") or ""
    fu_user = (frm.username if frm else "") or ""

    # Сохраняем сообщение для восстановления при удалении
    try:
        await storage.save_message(
            bc_id=bc_id, chat_id=msg.chat.id, message_id=msg.message_id,
            from_user_id=fu_id, from_first_name=fu_first, from_username=fu_user,
            text=msg.text or "", caption=msg.caption or "",
            content_type=ctype, media_file_id=file_id,
            raw_json=json.dumps({"date": msg.date.timestamp() if msg.date else 0}),
            date=int(time.time()),
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
        return

    # Если контент от владельца — точка-команда с медиа (например .check с фото)
    if msg.caption and msg.caption.startswith(".") and is_owner_msg:
        await cmd_handlers.dispatch_command(bot, msg, bc_id, owner_id)
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
    conn = await storage.get_connection(bc_id)
    owner_id = conn["user_id"] if conn else None
    if not owner_id:
        return

    frm = msg.from_user
    fu_id = frm.id if frm else 0
    fu_first = (frm.first_name if frm else "") or ""
    fu_user = (frm.username if frm else "") or ""

    # Не уведомляем о правках самого владельца
    old = await storage.get_message(bc_id, msg.chat.id, msg.message_id)
    new_text = msg.text or msg.caption or "[медиа]"

    if fu_id != owner_id:
        old_text = ""
        if old:
            old_text = old["text"] or old["caption"] or "[медиа]"
        if old_text and old_text != new_text:
            try:
                await bot.send_message(
                    chat_id=owner_id,
                    text=(
                        f"✏️ {format_user(fu_first, fu_user)} "
                        "отредактировал сообщение.\n\n"
                        f"{blockquote(old_text)}\n"
                        "⇩⇩⇩\n"
                        f"{blockquote(new_text)}"
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
    conn = await storage.get_connection(bc_id)
    owner_id = conn["user_id"] if conn else None
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

        try:
            if ctype == "text":
                await bot.send_message(
                    chat_id=owner_id,
                    text=header + escape(body),
                    parse_mode="HTML",
                )
            elif ctype == "photo" and file_id:
                await bot.send_photo(owner_id, file_id,
                                     caption=header + escape(m["caption"] or ""),
                                     parse_mode="HTML")
            elif ctype == "video" and file_id:
                await bot.send_video(owner_id, file_id,
                                     caption=header + escape(m["caption"] or ""),
                                     parse_mode="HTML")
            elif ctype == "voice" and file_id:
                await bot.send_voice(owner_id, file_id,
                                     caption=header, parse_mode="HTML")
            elif ctype == "video_note" and file_id:
                await bot.send_message(owner_id, header + "⭕ Видеокружок",
                                       parse_mode="HTML")
                await bot.send_video_note(owner_id, file_id)
            elif ctype == "audio" and file_id:
                await bot.send_audio(owner_id, file_id,
                                     caption=header, parse_mode="HTML")
            elif ctype == "document" and file_id:
                await bot.send_document(owner_id, file_id,
                                        caption=header, parse_mode="HTML")
            elif ctype == "sticker" and file_id:
                await bot.send_message(owner_id, header + escape(body),
                                       parse_mode="HTML")
                await bot.send_sticker(owner_id, file_id)
            elif ctype == "animation" and file_id:
                await bot.send_animation(owner_id, file_id,
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
