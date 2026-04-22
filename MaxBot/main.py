import asyncio
from maxapi import Bot, Dispatcher
from config_data.config import Config, load_config
from handlers import user_handlers, other_handlers
from keyboards.commands_menu import set_commands_menu
from webapp.server import start_webapp


async def main():
    config: Config = load_config()

    bot = Bot(token=config.max_bot.bot_token)
    dp = Dispatcher()

    await set_commands_menu(bot)

    dp.include_routers(user_handlers.router, other_handlers.router)

    # Запуск веб-сервера для мини-приложения
    webapp_runner = await start_webapp(
        host=config.webapp.host,
        port=config.webapp.port
    )

    try:
        await bot.delete_webhook()
        await dp.start_polling(bot)
    finally:
        await webapp_runner.cleanup()


asyncio.run(main())
