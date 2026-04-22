from maxapi.context import State, StatesGroup


class FSMFillForm(StatesGroup):
    begin = State()
    send_location = State()
    enter_location = State()
    confirm_question = State()
    fill_full_name = State()
    fill_date = State()
    fill_password = State()
    send_phone = State()


class FSMMainMenu(StatesGroup):
    main_page = State()
    profile_page = State()
    become_organizer = State()


class FSMGigaChat(StatesGroup):
    volunteer_ai = State()
    volunteer_helper = State()
    events_choice = State()
    creating_report = State()


class FSMQrCode(StatesGroup):
    get_qr = State()
