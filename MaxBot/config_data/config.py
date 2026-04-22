from dataclasses import dataclass
from environs import Env


@dataclass
class MaxBot:
    bot_token: str
    authorization_key: str


@dataclass
class WebApp:
    host: str
    port: int


@dataclass
class Config:
    max_bot: MaxBot
    webapp: WebApp


def load_config(path: str | None = None) -> Config:
    env = Env()
    env.read_env(path)

    return Config(
        max_bot=MaxBot(
            bot_token=env('BOT_TOKEN'),
            authorization_key=env('AUTHORIZATION_KEY')
        ),
        webapp=WebApp(
            host=env('WEBAPP_HOST', '0.0.0.0'),
            port=env.int('WEBAPP_PORT', 8080)
        )
    )
