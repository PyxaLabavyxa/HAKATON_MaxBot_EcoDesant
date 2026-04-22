from maxapi import Router, F
from maxapi.types import BotStarted, MessageCreated, CommandStart, Command, MessageCallback
from maxapi.enums import ParseMode
from maxapi.context import MemoryContext
from lexicon.lexicon import LEXICON
from states.states import FSMMainMenu, FSMFillForm, FSMGigaChat, FSMQrCode
from ai.gigachatai import volunteer_helper, create_report
from database.requests import (
    record_user,
    check_user_id,
    get_user_info,
    update_user_data,
    check_organizer,
    get_nearest_event,
    get_completed_events_and_user_info
)
from keyboards.inline import (
    inline_main_menu,
    profile_info,
    inline_rols,
    contact_button,
    send_location,
    inline_yesno,
    inline_begin,
    inline_back,
    inline_volunteer_helper_questions,
    inline_completed_events,
    inline_to_main_menu
)
from services.service import (
    extract_contact,
    check_full_name,
    get_address_by_coords,
    get_similar_city,
    check_date,
    convert_to_standart_date,
    get_qr
)


router = Router()

# хендлер срабатывает при нажатии кнопки "Начать" и отправляет пользователю приветствие и инлайн-кнопки
@router.bot_started()
async def process_bot_start_answer(event: BotStarted, context: MemoryContext):
    if await check_user_id(event.from_user.user_id):
        await event.bot.send_message(
            chat_id=event.chat_id,
            text=LEXICON['main_menu'],
            attachments=[await inline_main_menu(event)]
        )

        await context.set_state(FSMMainMenu.main_page)
    else:
        await event.bot.send_message(
            chat_id=event.chat_id,
            text=LEXICON['bot_started'],
            attachments=[inline_rols()]
        )

        await context.set_state(FSMFillForm.begin)


# хендлеры для команд:
@router.message_created(CommandStart())
async def process_command_start(event: MessageCreated, context: MemoryContext):
    if await check_user_id(event.from_user.user_id):
        await event.message.answer(
            text=LEXICON['main_menu'],
            attachments=[await inline_main_menu(event)]
        )

        await context.set_state(FSMMainMenu.main_page)
    else:
        await event.message.answer(
            text=LEXICON['bot_started'],
            attachments=[inline_rols()]
        )

        await context.set_state(FSMFillForm.begin)


@router.message_created(Command('help'))
async def process_command_help(event: MessageCreated,):
    await event.message.answer(text=LEXICON['help'])


# хендлеры для взаимодействием с главным меню:
@router.message_callback(FSMMainMenu.main_page, F.callback.payload == 'profile')
async def process_send_profile_info(event: MessageCallback, context: MemoryContext):
    await event.message.edit(
        text=await get_user_info(event.from_user.user_id),
        attachments=[await profile_info(event.from_user.user_id)]
    )

    await context.set_state(FSMMainMenu.profile_page)


@router.message_callback(FSMMainMenu.main_page, F.callback.payload == 'volunteer_ai')
async def process_volunteer_ai(event: MessageCallback, context: MemoryContext):
    await event.message.edit(
        text=LEXICON['volunteer_ai'],
        attachments=[inline_volunteer_helper_questions()]
    )
    
    await context.update_data(message_mid=event.message.body.mid)
    await context.set_state(FSMGigaChat.volunteer_ai)


@router.message_callback(FSMMainMenu.main_page, F.callback.payload == 'organizer_ai')
async def process_organizer_events_choice(event: MessageCallback, context: MemoryContext):
    await event.message.edit(
        text=LEXICON['organizer_ai'],
        attachments=[await inline_completed_events(event.from_user.user_id)]
    )

    await context.set_state(FSMGigaChat.events_choice)


@router.message_callback(FSMMainMenu.become_organizer, F.callback.payload == 'back')
async def process_back_to_send_profile_info(event: MessageCallback, context: MemoryContext):
    await event.message.edit(
        text=await get_user_info(event.from_user.user_id),
        attachments=[await profile_info(event.from_user.user_id)]
    )

    await context.set_state(FSMMainMenu.profile_page)


@router.message_callback(
        FSMMainMenu.profile_page,
        FSMGigaChat.volunteer_ai,
        FSMGigaChat.volunteer_helper,
        FSMGigaChat.events_choice,
        FSMGigaChat.creating_report,
        FSMQrCode.get_qr,
        F.callback.payload == 'back'
)
async def process_main_menu(event: MessageCallback, context: MemoryContext):    
    await event.message.edit(
        text=LEXICON['main_menu'],
        attachments=[await inline_main_menu(event)]
    )

    await context.clear()
    await context.set_state(FSMMainMenu.main_page)


@router.message_callback(
        FSMGigaChat.creating_report,
        FSMGigaChat.volunteer_helper,
        F.callback.payload == 'main_menu'
)
async def process_main_menu_new_message(event: MessageCallback, context: MemoryContext):    
    data = await context.get_data()
    
    await event.bot.edit_message(
        message_id=data['message_mid'],
        attachments=[]
    )
    
    await event.message.answer(
        text=LEXICON['main_menu'],
        attachments=[await inline_main_menu(event)]
    )

    await context.clear()
    await context.set_state(FSMMainMenu.main_page)


@router.message_callback(FSMMainMenu.profile_page, F.callback.payload == 'become_an_organizer')
async def process_become_organizer(event: MessageCallback, context: MemoryContext):
    await event.message.edit(
        text=LEXICON['organizer_not_found'],
        attachments=[inline_back()]
    )

    await context.set_state(FSMMainMenu.become_organizer)


# хендлеры для работы с ИИ-помощником
@router.message_created(FSMGigaChat.volunteer_ai, F.message.body.text)
async def process_volunteer_helper(event: MessageCallback, context: MemoryContext):
    data = await context.get_data()
    question = event.message.body.text
    
    await event.bot.edit_message(
        message_id=data['message_mid'],
        text=LEXICON['volunteer_ai'],
        attachments=[]
    )

    sent_message = await event.message.answer(
        text=await volunteer_helper(
            question=question, 
            user_data=await get_nearest_event(event.from_user.user_id)
        ),
        attachments=[inline_volunteer_helper_questions({question}, button='main_menu')],
        parse_mode=ParseMode.MARKDOWN      
    )

    await context.update_data(
        message_mid=sent_message.message.body.mid,
        response=sent_message.message.body.text,
        questions_used={question}
    )
    await context.set_state(FSMGigaChat.volunteer_helper)


@router.message_created(FSMGigaChat.volunteer_helper, F.message.body.text)
async def process_volunteer_helper_rec(event: MessageCallback, context: MemoryContext):
    data = await context.get_data()
    question = event.message.body.text

    data['questions_used'].add(question)

    await event.bot.edit_message(
        message_id=data['message_mid'],
        text=data['response'],
        attachments=[]
    )

    sent_message = await event.message.answer(
        text=await volunteer_helper(
            question=question, 
            user_data=await get_nearest_event(event.from_user.user_id)
        ),
        attachments=[inline_volunteer_helper_questions(data['questions_used'], button='main_menu')],
        parse_mode=ParseMode.MARKDOWN
    )

    await context.update_data(
        message_mid=sent_message.message.body.mid,
        response=sent_message.message.body.text,
        questions_used=data['questions_used']
    )
    await context.set_state(FSMGigaChat.volunteer_helper)


# хендлеры для работы с ии созданием отчетов
@router.message_callback(FSMGigaChat.events_choice, F.callback.payload.startswith('event_'))
async def process_ai_creating_report(event: MessageCallback, context: MemoryContext):
    await event.message.edit(
        text=LEXICON['loading'],
        attachments=[]
    )
    
    await event.message.edit(
        text=await create_report(
            await get_completed_events_and_user_info(
                max_user_id=event.from_user.user_id,
                event_id=int(event.callback.payload.split('_')[1])
            )
        ),
        attachments=[inline_to_main_menu()],
        parse_mode=ParseMode.MARKDOWN
    )

    await context.update_data(message_mid=event.message.body.mid)
    await context.set_state(FSMGigaChat.creating_report)


# отправка QR-кода
@router.message_callback(FSMMainMenu.main_page, F.callback.payload == 'get_qr')
async def process_get_qr(event: MessageCallback, context: MemoryContext):
    loading = await event.message.edit(
        text=LEXICON['loading'],
        attachments=[]
    )
    
    await event.message.edit(
        text='Твой QR-код',
        attachments=[await get_qr(event.from_user.user_id), inline_back()]
    )

    await context.set_state(FSMQrCode.get_qr)


# хендлеры для работы с регистрацией волонтера
@router.message_callback(FSMFillForm.send_location, F.callback.payload == 'back')
async def process_back_to_choice(event: MessageCallback, context: MemoryContext):
    if 'change_data' in await context.get_data():
        await event.message.edit(
            text=await get_user_info(event.from_user.user_id),
            attachments=[await profile_info(event.from_user.user_id)]
        )

        await context.set_state(FSMMainMenu.profile_page)
    else:
        await event.message.edit(
            text=LEXICON['bot_started'],
            attachments=[inline_rols()]
        )

        await context.set_state(FSMFillForm.begin)


@router.message_callback(
        FSMFillForm.begin,
        FSMMainMenu.profile_page,
        (F.callback.payload == 'volunteer') | (F.callback.payload == 'change_profile_data')
)
async def process_inline_location(event: MessageCallback, context: MemoryContext):
    await event.message.edit(
        text=LEXICON['wru'],
        attachments=[send_location()]
    )

    if await context.get_state() == FSMMainMenu.profile_page:
        await context.update_data(change_data=True)

    await context.update_data(message_mid=event.message.body.mid)
    await context.set_state(FSMFillForm.send_location)


@router.message_created(FSMFillForm.send_location, F.message.body.attachments[0].type == 'location')
async def process_location_determination(event: MessageCallback, context: MemoryContext):
    data = await context.get_data()
    await event.bot.delete_message(data['message_mid'])

    location = event.message.body.attachments[0]
    location_info = await get_address_by_coords(location.latitude, location.longitude)

    if location_info:
        await event.message.answer(
            text=f'{LEXICON['your_city']} {location_info['city']}? 📍',
            attachments=[inline_yesno()]
        )

        await context.update_data(city=location_info['city'], message_mid=None)
    else:
        await event.message.answer(text=LEXICON['city_error'])


@router.message_callback(
        FSMFillForm.send_location,
        FSMFillForm.enter_location,
        FSMFillForm.confirm_question,
        F.callback.payload == 'no'
)
async def process_wrong_location(event: MessageCallback, context: MemoryContext):
    await event.message.edit(
        text=LEXICON['enter_city'],
        attachments=[]
    )
    
    await context.set_state(FSMFillForm.enter_location)


@router.message_created(FSMFillForm.enter_location, FSMFillForm.send_location, F.message.body.text)
async def process_enter_location(event: MessageCreated, context: MemoryContext):
    data = await context.get_data()
    message_mid = data['message_mid']

    if message_mid:
        await event.bot.delete_message(message_mid)
    
    similar_city = get_similar_city(event.message.body.text)

    if similar_city[1] == 100:
        await event.message.answer(
            text=LEXICON['current_city']
        )
        
        await context.update_data(current_city=similar_city[0].capitalize())
        await context.set_state(FSMFillForm.fill_full_name)
    elif similar_city[1] > 0:
        await event.message.answer(
            text=f'Вы имели в виду {similar_city[0].capitalize()}?',
            attachments=[inline_yesno()]
        )

        await context.set_state(FSMFillForm.confirm_question)
        await context.update_data(city=similar_city[0].capitalize())
    else:
        await event.message.answer(
            text=LEXICON['incorrect_city'],
        )


@router.message_callback(
        FSMFillForm.enter_location,
        FSMFillForm.send_location,
        FSMFillForm.confirm_question,
        F.callback.payload == 'yes'
)
async def process_full_name(event: MessageCallback, context: MemoryContext):
    await context.set_state(FSMFillForm.fill_full_name)

    data = await context.get_data()

    if 'current_city' not in data:
        await context.update_data(current_city=data['city'], city=None)

    await event.message.edit(
        text=LEXICON['current_city'],
        attachments=[]
    )


@router.message_created(FSMFillForm.fill_full_name, F.message.body.text)
async def process_check_full_name(event: MessageCreated, context: MemoryContext):
    full_name = event.message.body.text
    
    if check_full_name(full_name):
        await event.message.answer(
            text=LEXICON['enter_date']
        )
        surname, name, patronymic = map(str.capitalize, full_name.split())
        await context.update_data(name=name, surname=surname, patronymic=patronymic)

        await context.set_state(FSMFillForm.fill_date)
    else:
        await event.message.answer(
            text=LEXICON['incorrect_name']
        )


@router.message_created(FSMFillForm.fill_date, F.message.body.text)
async def process_check_date(event: MessageCreated, context: MemoryContext):
    message = event.message.body.text

    if check_date(message):
        await context.update_data(birth_date=convert_to_standart_date(message))
        
        sent_message = await event.message.answer(
            text=LEXICON['send_contact'],
            attachments=[contact_button()]
        )

        await context.update_data(message_mid=sent_message.message.body.mid)
        await context.set_state(FSMFillForm.send_phone)
    else:
        await event.message.answer(
            text=LEXICON['incorrect_date']
        )


@router.message_created(FSMFillForm.send_phone, F.message.body.attachments[0].payload.vcf_info)
async def process_catch_contact(event: MessageCreated, context: MemoryContext):
    data = await context.get_data()
    phone = extract_contact(event.message.body.attachments[0].payload.vcf_info)

    await event.bot.edit_message(
        message_id=data['message_mid'],
        text=LEXICON['currect_phone'],
        attachments=[]
    )
    
    data = {k: v for k, v in data.items() if v is not None and k != 'message_mid'}
    missing_data = {'phone': phone, 'max_user_id': event.from_user.user_id}
    
    if 'change_data' in data:
        await update_user_data(data | missing_data)
        await event.message.answer(text='Данные были успешно обновлены ✅')
    else:
        await record_user(data | missing_data)
    
    await context.clear()

    await event.message.answer(
        text=LEXICON['main_menu'],
        attachments=[await inline_main_menu(event)]
    )

    await context.set_state(FSMMainMenu.main_page)


# хендлеры для организатора:
# хедлер, который срабатывает на кнопку "Организатор"
@router.message_callback(FSMFillForm.begin, F.callback.payload == 'organizer')
async def process_callback_organizer(event: MessageCallback, context: MemoryContext):
    if await check_organizer(event.from_user.user_id):
        await event.message.answer(
            text=LEXICON['main_menu'],
            attachments=[await inline_main_menu(event)]
        )

        await context.set_state(FSMMainMenu.main_page)
    else:
        await event.message.edit(
            text=LEXICON['organizer_not_found'] + LEXICON['set_volunteer'],
            attachments=[inline_begin()]
        )
