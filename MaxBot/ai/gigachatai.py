from gigachat import GigaChatAsyncClient
from gigachat.models import Chat, Messages, MessagesRole
from lexicon.lexicon import PROMPTS
from config_data.config import Config, load_config


config: Config = load_config()

client = GigaChatAsyncClient(
    credentials=config.max_bot.authorization_key,
    verify_ssl_certs=False,
    
)

async def volunteer_helper(question: str, user_data: str) -> str:
    payload = Chat(
        messages=[
            Messages(
                role=MessagesRole.SYSTEM,
                content=PROMPTS['volunteer_helper'] + user_data
            ),
            Messages(
                role=MessagesRole.USER,
                content=question
            )
        ]
    )
    response = await client.achat(payload)

    return response.choices[0].message.content


async def create_report(user_data: str) -> str:
    payload = Chat(
        messages=[
            Messages(
                role=MessagesRole.SYSTEM,
                content=PROMPTS['ai_creating_report'] + user_data
            ),
            Messages(
                role=MessagesRole.USER,
                content='Создай отчет'
            )
        ]
    )
    response = await client.achat(payload)

    return response.choices[0].message.content
