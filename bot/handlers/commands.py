"""Обработчики всех .команд SaveMOD.

Команды владельца в business-чатах. Форматирующие команды
(.kawaii/.love/.sw/.type) редактируют исходящее сообщение владельца
через business_connection_id. Остальные выполняют своё действие.
"""
import asyncio
import io
import logging
import time
from datetime import datetime

import aiohttp
from aiogram import Bot
from aiogram.types import Message

from bot import storage
from bot.utils import keyboards
from bot.utils.text_tools import (
    escape, switch_layout, kawaii, love, format_user,
)
from bot.utils.premium_emoji import pe, pe_random

logger = logging.getLogger(__name__)

# Антиспам для AFK-автоответов: {(bc_id, chat_id): last_ts}
_afk_last: dict = {}
# Антиспам для .type
_type_last: dict = {}
# Ожидающие обработки голосовые для .fv: {owner_id: file_id}
fv_pending: dict = {}


def _parse(text: str) -> tuple[str, str]:
    """Разбить '.cmd аргументы' на (команда, аргумент)."""
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    return cmd, arg


async def _edit_own(bot: Bot, msg: Message, bc_id: str, new_text: str,
                    parse_mode: str | None = None) -> bool:
    """Отредактировать исходящее сообщение владельца.

    В личке бота (bc_id пустой) редактировать чужое сообщение нельзя —
    отправляем результат обычным сообщением (тест-режим).
    """
    if not bc_id:
        try:
            await bot.send_message(chat_id=msg.chat.id, text=new_text,
                                   parse_mode=parse_mode)
            return True
        except Exception as e:
            logger.warning("Не удалось отправить результат в личке: %s", e)
            return False
    try:
        await bot.edit_message_text(
            chat_id=msg.chat.id,
            message_id=msg.message_id,
            text=new_text,
            business_connection_id=bc_id,
            parse_mode=parse_mode,
        )
        return True
    except Exception as e:
        logger.warning("Не удалось отредактировать сообщение: %s", e)
        # fallback — отправить новым сообщением
        try:
            await bot.send_message(
                chat_id=msg.chat.id, text=new_text,
                business_connection_id=bc_id, parse_mode=parse_mode,
            )
            return True
        except Exception as e2:
            logger.warning("Fallback отправки не удался: %s", e2)
            return False


async def _notify_owner_cmd(bot: Bot, owner_id: int, cmd: str,
                            username: str, desc: str):
    """Уведомление владельцу '🃏 команда для @username'."""
    try:
        uname = f"@{username}" if username else "чата"
        await bot.send_message(
            chat_id=owner_id,
            text=f"🃏 <b>{escape(cmd)}</b> для {escape(uname)}.\n{escape(desc)}",
            parse_mode="HTML",
        )
    except Exception:
        pass


async def maybe_afk_reply(bot: Bot, msg: Message, bc_id: str, reason: str):
    """AFK-автоответ (не чаще 1 раза в 60 сек на чат)."""
    key = (bc_id, msg.chat.id)
    now = time.time()
    if now - _afk_last.get(key, 0) < 60:
        return
    _afk_last[key] = now
    try:
        txt = f"💤 Пользователь сейчас AFK: {reason}" if reason else \
              "💤 Пользователь сейчас AFK."
        await bot.send_message(
            chat_id=msg.chat.id, text=txt, business_connection_id=bc_id,
        )
    except Exception as e:
        logger.warning("AFK-автоответ не отправлен: %s", e)


# Команды, которые ЗАМЕНЯЮТ (редактируют) исходное сообщение владельца
# результатом — их триггер удалять НЕ нужно (иначе пропадёт и результат).
EDIT_IN_PLACE_COMMANDS = {
    ".kawaii", ".love", ".sw", ".type", ".calc", ".mock", ".rev", ".roll",
    ".pick", ".b64", ".spoiler", ".tr", ".status", ".time",
}


async def dispatch_command(bot: Bot, msg: Message, bc_id: str, owner_id: int):
    """Роутер команд владельца."""
    raw = msg.text or msg.caption or ""
    cmd, arg = _parse(raw)

    # Определить username собеседника
    partner = msg.chat.username or ""

    # Переключатель авто-удаления команд (.autodel on|off) — не в меню.
    if cmd == ".autodel":
        state = arg.strip().lower()
        if state in ("on", "вкл", "1", "да"):
            await storage.set_setting(owner_id, "autodelete", "1")
            await bot.send_message(
                owner_id, f"{pe('gear')} Авто-удаление команд включено.",
                parse_mode="HTML")
        elif state in ("off", "выкл", "0", "нет"):
            await storage.set_setting(owner_id, "autodelete", "0")
            await bot.send_message(
                owner_id, f"{pe('gear')} Авто-удаление команд выключено.",
                parse_mode="HTML")
        else:
            cur = await storage.get_setting(owner_id, "autodelete", "1")
            await bot.send_message(
                owner_id,
                f"{pe('gear')} Авто-удаление сейчас: "
                f"<b>{'вкл' if cur == '1' else 'выкл'}</b>.\n"
                "Переключить: <code>.autodel on</code> / <code>.autodel off</code>",
                parse_mode="HTML")
        return

    handlers = {
        ".help": cmd_help,
        ".kawaii": cmd_kawaii,
        ".love": cmd_love,
        ".sw": cmd_sw,
        ".type": cmd_type,
        ".check": cmd_check,
        ".afk": cmd_afk,
        ".info": cmd_info,
        ".nk": cmd_nk,
        ".short": cmd_short,
        ".status": cmd_status,
        ".gifts": cmd_gifts,
        ".fv": cmd_fv,
        ".story": cmd_story,
        ".time": cmd_time,
        ".yars": cmd_yars,
        ".gosu": cmd_gosu,
        ".lq": cmd_lq,
        ".qr": cmd_qr,
        ".tr": cmd_tr,
        ".calc": cmd_calc,
        ".pass": cmd_pass,
        ".mock": cmd_mock,
        ".rev": cmd_rev,
        ".roll": cmd_roll,
        ".pick": cmd_pick,
        ".count": cmd_count,
        ".b64": cmd_b64,
        ".spoiler": cmd_spoiler,
    }

    # Игры
    if cmd in (".ttt", ".duel", ".dice", ".flip", ".bw"):
        from bot.handlers import games
        gtype = cmd[1:]
        pname = (msg.from_user.first_name if msg.from_user else "Игрок") or "Игрок"
        await games.start_game(bot, msg, gtype, bc_id, owner_id, pname)
        return
    if cmd == ".wordle":
        from bot.handlers import wordle
        initiator = (msg.from_user.id if msg.from_user else owner_id)
        pname = (msg.from_user.first_name if msg.from_user else "Игрок") or "Игрок"
        await wordle.start_wordle(bot, msg, bc_id, initiator, pname)
        return

    handler = handlers.get(cmd)
    if handler:
        try:
            await handler(bot, msg, bc_id, owner_id, arg, partner)
        except Exception as e:
            logger.exception("Ошибка команды %s: %s", cmd, e)
            try:
                await bot.send_message(
                    owner_id,
                    f"⚠️ Внутренняя ошибка при выполнении {escape(cmd)}. "
                    "Попробуйте позже.")
            except Exception:
                pass
    # Неизвестная команда — игнорируем (не мешаем обычным сообщениям с точкой)


# ══════════ КОМАНДЫ ══════════

async def cmd_help(bot, msg, bc_id, owner_id, arg, partner):
    from bot.utils.constants import menu_text
    await bot.send_message(
        chat_id=owner_id,
        text=menu_text(),
        reply_markup=keyboards.main_menu_kb(is_owner=True),
        parse_mode="HTML",
    )


async def cmd_kawaii(bot, msg, bc_id, owner_id, arg, partner):
    if not arg:
        await _edit_own(bot, msg, bc_id, "🌸 Укажите текст: .kawaii [текст]")
        return
    await _edit_own(bot, msg, bc_id, kawaii(arg))
    await _notify_owner_cmd(bot, owner_id, ".kawaii", partner,
                            "Kawaii-режим форматирования текста.")


async def cmd_love(bot, msg, bc_id, owner_id, arg, partner):
    if not arg:
        await _edit_own(bot, msg, bc_id, "💕 Укажите текст: .love [текст]")
        return
    await _edit_own(bot, msg, bc_id, love(arg), parse_mode="HTML")
    await _notify_owner_cmd(bot, owner_id, ".love", partner,
                            "Оформление текста сердечками.")


async def cmd_sw(bot, msg, bc_id, owner_id, arg, partner):
    if not arg:
        await _edit_own(bot, msg, bc_id, "⌨️ Укажите текст: .sw [текст]")
        return
    await _edit_own(bot, msg, bc_id, switch_layout(arg))


async def cmd_type(bot, msg, bc_id, owner_id, arg, partner):
    if not arg:
        await _edit_own(bot, msg, bc_id, "⌨️ Укажите текст: .type [текст]")
        return
    text = arg[:200]
    key = (bc_id, msg.chat.id)
    now = time.time()
    if now - _type_last.get(key, 0) < 30:
        await _edit_own(bot, msg, bc_id, text)
        return
    _type_last[key] = now
    # Анимация набора: редактируем сообщение посимвольно
    step = max(1, len(text) // 20)  # не более ~20 правок
    shown = ""
    idx = 0
    first = True
    while idx < len(text):
        idx = min(len(text), idx + step)
        shown = text[:idx]
        try:
            if first:
                await bot.edit_message_text(
                    chat_id=msg.chat.id, message_id=msg.message_id,
                    text=shown + " ▌", business_connection_id=bc_id)
                first = False
            else:
                await bot.edit_message_text(
                    chat_id=msg.chat.id, message_id=msg.message_id,
                    text=shown + (" ▌" if idx < len(text) else ""),
                    business_connection_id=bc_id)
        except Exception:
            break
        await asyncio.sleep(0.4)


async def cmd_check(bot, msg, bc_id, owner_id, arg, partner):
    doc = msg.document or (msg.photo[-1] if msg.photo else None) or \
        msg.video or msg.audio or msg.voice
    if not doc:
        await bot.send_message(
            owner_id, "🔍 Отправьте файл с подписью .check для анализа.")
        return
    file_id = doc.file_id
    file_name = getattr(doc, "file_name", None) or "без имени"
    mime = getattr(doc, "mime_type", None) or "неизвестно"
    size = getattr(doc, "file_size", 0) or 0
    size_mb = size / (1024 * 1024)

    report = (
        "🔍 <b>Анализ файла</b>\n\n"
        f"📄 Имя: <code>{escape(file_name)}</code>\n"
        f"🏷 Тип (MIME): <code>{escape(mime)}</code>\n"
        f"📦 Размер: {size_mb:.2f} МБ\n"
    )
    if size > 20 * 1024 * 1024:
        report += "\n⚠️ Файл больше 20 МБ — содержимое не загружалось."
    else:
        # Для текстовых файлов — показать превью
        if mime.startswith("text") or (file_name.endswith(
                (".txt", ".log", ".json", ".csv", ".md", ".py"))):
            try:
                tf = await bot.get_file(file_id)
                buf = io.BytesIO()
                await bot.download_file(tf.file_path, buf)
                content = buf.getvalue().decode("utf-8", errors="replace")
                preview = content[:500]
                report += (f"\n📝 <b>Превью:</b>\n<code>"
                           f"{escape(preview)}</code>")
                if len(content) > 500:
                    report += f"\n… (ещё {len(content) - 500} символов)"
            except Exception as e:
                report += f"\n⚠️ Не удалось прочитать: {escape(str(e))}"
    await bot.send_message(owner_id, report, parse_mode="HTML")


async def cmd_afk(bot, msg, bc_id, owner_id, arg, partner):
    if arg.strip().lower() in ("off", "выкл", "выключить"):
        await storage.remove_afk(owner_id)
        await _edit_own(bot, msg, bc_id, "✅ AFK-режим выключен.")
        return
    reason = arg.strip() or "не указана"
    await storage.set_afk(owner_id, reason)
    await _edit_own(bot, msg, bc_id, f"💤 AFK включён. Причина: {reason}")


async def cmd_info(bot, msg, bc_id, owner_id, arg, partner):
    target = msg.reply_to_message.from_user if msg.reply_to_message else None
    if not target:
        target = msg.from_user
    if not target:
        await bot.send_message(owner_id, "ℹ️ Не удалось определить пользователя.")
        return
    premium = "✅ Да" if getattr(target, "is_premium", False) else "❌ Нет"
    info = (
        f"ℹ️ <b>Публичная информация</b> {pe('satellite')}\n\n"
        f"👤 Имя: {escape(target.first_name or '')}"
        f" {escape(target.last_name or '')}\n"
    )
    if target.username:
        info += f"🔗 Username: @{escape(target.username)}\n"
    info += (
        f"🆔 ID: <code>{target.id}</code>\n"
        f"💎 Premium: {premium}\n"
        f"🌐 Язык: {escape(getattr(target, 'language_code', '') or 'неизвестно')}\n\n"
        "<i>Показаны только публичные данные из Telegram API.</i>"
    )
    await bot.send_message(owner_id, info, parse_mode="HTML")


async def cmd_nk(bot, msg, bc_id, owner_id, arg, partner):
    url = None
    for attempt in range(2):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://nekos.best/api/v2/neko",
                                 timeout=aiohttp.ClientTimeout(total=10)) as r:
                    data = await r.json()
                    url = data["results"][0]["url"]
                    break
        except Exception as e:
            logger.warning("nekos.best попытка %d: %s", attempt, e)
            await asyncio.sleep(1)
    if url:
        try:
            await bot.send_photo(msg.chat.id, url, business_connection_id=bc_id)
        except Exception:
            await bot.send_message(msg.chat.id, url, business_connection_id=bc_id)
    else:
        await bot.send_message(
            owner_id, "😺 API неко-тян временно недоступен, попробуйте позже.")


async def cmd_short(bot, msg, bc_id, owner_id, arg, partner):
    from bot.utils.text_tools import summarize
    from bot.utils.stt import transcribe, stt_available
    reply = msg.reply_to_message
    if not reply:
        await bot.send_message(
            owner_id, "📝 Ответьте на голосовое или текстовое "
                      "сообщение командой .short")
        return
    if reply.voice or reply.audio:
        media = reply.voice or reply.audio
        dur = getattr(media, "duration", 0)
        if stt_available():
            await bot.send_message(owner_id, "📝 Расшифровываю голосовое…")
            try:
                tf = await bot.get_file(media.file_id)
                buf = io.BytesIO()
                await bot.download_file(tf.file_path, buf)
                text = await transcribe(buf.getvalue())
            except Exception as e:
                logger.warning("STT error: %s", e)
                text = None
            if text:
                out = f"📝 <b>Расшифровка ({dur} сек):</b>\n{escape(text)}"
                summary = summarize(text, 2)
                if summary and summary != text:
                    out += f"\n\n🔑 <b>Кратко:</b>\n{escape(summary)}"
                await bot.send_message(owner_id, out, parse_mode="HTML")
            else:
                await bot.send_message(
                    owner_id,
                    f"📝 Голосовое: {dur} сек. Не удалось расшифровать "
                    "(проверьте OPENAI_API_KEY или попробуйте позже).")
        else:
            await bot.send_message(
                owner_id,
                f"📝 Голосовое сообщение: {dur} сек.\n\n"
                "ℹ️ Транскрибация отключена. Чтобы включить, задайте "
                "<code>OPENAI_API_KEY</code> в окружении (используется "
                "Whisper API). Без ключа расшифровка недоступна.",
                parse_mode="HTML")
    elif reply.text:
        t = reply.text
        summary = summarize(t, 3)
        if summary and summary.strip() != t.strip():
            await bot.send_message(
                owner_id,
                f"📝 <b>Краткий пересказ:</b>\n{escape(summary)}\n\n"
                f"<i>(из {len(t)} символов)</i>",
                parse_mode="HTML")
        else:
            await bot.send_message(
                owner_id, "📝 Текст короткий, пересказ не требуется:\n" +
                escape(t), parse_mode="HTML")
    else:
        await bot.send_message(owner_id, "📝 Нечего пересказывать.")


async def cmd_status(bot, msg, bc_id, owner_id, arg, partner):
    if not arg:
        await bot.send_message(
            owner_id, "✏️ Укажите статус: .status [текст]\n"
                      "Для сброса: .status off")
        return
    if arg.strip().lower() in ("off", "выкл", "сброс"):
        await bot.send_message(owner_id, "✏️ Статус сброшен.")
        return
    # Что ДЕЙСТВИТЕЛЬНО можем: красиво оформить исходящее сообщение владельца.
    styled = f"『 {arg.strip()} 』"
    ok = await _edit_own(bot, msg, bc_id, styled)
    note = (
        f"{pe('writing')} <b>Про имя профиля:</b> Bot API Telegram не позволяет менять "
        "имя/статус аккаунта — это ограничение самого Telegram, а не бота. "
        "Поменять имя можно только вручную: Настройки → Изменить профиль.\n\n"
        f"✅ Оформил текущее сообщение в стиле статуса: {escape(styled)}"
        if ok else
        "ℹ️ Bot API не позволяет менять имя аккаунта Telegram. "
        "Установите имя/статус вручную в настройках профиля."
    )
    await bot.send_message(owner_id, note, parse_mode="HTML")


async def cmd_gifts(bot, msg, bc_id, owner_id, arg, partner):
    text = f"{pe('gift')} <b>Подарки Telegram</b>\n\n"
    try:
        gifts = await bot.get_available_gifts()
        items = getattr(gifts, "gifts", [])
        if items:
            for g in items[:20]:
                star = getattr(g, "star_count", "?")
                text += f"• {getattr(g, 'sticker', '').emoji if getattr(g, 'sticker', None) else '🎁'} — {star} ⭐\n"
        else:
            text += "Список подарков пуст."
    except Exception as e:
        logger.warning("get_available_gifts: %s", e)
        text += ("Информация о подарках недоступна через этот бот. "
                 "Подарки доступны в официальном клиенте Telegram "
                 "(значок 🎁 в профиле).")
    await bot.send_message(owner_id, text, parse_mode="HTML")


async def cmd_fv(bot, msg, bc_id, owner_id, arg, partner):
    reply = msg.reply_to_message
    if not reply or not reply.voice:
        await bot.send_message(
            owner_id, "🎤 Ответьте на голосовое сообщение командой .fv")
        return
    from bot.utils.audio import ffmpeg_available
    # Запоминаем голосовое для последующей обработки по нажатию кнопки
    fv_pending[owner_id] = reply.voice.file_id
    note = ""
    if not ffmpeg_available():
        note = ("\n\n⚠️ ffmpeg не найден на сервере — обработка не сработает. "
                "Установите его (Termux: <code>pkg install ffmpeg</code>; "
                "Docker-образ уже содержит ffmpeg).")
    await bot.send_message(
        owner_id, "🎤 Выберите эффект голоса:" + note,
        reply_markup=keyboards.fv_kb(), parse_mode="HTML")


async def cmd_story(bot, msg, bc_id, owner_id, arg, partner):
    reply = msg.reply_to_message
    photo = None
    if reply and reply.photo:
        photo = reply.photo[-1]
    elif msg.photo:
        photo = msg.photo[-1]
    if not photo:
        await bot.send_message(
            owner_id, "🖼 Ответьте на фотографию командой .story")
        return
    try:
        from PIL import Image, ImageEnhance
        tf = await bot.get_file(photo.file_id)
        buf = io.BytesIO()
        await bot.download_file(tf.file_path, buf)
        buf.seek(0)
        img = Image.open(buf).convert("RGB")
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = ImageEnhance.Color(img).enhance(1.4)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=90)
        out.seek(0)
        from aiogram.types import BufferedInputFile
        await bot.send_photo(
            owner_id, BufferedInputFile(out.read(), "story.jpg"),
            caption="🖼 Арт из вашего фото готов!")
    except ImportError:
        await bot.send_message(owner_id, "🖼 Требуется библиотека Pillow.")
    except Exception as e:
        await bot.send_message(owner_id, f"🖼 Ошибка обработки: {escape(str(e))}")


_CLOCK_EMOJI = {
    0: "🕛", 1: "🕐", 2: "🕑", 3: "🕒", 4: "🕓", 5: "🕔",
    6: "🕕", 7: "🕖", 8: "🕗", 9: "🕘", 10: "🕙", 11: "🕚",
}


async def cmd_time(bot, msg, bc_id, owner_id, arg, partner):
    from datetime import timedelta, timezone
    # Опциональный аргумент — смещение UTC, напр. ".time +3" или ".time -5"
    tz = timezone.utc
    off_txt = "UTC"
    a = arg.strip().replace(" ", "")
    if a:
        try:
            hours = int(a)
            if -14 <= hours <= 14:
                tz = timezone(timedelta(hours=hours))
                off_txt = f"UTC{'+' if hours >= 0 else ''}{hours}"
        except ValueError:
            pass
    else:
        tz = None  # локальное время сервера
        off_txt = "локальное"
    now = datetime.now(tz)
    clock = _CLOCK_EMOJI.get(now.hour % 12, "🕐")
    formatted = f"{clock} {now.strftime('%H:%M')} ({off_txt})"
    ok = await _edit_own(bot, msg, bc_id, formatted)
    if not ok:
        await bot.send_message(
            owner_id,
            f"{formatted}\n\nℹ️ Не удалось вписать время в сообщение "
            "(возможно, сообщение уже не редактируется).")


async def cmd_yars(bot, msg, bc_id, owner_id, arg, partner):
    reply = msg.reply_to_message
    photo = None
    if reply and reply.photo:
        photo = reply.photo[-1]
    if not photo:
        await bot.send_message(
            owner_id, "🔎 Ответьте на изображение командой .yars")
        return
    try:
        tf = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{tf.file_path}"
        yandex = f"https://yandex.ru/images/search?rpt=imageview&url={file_url}"
        await bot.send_message(
            owner_id,
            "🔎 <b>Реверс-поиск изображения</b>\n\n"
            f'<a href="{yandex}">🔗 Открыть поиск в Yandex Images</a>\n\n'
            "Там вы найдёте источник и похожие фото.",
            parse_mode="HTML")
    except Exception as e:
        await bot.send_message(owner_id, f"🔎 Ошибка: {escape(str(e))}")


_GOSU_SURPRISES = [
    "🎉 Сюрприз! Ты сегодня великолепен!",
    "✨ Держи щепотку блеска за отличный день!",
    "🎁 Виртуальный подарок специально для тебя!",
    "🦄 Единорог передаёт тебе привет!",
    "🍀 Немного удачи тебе сегодня!",
    "🎊 Та-дам! Хорошего настроения!",
    "🚀 Ты космос!",
    "💫 Магия в твоих руках!",
]


async def cmd_gosu(bot, msg, bc_id, owner_id, arg, partner):
    import random
    surprise = random.choice(_GOSU_SURPRISES)
    await _edit_own(bot, msg, bc_id, f"{surprise} {pe_random('reward')}",
                    parse_mode="HTML")


async def cmd_lq(bot, msg, bc_id, owner_id, arg, partner):
    reply = msg.reply_to_message
    photo = None
    if reply and reply.photo:
        photo = reply.photo[-1]
    if not photo:
        await bot.send_message(owner_id, "📉 Ответьте на фото командой .lq")
        return
    try:
        level = int(arg.strip()) if arg.strip().isdigit() else 3
    except Exception:
        level = 3
    level = max(1, min(10, level))
    try:
        from PIL import Image
        tf = await bot.get_file(photo.file_id)
        buf = io.BytesIO()
        await bot.download_file(tf.file_path, buf)
        buf.seek(0)
        img = Image.open(buf).convert("RGB")
        # снижаем разрешение и качество
        scale = level / 10  # 1->0.1, 10->1.0
        scale = max(0.1, scale)
        w, h = img.size
        small = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
        img2 = small.resize((w, h))
        out = io.BytesIO()
        quality = max(5, level * 8)
        img2.save(out, format="JPEG", quality=quality)
        out.seek(0)
        from aiogram.types import BufferedInputFile
        await bot.send_photo(
            msg.chat.id, BufferedInputFile(out.read(), "lq.jpg"),
            caption=f"📉 Шакал-уровень: {level}/10",
            business_connection_id=bc_id)
    except ImportError:
        await bot.send_message(owner_id, "📉 Требуется библиотека Pillow.")
    except Exception as e:
        await bot.send_message(owner_id, f"📉 Ошибка: {escape(str(e))}")


# ══════════ ИНСТРУМЕНТЫ (новые команды) ══════════

def _reply_or_arg(msg: Message, arg: str) -> str:
    """Взять аргумент, либо текст сообщения-ответа."""
    if arg:
        return arg
    r = getattr(msg, "reply_to_message", None)
    if r is not None:
        return (r.text or r.caption or "")
    return ""


async def cmd_qr(bot, msg, bc_id, owner_id, arg, partner):
    from bot.utils import tools
    data = _reply_or_arg(msg, arg)
    if not data.strip():
        await bot.send_message(owner_id, "Использование: <code>.qr текст/ссылка</code>",
                               parse_mode="HTML")
        return
    try:
        png = tools.make_qr_png(data)
    except Exception as e:
        await bot.send_message(owner_id, f"QR: {escape(str(e))}")
        return
    from aiogram.types import BufferedInputFile
    photo = BufferedInputFile(png, filename="qr.png")
    try:
        await bot.send_photo(chat_id=msg.chat.id, photo=photo,
                             caption="QR-код", business_connection_id=bc_id or None)
    except Exception:
        await bot.send_photo(chat_id=owner_id, photo=photo, caption="QR-код")


async def cmd_tr(bot, msg, bc_id, owner_id, arg, partner):
    from bot.utils import tools
    src = _reply_or_arg(msg, arg)
    lang, text = tools.parse_tr_args(src)
    if not text.strip():
        await bot.send_message(owner_id,
                               "Использование: <code>.tr en текст</code>",
                               parse_mode="HTML")
        return
    try:
        translated = await tools.translate(text, lang)
    except Exception as e:
        logger.warning("Ошибка перевода: %s", e)
        await bot.send_message(owner_id, "Не удалось перевести (сервис недоступен).")
        return
    await _edit_own(bot, msg, bc_id, translated)


async def cmd_calc(bot, msg, bc_id, owner_id, arg, partner):
    from bot.utils import tools
    expr = _reply_or_arg(msg, arg)
    try:
        res = tools.calc(expr)
        out = f"{expr.strip()} = {res}"
    except Exception as e:
        out = f"Ошибка: {e}"
    await _edit_own(bot, msg, bc_id, out)


async def cmd_pass(bot, msg, bc_id, owner_id, arg, partner):
    from bot.utils import tools
    try:
        length = int(arg.strip()) if arg.strip() else 16
    except ValueError:
        length = 16
    pwd = tools.gen_password(length)
    # Пароль отправляем ТОЛЬКО в личку владельцу, не в чат.
    await bot.send_message(
        owner_id,
        f"{pe('key')} Пароль ({len(pwd)} симв.):\n<code>{escape(pwd)}</code>",
        parse_mode="HTML")


async def cmd_mock(bot, msg, bc_id, owner_id, arg, partner):
    from bot.utils import tools
    text = _reply_or_arg(msg, arg)
    await _edit_own(bot, msg, bc_id, tools.mock_case(text) or "—")


async def cmd_rev(bot, msg, bc_id, owner_id, arg, partner):
    from bot.utils import tools
    text = _reply_or_arg(msg, arg)
    await _edit_own(bot, msg, bc_id, tools.reverse_text(text) or "—")


async def cmd_roll(bot, msg, bc_id, owner_id, arg, partner):
    from bot.utils import tools
    try:
        out = tools.roll(arg)
    except Exception as e:
        out = f"Ошибка: {e}"
    await _edit_own(bot, msg, bc_id, out, parse_mode="HTML")


async def cmd_pick(bot, msg, bc_id, owner_id, arg, partner):
    from bot.utils import tools
    try:
        out = f"🎲 {tools.pick(arg)}"
    except Exception as e:
        out = f"Ошибка: {e}"
    await _edit_own(bot, msg, bc_id, out)


async def cmd_count(bot, msg, bc_id, owner_id, arg, partner):
    from bot.utils import tools
    text = _reply_or_arg(msg, arg)
    await bot.send_message(owner_id, tools.count_text(text), parse_mode="HTML")


async def cmd_b64(bot, msg, bc_id, owner_id, arg, partner):
    from bot.utils import tools
    parts = arg.split(maxsplit=1)
    if len(parts) < 2:
        await bot.send_message(owner_id,
                               "Использование: <code>.b64 e|d текст</code>",
                               parse_mode="HTML")
        return
    try:
        out = tools.b64(parts[0], parts[1])
    except Exception as e:
        out = f"Ошибка: {e}"
    await _edit_own(bot, msg, bc_id, out)


async def cmd_spoiler(bot, msg, bc_id, owner_id, arg, partner):
    text = _reply_or_arg(msg, arg)
    if not text.strip():
        return
    await _edit_own(bot, msg, bc_id,
                    f"<tg-spoiler>{escape(text)}</tg-spoiler>", parse_mode="HTML")
