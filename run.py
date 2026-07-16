"""SaveMOD — точка входа. 24/7 long-polling."""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import BOT_TOKEN, OWNER_ID
from bot import storage
from bot.keepalive import start_keepalive_server
from bot.handlers import business, callbacks, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("savemod")

# Маркер сборки — по нему видно, какой билд реально запущен на хосте.
# Если в логе НЕ видно этой строки после git pull + restart — крутится старый код.
BUILD = "2026-07-17 buttons-color+diag"


async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не задан! Укажите его в .env или переменной окружения.")
        sys.exit(1)
    if not OWNER_ID:
        logger.warning("OWNER_ID не задан — админ-функции будут недоступны.")

    await storage.init_db()
    logger.info("База данных инициализирована.")

    # Health-сервер для keep-alive на бесплатных хостингах (Koyeb/Render).
    # Бот при этом работает в обычном long-polling — вебхук не требуется.
    keepalive_runner = await start_keepalive_server()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    # Порядок: admin (команды /start /admin, приём текста) → callbacks → business
    dp.include_router(admin.router)
    dp.include_router(callbacks.router)
    dp.include_router(business.router)

    me = await bot.get_me()
    logger.info("=== SaveMOD BUILD: %s ===", BUILD)
    logger.info("Бот запущен: @%s (id=%s) can_connect_to_business=%s",
                me.username, me.id,
                getattr(me, "can_connect_to_business", False))
    if not getattr(me, "can_connect_to_business", False):
        logger.warning(
            "⚠️ can_connect_to_business=False! Включите Business Mode "
            "в @BotFather: /mybots → Bot Settings → Business Mode → Turn on.")

    allowed = [
        "message", "edited_message", "callback_query",
        "business_connection", "business_message",
        "edited_business_message", "deleted_business_messages",
    ]
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot, allowed_updates=allowed)
    finally:
        await bot.session.close()
        if keepalive_runner is not None:
            await keepalive_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановка бота.")
