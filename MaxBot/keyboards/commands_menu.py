from maxapi import Bot
from maxapi.types.command import BotCommand


async def set_commands_menu(bot: Bot):
    commands = [
        BotCommand(name='start', description='Запустить бота'),
        BotCommand(name='help', description='Помощь по работе с ботом')
    ]
    await bot.set_my_commands(*commands)
