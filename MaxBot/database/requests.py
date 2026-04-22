import aiosqlite
from pathlib import Path
from re import search


DB_PATH = Path(__file__).resolve().with_name('maxbot.db')
CERTIFICATE_TYPES = {'none', 'international', 'russian', 'regional', 'university'}


async def _table_columns(db: aiosqlite.Connection, table_name: str) -> set[str]:
    cursor = await db.execute(f"PRAGMA table_info({table_name})")
    rows = await cursor.fetchall()
    return {row[1] for row in rows}


async def ensure_schema() -> None:
    """Мигрирует SQLite-схему под актуальные возможности мини-приложения."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = OFF")

        cursor = await db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'events'"
        )
        events_sql_row = await cursor.fetchone()
        events_sql = events_sql_row[0] if events_sql_row else ''
        event_columns = await _table_columns(db, 'events')

        required_event_columns = {
            'inventory',
            'duration_hours',
            'certificate_type',
        }
        needs_events_rebuild = (
            'cancelled' not in events_sql
            or not required_event_columns.issubset(event_columns)
        )

        if needs_events_rebuild:
            await _rebuild_events_table(db, event_columns)

        registration_columns = await _table_columns(db, 'event_registrations')
        if 'confirmed_at' not in registration_columns:
            await db.execute(
                "ALTER TABLE event_registrations ADD COLUMN confirmed_at TEXT"
            )

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_registrations_event_user
            ON event_registrations(event_id, user_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_volunteer_history_event_user
            ON volunteer_history(event_id, user_id)
        """)
        await db.commit()
        await db.execute("PRAGMA foreign_keys = ON")

    await refresh_expired_events()


async def _rebuild_events_table(
        db: aiosqlite.Connection,
        existing_columns: set[str]
) -> None:
    await db.execute("DROP TABLE IF EXISTS events_new")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS events_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            event_date TEXT NOT NULL,
            event_time TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'other' CHECK (category IN (
                'ecology','social','education','sport','culture','animals','other'
            )),
            volunteers_needed INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
                'open','closed','completed','cancelled'
            )),
            organizer_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            inventory TEXT NOT NULL DEFAULT '',
            duration_hours INTEGER NOT NULL DEFAULT 0,
            certificate_type TEXT NOT NULL DEFAULT 'none' CHECK (certificate_type IN (
                'none','international','russian','regional','university'
            )),
            FOREIGN KEY (organizer_id) REFERENCES users(id)
        )
    """)

    def column_or_default(column: str, default_sql: str) -> str:
        return column if column in existing_columns else default_sql

    await db.execute(f"""
        INSERT INTO events_new (
            id, title, description, event_date, event_time,
            city, address, category, volunteers_needed, status,
            organizer_id, created_at, updated_at,
            inventory, duration_hours, certificate_type
        )
        SELECT
            id,
            title,
            description,
            event_date,
            event_time,
            city,
            address,
            category,
            volunteers_needed,
            CASE
                WHEN status IN ('open','closed','completed','cancelled') THEN status
                ELSE 'open'
            END,
            organizer_id,
            created_at,
            updated_at,
            {column_or_default('inventory', "''")},
            {column_or_default('duration_hours', '0')},
            CASE
                WHEN {column_or_default('certificate_type', "'none'")} IN (
                    'none','international','russian','regional','university'
                )
                THEN {column_or_default('certificate_type', "'none'")}
                ELSE 'none'
            END
        FROM events
    """)
    await db.execute("DROP TABLE events")
    await db.execute("ALTER TABLE events_new RENAME TO events")


async def refresh_expired_events(db: aiosqlite.Connection | None = None) -> None:
    """Закрывает прошедшие события, чтобы волонтёры больше не могли записаться."""
    query = """
        UPDATE events
        SET status = 'completed',
            updated_at = datetime('now')
        WHERE status IN ('open', 'closed')
          AND datetime(
                event_date || ' ' ||
                CASE
                    WHEN COALESCE(event_time, '') = '' THEN '23:59'
                    ELSE event_time
                END
          ) < datetime('now', 'localtime')
    """

    if db is not None:
        await db.execute(query)
        return

    async with aiosqlite.connect(DB_PATH) as connection:
        await connection.execute(query)
        await connection.commit()

async def record_user(data: dict[str, str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (max_user_id, name, surname, patronymic, city, birth_date, phone, role)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['max_user_id'],
            data['name'],
            data['surname'],
            data['patronymic'],
            data['current_city'],
            data['birth_date'],
            data['phone'],
            'volunteer'
        ))
        await db.commit()


async def update_user_data(data: dict[str, str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users
            SET name = ?,
                surname = ?,
                patronymic = ?,
                city = ?,
                birth_date = ?,
                phone = ?
            WHERE max_user_id = ?
        """, (
            data['name'],
            data['surname'],
            data['patronymic'],
            data['current_city'],
            data['birth_date'],
            data['phone'],
            data['max_user_id']
        ))
        await db.commit()


async def check_user_id(max_user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT
                max_user_id
            FROM users
            WHERE
                max_user_id = ?
        """, (max_user_id,)) as cursor:
            data = await cursor.fetchone()
    return bool(data)


async def check_organizer(max_user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT
                role
            FROM users
            WHERE
                max_user_id = ?
        """, (max_user_id,)) as cursor:
            data = await cursor.fetchone()
    return False if not data else data[0] == 'organizer'


async def get_role(max_user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT
                role
            FROM users
            WHERE
                max_user_id = ?
        """, (max_user_id,)) as cursor:
            data = await cursor.fetchone()
    return data[0]


async def get_user_info(max_user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT
                name,
                surname,
                patronymic,
                birth_date,
                city,
                phone,
                rating                      
            FROM users
            WHERE
                max_user_id = ?
        """, (max_user_id,)) as cursor:
            data = await cursor.fetchone()
    
    info = f"""
👤 Ифнормация о профиле
    
🪪 ФИО: {data[1]} {data[0]} {data[2]}
📅 Дата рождения: {data[3]}
🏙️ Город: {data[4]}
📞 Номер телефона: {data[5]}
⭐ Рейтинг: {data[6]}
""" 
    return info


async def get_nearest_event(max_user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT
                CONCAT('Информация о пользователе: ', CONCAT_WS(
                    '; ',
                    CONCAT('Имя: ', u.name),
                    CONCAT('Фамилия: ', u.surname),
                    CONCAT('Отчесвто: ', u.patronymic),
                    CONCAT('Город: ', u.city),
                    CONCAT('Дата рождения: ', u.birth_date)
                )) as user_info,
                CONCAT('Информация о мероприятии: ', CONCAT_WS(
                    '; ',
                    CONCAT('Заголовок: ', e.title),
                    CONCAT('Описание: ', e.description),
                    CONCAT('Категория: ', e.category),
                    CONCAT('Город: ', e.city),
                    CONCAT('Адрес: ', e.address),
                    CONCAT('Дата проведения: ', e.event_date),
                    CONCAT('Время проведения: ', e.event_time),
					CONCAT('Инвентарь: ', e.inventory),
					CONCAT('Длительность в часах: ', e.duration_hours),
					CONCAT('Тип сертификата: ', e.certificate_type)
                )) as event_info
            FROM event_registrations er
            JOIN users u
                ON er.user_id = u.id
            JOIN events e
                ON er.event_id = e.id
            WHERE
                u.max_user_id = ?
                AND e.status = 'open'
				AND e.event_date = (SELECT MIN(event_date)
									FROM event_registrations inner_er
									JOIN events inner_e ON inner_er.event_id = inner_e.id
									WHERE inner_er.user_id = er.user_id)
        """, (max_user_id,)) as cursor:
            data = await cursor.fetchone()
    
    return str(data)


async def get_completed_events(max_user_id: int) -> str:
    await refresh_expired_events()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
			SELECT
                e.id,
                e.title,
                e.event_date
			FROM events e
			JOIN users u
				ON e.organizer_id = u.id
				AND u.role = 'organizer'
			WHERE
                u.max_user_id = ?
				AND status = 'completed'
        """, (max_user_id,)) as cursor:
            rows = await cursor.fetchall()
    
    return None if not rows else [dict(row) for row in rows]


async def get_completed_events_and_user_info(max_user_id: int, event_id: int) -> str:
    await refresh_expired_events()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
			SELECT
                u.name,
                u.surname,
                u.patronymic,
                u.city,
                u.birth_date,
                e.title,
                e.description,
                e.category,
                e.city,
                e.address,
				e.category,
                e.event_date,
                e.event_time,
				e.volunteers_needed,
                e.duration_hours,
                e.inventory,
                e.certificate_type
			FROM events e
			JOIN users u
				ON e.organizer_id = u.id
				AND u.role = 'organizer'
			WHERE
                u.max_user_id = ?
                AND e.id = ?
				AND status = 'completed'
        """, (max_user_id, event_id)) as cursor:
            rows = await cursor.fetchone()
    
    return 'Нет данных' if not rows else str(dict(rows))


# Функции для мини-приложения
async def get_user_data(max_user_id: int) -> dict | None:
    """Получает данные пользователя как словарь для мини-приложения."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT id, max_user_id, name, surname, patronymic,
                   city, birth_date, phone, role, rating
            FROM users
            WHERE max_user_id = ?
        """, (max_user_id,)) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    return dict(row)


async def get_events(city: str = '', max_user_id: int | None = None) -> list[dict]:
    """Получает список мероприятий. Если указан город — фильтрует."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await refresh_expired_events(db)
        await db.commit()
        user_id = None
        registration_projection = "0 as is_registered"
        query_params: list[int | str] = []

        if max_user_id is not None:
            cursor = await db.execute(
                "SELECT id FROM users WHERE max_user_id = ?", (max_user_id,)
            )
            user_row = await cursor.fetchone()
            if user_row:
                user_id = user_row['id']
                registration_projection = """
                    EXISTS(
                        SELECT 1 FROM event_registrations er
                        WHERE er.event_id = e.id AND er.user_id = ?
                    ) as is_registered
                """
                query_params.append(user_id)

        event_deadline_filter = """
            e.status IN ('open', 'closed')
            AND datetime(
                e.event_date || ' ' ||
                CASE
                    WHEN COALESCE(e.event_time, '') = '' THEN '23:59'
                    ELSE e.event_time
                END
            ) >= datetime('now', 'localtime')
        """
        visibility_filter = "e.status = 'open'"
        visibility_params: list[int] = []
        if user_id is not None:
            visibility_filter = """
                (
                    e.status = 'open'
                    OR EXISTS(
                        SELECT 1
                        FROM event_registrations er_visible
                        WHERE er_visible.event_id = e.id
                          AND er_visible.user_id = ?
                    )
                )
            """
            visibility_params.append(user_id)

        if city:
            cursor = await db.execute(f"""
                SELECT e.*,
                    (SELECT COUNT(*) FROM event_registrations er WHERE er.event_id = e.id) as volunteers_registered,
                    u.name || ' ' || u.surname as organizer_name,
                    {registration_projection}
                FROM events e
                LEFT JOIN users u ON u.id = e.organizer_id
                WHERE (e.city = ? OR e.city = '')
                  AND {event_deadline_filter}
                  AND {visibility_filter}
                ORDER BY e.event_date ASC
            """, tuple(query_params + [city] + visibility_params))
        else:
            cursor = await db.execute(f"""
                SELECT e.*,
                    (SELECT COUNT(*) FROM event_registrations er WHERE er.event_id = e.id) as volunteers_registered,
                    u.name || ' ' || u.surname as organizer_name,
                    {registration_projection}
                FROM events e
                LEFT JOIN users u ON u.id = e.organizer_id
                WHERE {event_deadline_filter}
                  AND {visibility_filter}
                ORDER BY e.event_date ASC
            """, tuple(query_params + visibility_params))

        rows = await cursor.fetchall()

    events = [dict(r) for r in rows]
    for event in events:
        event['is_registered'] = bool(event.get('is_registered'))

    return events


async def get_user_history(max_user_id: int) -> list[dict]:
    """Получает историю волонтёрства пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT vh.id, vh.user_id, vh.event_id, vh.hours, vh.completed_at,
                   e.title, e.event_date, e.category
            FROM volunteer_history vh
            JOIN events e ON e.id = vh.event_id
            JOIN users u ON u.id = vh.user_id
            WHERE u.max_user_id = ?
            ORDER BY vh.completed_at DESC
        """, (max_user_id,))
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_user_events(max_user_id: int) -> list[dict]:
    """Получает мероприятия, созданные организатором."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await refresh_expired_events(db)
        await db.commit()

        # Сначала получаем id пользователя по max_user_id
        cursor = await db.execute(
            "SELECT id FROM users WHERE max_user_id = ?", (max_user_id,)
        )
        user_row = await cursor.fetchone()
        if not user_row:
            return []

        user_id = user_row['id']

        cursor = await db.execute("""
            SELECT e.*,
                (SELECT COUNT(*) FROM event_registrations er WHERE er.event_id = e.id) as volunteers_registered
            FROM events e
            WHERE e.organizer_id = ?
            ORDER BY e.event_date DESC
        """, (user_id,))
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_event_registration_count(db: aiosqlite.Connection, event_id: int) -> int:
    cursor = await db.execute(
        "SELECT COUNT(*) FROM event_registrations WHERE event_id = ?", (event_id,)
    )
    count_row = await cursor.fetchone()
    return count_row[0]


async def join_event(max_user_id: int, event_id: int) -> dict[str, str | int | bool]:
    """Записывает волонтёра на мероприятие и возвращает подробный статус."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await refresh_expired_events(db)
        await db.commit()

        cursor = await db.execute(
            "SELECT id, role FROM users WHERE max_user_id = ?", (max_user_id,)
        )
        user_row = await cursor.fetchone()
        if not user_row:
            return {
                'ok': False,
                'code': 'user_not_found',
                'message': 'Пользователь не найден.'
            }

        user_id = user_row['id']
        if user_row['role'] != 'volunteer':
            return {
                'ok': False,
                'code': 'not_volunteer',
                'message': 'Записываться на мероприятия могут только волонтёры.'
            }

        cursor = await db.execute(
            """
            SELECT id, status, volunteers_needed, organizer_id,
                   event_date, event_time
            FROM events
            WHERE id = ?
            """,
            (event_id,)
        )
        event_row = await cursor.fetchone()
        if not event_row:
            return {
                'ok': False,
                'code': 'event_not_found',
                'message': 'Мероприятие не найдено.'
            }

        if event_row['organizer_id'] == user_id:
            return {
                'ok': False,
                'code': 'own_event',
                'message': 'Нельзя записаться на собственное мероприятие.'
            }

        cursor = await db.execute(
            "SELECT id FROM event_registrations WHERE user_id = ? AND event_id = ?",
            (user_id, event_id)
        )
        if await cursor.fetchone():
            return {
                'ok': False,
                'code': 'already_joined',
                'message': 'Вы уже записаны на это мероприятие.',
                'volunteers_registered': await get_event_registration_count(db, event_id),
                'event_status': event_row['status']
            }

        if event_row['status'] == 'cancelled':
            return {
                'ok': False,
                'code': 'event_cancelled',
                'message': 'Мероприятие отменено организатором.',
                'volunteers_registered': await get_event_registration_count(db, event_id),
                'event_status': event_row['status']
            }

        if event_row['status'] == 'completed':
            return {
                'ok': False,
                'code': 'event_completed',
                'message': 'Мероприятие уже завершено.',
                'volunteers_registered': await get_event_registration_count(db, event_id),
                'event_status': event_row['status']
            }

        if event_row['status'] != 'open':
            return {
                'ok': False,
                'code': 'event_closed',
                'message': 'Запись на мероприятие уже закрыта.',
                'volunteers_registered': await get_event_registration_count(db, event_id),
                'event_status': event_row['status']
            }

        volunteers_registered = await get_event_registration_count(db, event_id)
        if volunteers_registered >= event_row['volunteers_needed']:
            await db.execute(
                "UPDATE events SET status = 'closed' WHERE id = ? AND status = 'open'",
                (event_id,)
            )
            await db.commit()
            return {
                'ok': False,
                'code': 'limit_reached',
                'message': 'Свободных мест больше нет.',
                'volunteers_registered': volunteers_registered,
                'event_status': 'closed'
            }

        await db.execute(
            "INSERT INTO event_registrations (user_id, event_id) VALUES (?, ?)",
            (user_id, event_id)
        )

        volunteers_registered += 1
        event_status = event_row['status']
        if volunteers_registered >= event_row['volunteers_needed']:
            event_status = 'closed'
            await db.execute(
                "UPDATE events SET status = 'closed' WHERE id = ?",
                (event_id,)
            )

        await db.commit()

    return {
        'ok': True,
        'code': 'joined',
        'message': 'Вы успешно записались на мероприятие!',
        'event_id': event_id,
        'volunteers_registered': volunteers_registered,
        'event_status': event_status
    }


async def create_event(data: dict) -> int:
    """Создаёт новое мероприятие и возвращает его id."""
    async with aiosqlite.connect(DB_PATH) as db:
        organizer_id = data.get('organizer_id')

        if data.get('organizer_max_user_id'):
            cursor = await db.execute("""
                SELECT id, role
                FROM users
                WHERE max_user_id = ?
            """, (int(data['organizer_max_user_id']),))
            organizer_row = await cursor.fetchone()
            if not organizer_row or organizer_row[1] != 'organizer':
                raise ValueError('Организатор не найден.')
            organizer_id = organizer_row[0]

        if not organizer_id:
            raise ValueError('organizer_id is required')

        duration_hours = max(0, int(data.get('duration_hours') or 0))
        certificate_type = data.get('certificate_type') or 'none'
        if certificate_type not in CERTIFICATE_TYPES:
            certificate_type = 'none'

        cursor = await db.execute("""
            INSERT INTO events (title, description, event_date, event_time,
                                city, address, category, volunteers_needed, organizer_id,
                                inventory, duration_hours, certificate_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['title'],
            data['description'],
            data['event_date'],
            data['event_time'],
            data['city'],
            data['address'],
            data['category'],
            data['volunteers_needed'],
            organizer_id,
            data.get('inventory', ''),
            duration_hours,
            certificate_type
        ))
        await db.commit()
        return cursor.lastrowid


async def cancel_registration(max_user_id: int, event_id: int) -> dict[str, str | int | bool]:
    """Отменяет запись волонтёра на будущее мероприятие."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await refresh_expired_events(db)
        await db.commit()

        cursor = await db.execute(
            "SELECT id, role FROM users WHERE max_user_id = ?",
            (max_user_id,)
        )
        user_row = await cursor.fetchone()
        if not user_row:
            return {'ok': False, 'code': 'user_not_found', 'message': 'Пользователь не найден.'}
        if user_row['role'] != 'volunteer':
            return {'ok': False, 'code': 'not_volunteer', 'message': 'Отменять запись могут только волонтёры.'}

        user_id = user_row['id']
        cursor = await db.execute("""
            SELECT id, status, volunteers_needed
            FROM events
            WHERE id = ?
        """, (event_id,))
        event_row = await cursor.fetchone()
        if not event_row:
            return {'ok': False, 'code': 'event_not_found', 'message': 'Мероприятие не найдено.'}

        if event_row['status'] == 'completed':
            return {
                'ok': False,
                'code': 'event_completed',
                'message': 'Нельзя отменить запись на уже завершённое мероприятие.'
            }

        cursor = await db.execute("""
            SELECT id, confirmed_at
            FROM event_registrations
            WHERE user_id = ? AND event_id = ?
        """, (user_id, event_id))
        registration_row = await cursor.fetchone()
        if not registration_row:
            return {'ok': False, 'code': 'not_registered', 'message': 'Вы не записаны на это мероприятие.'}
        if registration_row['confirmed_at']:
            return {
                'ok': False,
                'code': 'already_confirmed',
                'message': 'Участие уже подтверждено, запись отменить нельзя.'
            }

        await db.execute(
            "DELETE FROM event_registrations WHERE id = ?",
            (registration_row['id'],)
        )

        volunteers_registered = await get_event_registration_count(db, event_id)
        event_status = event_row['status']
        if event_status == 'closed' and volunteers_registered < event_row['volunteers_needed']:
            event_status = 'open'
            await db.execute(
                "UPDATE events SET status = 'open', updated_at = datetime('now') WHERE id = ?",
                (event_id,)
            )

        await db.commit()

    return {
        'ok': True,
        'code': 'registration_cancelled',
        'message': 'Запись отменена.',
        'event_id': event_id,
        'volunteers_registered': volunteers_registered,
        'event_status': event_status,
        'is_registered': False
    }


async def get_event_volunteers(max_user_id: int, event_id: int) -> dict:
    """Возвращает список волонтёров, записанных на мероприятие организатора."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await refresh_expired_events(db)
        await db.commit()

        owner_result = await _check_event_owner(db, max_user_id, event_id)
        if not owner_result['ok']:
            return owner_result

        cursor = await db.execute("""
            SELECT
                u.id,
                u.max_user_id,
                u.name,
                u.surname,
                u.patronymic,
                u.city,
                u.phone,
                er.registered_at,
                er.confirmed_at,
                EXISTS(
                    SELECT 1
                    FROM volunteer_history vh
                    WHERE vh.user_id = u.id AND vh.event_id = er.event_id
                ) AS in_history
            FROM event_registrations er
            JOIN users u ON u.id = er.user_id
            WHERE er.event_id = ?
            ORDER BY er.registered_at ASC
        """, (event_id,))
        rows = await cursor.fetchall()

    volunteers = [dict(row) for row in rows]
    for volunteer in volunteers:
        volunteer['is_confirmed'] = bool(volunteer.get('confirmed_at') or volunteer.get('in_history'))

    return {'ok': True, 'code': 'volunteers_loaded', 'volunteers': volunteers}


async def cancel_event(max_user_id: int, event_id: int) -> dict[str, str | int | bool]:
    """Отменяет мероприятие, если пользователь является его организатором."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await refresh_expired_events(db)
        await db.commit()

        owner_result = await _check_event_owner(db, max_user_id, event_id)
        if not owner_result['ok']:
            return owner_result

        event_row = owner_result['event']
        if event_row['status'] == 'completed':
            return {
                'ok': False,
                'code': 'event_completed',
                'message': 'Завершённое мероприятие отменить нельзя.'
            }
        if event_row['status'] == 'cancelled':
            return {
                'ok': False,
                'code': 'already_cancelled',
                'message': 'Мероприятие уже отменено.',
                'event_status': 'cancelled'
            }

        await db.execute("""
            UPDATE events
            SET status = 'cancelled',
                updated_at = datetime('now')
            WHERE id = ?
        """, (event_id,))
        await db.commit()

    return {
        'ok': True,
        'code': 'event_cancelled',
        'message': 'Мероприятие отменено.',
        'event_id': event_id,
        'event_status': 'cancelled'
    }


async def confirm_event_participation(
        organizer_max_user_id: int,
        event_id: int,
        volunteer_max_user_id: int | None = None,
        qr_payload: str | None = None
) -> dict[str, str | int | bool | dict]:
    """Подтверждает участие волонтёра в событии по QR-коду."""
    if volunteer_max_user_id is None and qr_payload:
        volunteer_max_user_id = extract_max_user_id_from_qr_payload(qr_payload)

    if not volunteer_max_user_id:
        return {
            'ok': False,
            'code': 'invalid_qr',
            'message': 'Не удалось распознать QR-код волонтёра.'
        }

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await refresh_expired_events(db)
        await db.commit()

        owner_result = await _check_event_owner(db, organizer_max_user_id, event_id)
        if not owner_result['ok']:
            return owner_result

        event_row = owner_result['event']
        if event_row['status'] == 'cancelled':
            return {
                'ok': False,
                'code': 'event_cancelled',
                'message': 'Нельзя подтверждать участие в отменённом мероприятии.'
            }

        cursor = await db.execute("""
            SELECT id, max_user_id, name, surname, patronymic, role
            FROM users
            WHERE max_user_id = ?
        """, (volunteer_max_user_id,))
        volunteer_row = await cursor.fetchone()
        if not volunteer_row or volunteer_row['role'] != 'volunteer':
            return {
                'ok': False,
                'code': 'volunteer_not_found',
                'message': 'Волонтёр не найден.'
            }

        cursor = await db.execute("""
            SELECT id, confirmed_at
            FROM event_registrations
            WHERE event_id = ? AND user_id = ?
        """, (event_id, volunteer_row['id']))
        registration_row = await cursor.fetchone()
        if not registration_row:
            return {
                'ok': False,
                'code': 'not_registered',
                'message': 'Этот волонтёр не записан на мероприятие.'
            }

        cursor = await db.execute("""
            SELECT id
            FROM volunteer_history
            WHERE event_id = ? AND user_id = ?
        """, (event_id, volunteer_row['id']))
        history_row = await cursor.fetchone()

        if not registration_row['confirmed_at']:
            await db.execute("""
                UPDATE event_registrations
                SET confirmed_at = datetime('now')
                WHERE id = ?
            """, (registration_row['id'],))

        if not history_row:
            await db.execute("""
                INSERT INTO volunteer_history (user_id, event_id, hours)
                VALUES (?, ?, ?)
            """, (
                volunteer_row['id'],
                event_id,
                int(event_row['duration_hours'] or 0)
            ))

        await db.commit()

    return {
        'ok': True,
        'code': 'participation_confirmed',
        'message': 'Участие волонтёра подтверждено.',
        'event_id': event_id,
        'volunteer': {
            'max_user_id': volunteer_row['max_user_id'],
            'name': volunteer_row['name'],
            'surname': volunteer_row['surname'],
            'patronymic': volunteer_row['patronymic']
        }
    }


async def _check_event_owner(
        db: aiosqlite.Connection,
        max_user_id: int,
        event_id: int
) -> dict:
    cursor = await db.execute("""
        SELECT id, role
        FROM users
        WHERE max_user_id = ?
    """, (max_user_id,))
    user_row = await cursor.fetchone()
    if not user_row:
        return {'ok': False, 'code': 'user_not_found', 'message': 'Пользователь не найден.'}
    if user_row['role'] != 'organizer':
        return {'ok': False, 'code': 'not_organizer', 'message': 'Доступно только организаторам.'}

    cursor = await db.execute("""
        SELECT *
        FROM events
        WHERE id = ?
    """, (event_id,))
    event_row = await cursor.fetchone()
    if not event_row:
        return {'ok': False, 'code': 'event_not_found', 'message': 'Мероприятие не найдено.'}
    if event_row['organizer_id'] != user_row['id']:
        return {'ok': False, 'code': 'forbidden', 'message': 'Это мероприятие принадлежит другому организатору.'}

    return {'ok': True, 'user': user_row, 'event': event_row}


def extract_max_user_id_from_qr_payload(payload: str) -> int | None:
    text = str(payload or '').strip()
    if text.isdigit():
        return int(text)

    match = search(r"['\"]?max_user_id['\"]?\s*[:=]\s*'?(\d+)'?", text)
    if match:
        return int(match.group(1))

    return None
