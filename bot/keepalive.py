"""Мини HTTP-сервер для health-check / keep-alive.

Нужен, чтобы бесплатные хостинги (Koyeb, Render и т.п.) считали сервис
«живым» веб-сервисом и не выгружали его. Внешний пинг (UptimeRobot каждые
5 минут) держит инстанс тёплым 24/7. Бот при этом работает в обычном
режиме long-polling — вебхук не нужен.
"""
import logging
import os

from aiohttp import web

logger = logging.getLogger("savemod.keepalive")


async def _health(request: web.Request) -> web.Response:
    return web.Response(text="SaveMOD is alive ✅")


async def start_keepalive_server() -> web.AppRunner | None:
    """Запустить health-сервер на порту из переменной PORT (по умолчанию 8000).

    Возвращает AppRunner (чтобы можно было закрыть) или None, если не удалось.
    """
    port_raw = os.getenv("PORT", "8000")
    try:
        port = int(port_raw)
    except ValueError:
        port = 8000

    app = web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)

    runner = web.AppRunner(app)
    try:
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=port)
        await site.start()
        logger.info("Health-сервер запущен на 0.0.0.0:%s (/ и /health)", port)
        return runner
    except Exception as e:  # noqa: BLE001
        logger.warning("Не удалось запустить health-сервер: %s", e)
        return None
