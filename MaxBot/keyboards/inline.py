from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from database.requests import get_role, get_completed_events
from maxapi.types import (
    CallbackButton,
    RequestContactButton,
    RequestGeoLocationButton,
    OpenAppButton,
    MessageButton
)


inline_button_back = CallbackButton(text='◀️ Назад', payload='back')
inline_button_main_menu = CallbackButton(text='🏠 В главное меню', payload='main_menu')

async def inline_main_menu(event):
    inline_buttons = {
        'volunteer': CallbackButton(text='🤖 ИИ-помощник', payload='volunteer_ai'),
        'organizer': CallbackButton(text='🤖 Создать отчёт', payload='organizer_ai')
    }

    max_user_id = event.from_user.user_id
    role = await get_role(max_user_id)

    builder = InlineKeyboardBuilder()

    builder.add(OpenAppButton(
        text='Открыть мини-приложение',
        payload=str(max_user_id),
        web_app=event.bot.me.username,
        contact_id=event.bot.me.user_id
    ))
    builder.add(inline_buttons[role])
    if role == 'volunteer':
        builder.add(CallbackButton(text='📲 Предъявить QR-код', payload='get_qr'))
    builder.add(CallbackButton(text='👤 Профиль', payload='profile'))

    return builder.adjust(2, 1).as_markup()


def inline_back():
    builder = InlineKeyboardBuilder()
    builder.add(inline_button_back)
    
    return builder.adjust(1).as_markup()


def inline_begin():
    builder = InlineKeyboardBuilder()

    builder.add(CallbackButton(text='✔️ Начать', payload='volunteer'))

    return builder.adjust(1).as_markup()


async def profile_info(max_user_id: int):
    builder = InlineKeyboardBuilder()

    builder.add(CallbackButton(text='⚙️ Изменить данные', payload='change_profile_data'))
    if await get_role(max_user_id) == 'volunteer':
        builder.add(CallbackButton(text='💼 Стать организатором', payload='become_an_organizer'))
    builder.add(inline_button_back)

    return builder.adjust(1).as_markup()


def inline_rols():
    builder = InlineKeyboardBuilder()

    builder.add(CallbackButton(text='Организатор', payload='organizer'))
    builder.add(CallbackButton(text='Волонтер', payload='volunteer'))

    return builder.adjust(2).as_markup()


def send_location():
    builder = InlineKeyboardBuilder()

    builder.add(RequestGeoLocationButton(text='Отправить геолокацию'))
    builder.add(inline_button_back)

    return builder.adjust(1).as_markup()


def contact_button():
    builder = InlineKeyboardBuilder()

    builder.add(RequestContactButton(text='📞 Отправить номер'))
    builder.add(inline_button_back)

    return builder.adjust(1).as_markup()


def inline_yesno():
    builder = InlineKeyboardBuilder()

    builder.add(CallbackButton(text='✅ Да', payload='yes'))
    builder.add(CallbackButton(text='❌ Нет', payload='no'))

    return builder.adjust(2).as_markup()


def inline_volunteer_helper_questions(data: set|None = None, button: str = 'back'):
    builder = InlineKeyboardBuilder()
    questions = {
        'Что взять с собой?', 
        'Как подготовиться?',
        'Где проходит акция?', 
        'Что делать на месте?',
        'Правила безопасности'
    }
    buttons = {'back': inline_button_back, 'main_menu': inline_button_main_menu}

    if data is None:
        for question in sorted(questions):
            builder.add(MessageButton(text=question))
    elif len(data) < 5:
        for question in sorted(questions - data):
            builder.add(MessageButton(text=question))
    
    builder.add(buttons[button])

    return builder.adjust(2).as_markup()


def inline_to_main_menu():
    builder = InlineKeyboardBuilder()
    builder.add(CallbackButton(text='🏠 В главное меню', payload='main_menu'))
    return builder.adjust(1).as_markup()


async def inline_completed_events(max_user_id: int):
    builder = InlineKeyboardBuilder()

    events = await get_completed_events(max_user_id)

    if events:
        for event in events:
            builder.add(
                CallbackButton(
                    text=f'{event['title']} 📅 {event['event_date']}',
                    payload=f'event_{event['id']}'
                )
            )

    builder.add(inline_button_back)

    return builder.adjust(1).as_markup()
