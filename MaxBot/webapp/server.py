"""
Веб-сервер для мини-приложения.
Раздаёт статические файлы (HTML/CSS/JS) и предоставляет API для работы с БД.
"""

from aiohttp import web
from pathlib import Path
from database.requests import (
    ensure_schema,
    get_user_data,
    get_role,
    get_events,
    get_user_history,
    get_user_events,
    join_event,
    cancel_registration,
    create_event,
    get_event_volunteers,
    cancel_event,
    confirm_event_participation
)

BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / 'MIni app for MAX'
NO_CACHE_HEADERS = {
    'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
    'Pragma': 'no-cache',
    'Expires': '0',
}


def create_app() -> web.Application:
    """Создаёт и настраивает aiohttp-приложение."""
    if not STATIC_DIR.exists():
        raise FileNotFoundError(f'Mini app directory not found: {STATIC_DIR}')

    app = web.Application()

    # CORS middleware
    app.middlewares.append(cors_middleware)

    # API маршруты
    app.router.add_get('/api/user', handle_get_user)
    app.router.add_get('/api/events', handle_get_events)
    app.router.add_get('/api/history', handle_get_history)
    app.router.add_post('/api/join', handle_join_event)
    app.router.add_post('/api/cancel-registration', handle_cancel_registration)
    app.router.add_post('/api/events', handle_create_event)
    app.router.add_get('/api/events/{event_id:\\d+}/volunteers', handle_get_event_volunteers)
    app.router.add_post('/api/events/{event_id:\\d+}/cancel', handle_cancel_event)
    app.router.add_post('/api/events/{event_id:\\d+}/confirm', handle_confirm_participation)

    # Статические файлы (CSS, JS)
    app.router.add_get('/style.css', handle_static)
    app.router.add_get('/app.js', handle_static)

    # Главная страница мини-приложения
    app.router.add_get('/', handle_index)
    app.router.add_get('', handle_index)

    return app


@web.middleware
async def cors_middleware(request, handler):
    """CORS middleware для разрешения кроссдоменных запросов."""
    if request.method == 'OPTIONS':
        response = web.Response()
    else:
        response = await handler(request)

    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# ============ Обработчики статических файлов ============

async def handle_index(request: web.Request) -> web.Response:
    """Отдаёт главную страницу мини-приложения."""
    index_path = STATIC_DIR / 'index.html'
    return web.FileResponse(index_path, headers=NO_CACHE_HEADERS)


async def handle_static(request: web.Request) -> web.Response:
    """Отдаёт статические файлы (CSS, JS)."""
    filename = request.path.lstrip('/')
    file_path = STATIC_DIR / filename
    if file_path.exists():
        return web.FileResponse(file_path, headers=NO_CACHE_HEADERS)
    return web.Response(status=404, text='Not found')


# ============ API обработчики ============

async def handle_get_user(request: web.Request) -> web.Response:
    """
    GET /api/user?max_user_id=...
    Возвращает данные пользователя, мероприятия, историю.
    """
    max_user_id = request.query.get('max_user_id')
    if not max_user_id:
        return web.json_response({'error': 'max_user_id is required'}, status=400)

    try:
        max_user_id = int(max_user_id)
    except ValueError:
        return web.json_response({'error': 'invalid max_user_id'}, status=400)

    user = await get_user_data(max_user_id)
    if not user:
        return web.json_response({'error': 'user not found'}, status=404)

    role = await get_role(max_user_id)
    events_list = await get_events(user.get('city', ''), max_user_id=max_user_id)
    history_list = await get_user_history(max_user_id)

    result = {
        'role': role,
        'user': user,
        'events': events_list,
        'history': history_list,
    }

    if role == 'organizer':
        result['my_events'] = await get_user_events(max_user_id)

    return web.json_response(result)


async def handle_get_events(request: web.Request) -> web.Response:
    """GET /api/events?city=..."""
    city = request.query.get('city', '')
    max_user_id = request.query.get('max_user_id')

    if max_user_id is not None:
        try:
            max_user_id = int(max_user_id)
        except ValueError:
            return web.json_response({'error': 'invalid max_user_id'}, status=400)

    events_list = await get_events(city, max_user_id=max_user_id)
    return web.json_response(events_list)


async def handle_get_history(request: web.Request) -> web.Response:
    """GET /api/history?max_user_id=..."""
    max_user_id = request.query.get('max_user_id')
    if not max_user_id:
        return web.json_response({'error': 'max_user_id is required'}, status=400)

    try:
        max_user_id = int(max_user_id)
    except ValueError:
        return web.json_response({'error': 'invalid max_user_id'}, status=400)

    history_list = await get_user_history(max_user_id)
    return web.json_response(history_list)


async def handle_join_event(request: web.Request) -> web.Response:
    """POST /api/join  body: {max_user_id, event_id}"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({'error': 'invalid JSON'}, status=400)

    max_user_id = data.get('max_user_id')
    event_id = data.get('event_id')

    if not max_user_id or not event_id:
        return web.json_response({'error': 'max_user_id and event_id required'}, status=400)

    try:
        max_user_id = int(max_user_id)
        event_id = int(event_id)
    except ValueError:
        return web.json_response({'error': 'invalid max_user_id or event_id'}, status=400)

    result = await join_event(max_user_id, event_id)
    payload = {k: v for k, v in result.items() if k != 'ok'}

    if result['ok']:
        return web.json_response({'status': 'ok', **payload})

    status_by_code = {
        'user_not_found': 404,
        'event_not_found': 404,
        'not_volunteer': 403,
        'own_event': 403,
        'already_joined': 409,
        'event_closed': 409,
        'event_cancelled': 409,
        'event_completed': 409,
        'limit_reached': 409,
    }
    return web.json_response(
        {'status': 'error', 'error': payload.get('message'), **payload},
        status=status_by_code.get(payload.get('code'), 400)
    )


async def handle_cancel_registration(request: web.Request) -> web.Response:
    """POST /api/cancel-registration  body: {max_user_id, event_id}"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({'error': 'invalid JSON'}, status=400)

    max_user_id = data.get('max_user_id')
    event_id = data.get('event_id')
    if not max_user_id or not event_id:
        return web.json_response({'error': 'max_user_id and event_id required'}, status=400)

    try:
        max_user_id = int(max_user_id)
        event_id = int(event_id)
    except ValueError:
        return web.json_response({'error': 'invalid max_user_id or event_id'}, status=400)

    result = await cancel_registration(max_user_id, event_id)
    payload = {k: v for k, v in result.items() if k != 'ok'}
    if result['ok']:
        return web.json_response({'status': 'ok', **payload})

    status_by_code = {
        'user_not_found': 404,
        'event_not_found': 404,
        'not_volunteer': 403,
        'not_registered': 409,
        'already_confirmed': 409,
        'event_completed': 409,
    }
    return web.json_response(
        {'status': 'error', 'error': payload.get('message'), **payload},
        status=status_by_code.get(payload.get('code'), 400)
    )


async def handle_create_event(request: web.Request) -> web.Response:
    """POST /api/events  body: {event data}"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({'error': 'invalid JSON'}, status=400)

    required = ['title', 'description', 'event_date', 'event_time',
                'city', 'address', 'volunteers_needed', 'category']
    for field in required:
        if field not in data:
            return web.json_response({'error': f'{field} is required'}, status=400)

    if not data.get('organizer_max_user_id') and not data.get('organizer_id'):
        return web.json_response({'error': 'organizer_max_user_id is required'}, status=400)

    try:
        event_id = await create_event(data)
    except ValueError as error:
        return web.json_response({'error': str(error)}, status=403)

    return web.json_response({'status': 'ok', 'event_id': event_id})


async def handle_get_event_volunteers(request: web.Request) -> web.Response:
    """GET /api/events/{event_id}/volunteers?max_user_id=..."""
    max_user_id = request.query.get('max_user_id')
    event_id = request.match_info.get('event_id')
    if not max_user_id:
        return web.json_response({'error': 'max_user_id is required'}, status=400)

    try:
        max_user_id = int(max_user_id)
        event_id = int(event_id)
    except ValueError:
        return web.json_response({'error': 'invalid max_user_id or event_id'}, status=400)

    result = await get_event_volunteers(max_user_id, event_id)
    payload = {k: v for k, v in result.items() if k != 'ok'}
    if result['ok']:
        return web.json_response({'status': 'ok', **payload})

    return _json_error(payload)


async def handle_cancel_event(request: web.Request) -> web.Response:
    """POST /api/events/{event_id}/cancel  body: {max_user_id}"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({'error': 'invalid JSON'}, status=400)

    max_user_id = data.get('max_user_id')
    event_id = request.match_info.get('event_id')
    if not max_user_id:
        return web.json_response({'error': 'max_user_id is required'}, status=400)

    try:
        max_user_id = int(max_user_id)
        event_id = int(event_id)
    except ValueError:
        return web.json_response({'error': 'invalid max_user_id or event_id'}, status=400)

    result = await cancel_event(max_user_id, event_id)
    payload = {k: v for k, v in result.items() if k != 'ok'}
    if result['ok']:
        return web.json_response({'status': 'ok', **payload})

    return _json_error(payload)


async def handle_confirm_participation(request: web.Request) -> web.Response:
    """POST /api/events/{event_id}/confirm  body: {max_user_id, volunteer_max_user_id|qr_payload}"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({'error': 'invalid JSON'}, status=400)

    max_user_id = data.get('max_user_id')
    volunteer_max_user_id = data.get('volunteer_max_user_id')
    qr_payload = data.get('qr_payload')
    event_id = request.match_info.get('event_id')

    if not max_user_id:
        return web.json_response({'error': 'max_user_id is required'}, status=400)

    try:
        max_user_id = int(max_user_id)
        event_id = int(event_id)
        if volunteer_max_user_id:
            volunteer_max_user_id = int(volunteer_max_user_id)
    except ValueError:
        return web.json_response({'error': 'invalid max_user_id, volunteer_max_user_id or event_id'}, status=400)

    result = await confirm_event_participation(
        organizer_max_user_id=max_user_id,
        event_id=event_id,
        volunteer_max_user_id=volunteer_max_user_id,
        qr_payload=qr_payload
    )
    payload = {k: v for k, v in result.items() if k != 'ok'}
    if result['ok']:
        return web.json_response({'status': 'ok', **payload})

    return _json_error(payload)


def _json_error(payload: dict) -> web.Response:
    status_by_code = {
        'user_not_found': 404,
        'event_not_found': 404,
        'volunteer_not_found': 404,
        'not_organizer': 403,
        'forbidden': 403,
        'event_cancelled': 409,
        'event_completed': 409,
        'already_cancelled': 409,
        'invalid_qr': 400,
        'not_registered': 409,
    }
    return web.json_response(
        {'status': 'error', 'error': payload.get('message'), **payload},
        status=status_by_code.get(payload.get('code'), 400)
    )


async def start_webapp(host: str = '0.0.0.0', port: int = 8080):
    """Запускает веб-сервер."""
    await ensure_schema()
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    # print(f'Mini app started: http://{host}:{port}')
    return runner
