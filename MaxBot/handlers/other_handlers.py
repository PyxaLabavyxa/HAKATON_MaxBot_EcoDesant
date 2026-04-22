from maxapi import Router
from maxapi.types import MessageCreated, Attachment


router = Router()

# хендлер для ответа на не обрабатываемые сообщения
@router.message_created()
async def process_other_answer(event: MessageCreated) -> Attachment:
    await event.bot.delete_message(event.message.body.mid)
