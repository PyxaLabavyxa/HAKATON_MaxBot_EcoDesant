/**
 * ===========================================
 *  Мини-приложение «Волонтёрство» для MAX
 * ===========================================
 *
 * Это мини-приложение получает данные пользователя
 * через MAX Bridge (window.WebApp) и определяет
 * роль: волонтёр или организатор.
 *
 * Данные пользователя (user_data) передаются ботом
 * при открытии мини-приложения.
 *
 * ── Интеграция с вашим ботом ──
 *
 * При открытии мини-приложения MAX передаёт
 * `window.WebApp.initData` и `window.WebApp.initDataUnsafe`.
 *
 * Ваш бот должен передать JSON-данные пользователя
 * через параметр start_param (deep link) или через
 * ваш собственный API endpoint.
 *
 * Структура данных, которую ожидает приложение:
 * {
 *   role: "volunteer" | "organizer",
 *   user: {
 *     id: number,
 *     max_user_id: number,
 *     name: string,
 *     surname: string,
 *     patronymic: string,
 *     city: string,
 *     birth_date: string,
 *     phone: number,
 *     rating: number
 *   },
 *   events: [...],         // доступные мероприятия
 *   history: [...],        // история (для волонтёров)
 *   my_events: [...]       // мои мероприятия (для организаторов)
 * }
 */

(function () {
    'use strict';

    // ============ Config ============

    /**
     * URL вашего API (бэкенда).
     * Замените на реальный адрес, когда подключите бот.
     *
     * Приложение отправит GET-запрос:
     *   GET {API_BASE_URL}/user?init_data=...
     * и ожидает JSON-ответ описанной выше структуры.
     */
    const API_BASE_URL = getApiBaseUrl();  // URL веб-сервера бота

    // ============ State ============

    let currentUser = null;
    let currentRole = null;  // 'volunteer' | 'organizer'
    let events = [];
    let history = [];
    let myEvents = [];
    let currentPage = null;
    let pageHistory = [];
    let scannerStream = null;
    let scannerFrameId = null;

    // ============ DOM refs ============

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const loadingScreen = $('#loading-screen');
    const app = $('#app');
    const headerTitle = $('#header-title');
    const btnBack = $('#btn-back');
    const userAvatar = $('#user-avatar');
    const toast = $('#toast');
    const toastMessage = $('#toast-message');

    // ============ Mock Data ============

    const MONTHS_SHORT = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];

    const CATEGORY_LABELS = {
        ecology: '🌿 Экология',
        social: '🤝 Социальная помощь',
        education: '📚 Образование',
        sport: '⚽ Спорт',
        culture: '🎭 Культура',
        animals: '🐾 Помощь животным',
        other: '📌 Другое'
    };

    const CERTIFICATE_LABELS = {
        none: 'Не выдаётся',
        international: 'Международный',
        russian: 'Всероссийский',
        regional: 'Региональный',
        university: 'Университетский'
    };

    /**
     * Демо-данные. Используются, если бот не передаёт данные
     * или API_BASE_URL пустой. Замените на реальный API.
     */
    function getMockData() {
        return {
            role: 'volunteer',  // Переключите на 'organizer' для теста
            user: {
                id: 1,
                max_user_id: 123456,
                name: 'Алексей',
                surname: 'Волков',
                patronymic: 'Иванович',
                city: 'Москва',
                birth_date: '1995-06-15',
                phone: 79991234567,
                role: 'volunteer',
                rating: 4.2
            },
            events: [
                {
                    id: 1,
                    title: 'Уборка парка Горького',
                    description: 'Масштабная уборка территории парка. Мы соберём мусор, очистим дорожки и посадим цветы. Присоединяйтесь к нам!',
                    event_date: '2026-05-10',
                    event_time: '10:00',
                    city: 'Москва',
                    address: 'ул. Крымский Вал, 9',
                    category: 'ecology',
                    volunteers_needed: 30,
                    volunteers_registered: 18,
                    status: 'open',
                    organizer_id: 2,
                    organizer_name: 'ЭкоМосква'
                },
                {
                    id: 2,
                    title: 'Помощь приюту для животных',
                    description: 'Поможем приюту «Дружок» с уборкой вольеров, выгулом собак и распределением корма.',
                    event_date: '2026-05-15',
                    event_time: '09:00',
                    city: 'Москва',
                    address: 'ул. Южная, 12',
                    category: 'animals',
                    volunteers_needed: 15,
                    volunteers_registered: 15,
                    status: 'closed',
                    organizer_id: 3,
                    organizer_name: 'Приют Дружок'
                },
                {
                    id: 3,
                    title: 'Донорский день',
                    description: 'Совместная акция по сдаче крови. Все доноры получат памятные подарки и бесплатное питание.',
                    event_date: '2026-05-20',
                    event_time: '08:00',
                    city: 'Москва',
                    address: 'Центр крови, ул. Бакинская, 31',
                    category: 'social',
                    volunteers_needed: 50,
                    volunteers_registered: 32,
                    status: 'open',
                    organizer_id: 4,
                    organizer_name: 'Красный Крест'
                },
                {
                    id: 4,
                    title: 'Мастер-класс для детей',
                    description: 'Проведение творческого мастер-класса по рисованию для детей из детского дома.',
                    event_date: '2026-06-01',
                    event_time: '14:00',
                    city: 'Москва',
                    address: 'Детский центр «Радуга», ул. Зелёная, 5',
                    category: 'education',
                    volunteers_needed: 10,
                    volunteers_registered: 6,
                    status: 'open',
                    organizer_id: 5,
                    organizer_name: 'Фонд «Надежда»'
                }
            ],
            history: [
                {
                    id: 1,
                    user_id: 1,
                    event_id: 10,
                    title: 'Посадка деревьев в Битцевском парке',
                    event_date: '2026-03-22',
                    hours: 5,
                    completed_at: '2026-03-22T18:00:00',
                    category: 'ecology'
                },
                {
                    id: 2,
                    user_id: 1,
                    event_id: 11,
                    title: 'Благотворительный забег',
                    event_date: '2026-02-14',
                    hours: 3,
                    completed_at: '2026-02-14T15:00:00',
                    category: 'sport'
                },
                {
                    id: 3,
                    user_id: 1,
                    event_id: 12,
                    title: 'Сбор вещей для нуждающихся',
                    event_date: '2026-01-20',
                    hours: 4,
                    completed_at: '2026-01-20T16:00:00',
                    category: 'social'
                }
            ],
            my_events: [
                {
                    id: 1,
                    title: 'Уборка парка Горького',
                    description: 'Масштабная уборка территории парка.',
                    event_date: '2026-05-10',
                    event_time: '10:00',
                    city: 'Москва',
                    address: 'ул. Крымский Вал, 9',
                    category: 'ecology',
                    volunteers_needed: 30,
                    volunteers_registered: 18,
                    status: 'open',
                    organizer_id: 1
                },
                {
                    id: 5,
                    title: 'Экологический субботник',
                    description: 'Уборка берега реки Москва.',
                    event_date: '2026-04-05',
                    event_time: '09:00',
                    city: 'Москва',
                    address: 'Набережная Тараса Шевченко',
                    category: 'ecology',
                    volunteers_needed: 20,
                    volunteers_registered: 20,
                    status: 'completed',
                    organizer_id: 1
                }
            ]
        };
    }

    // ============ Init ============

    async function init() {
        try {
            const data = await loadUserData();

            currentRole = data.role;
            currentUser = data.user;
            events = normalizeEventList(data.events || []);
            history = data.history || [];
            myEvents = normalizeEventList(data.my_events || []);

            setupUI();
            setupNavigation();
            setupEventListeners();

            // Show app
            loadingScreen.classList.add('fade-out');
            setTimeout(() => {
                loadingScreen.classList.add('hidden');
                app.classList.remove('hidden');
            }, 400);

        } catch (err) {
            console.error('Init error:', err);
            if (err && err.code === 'registration_required') {
                showRegistrationRequired(err.message);
            } else {
                showLoadError(err && err.message ? err.message : 'Ошибка загрузки данных');
            }
        } finally {
            notifyWebAppReady();
        }
    }

    /**
     * Загрузка данных пользователя.
     *
     * Порядок приоритетов:
     * 1. Если задан API_BASE_URL → делаем запрос к вашему серверу
     *    с передачей initData от MAX Bridge
     * 2. Иначе → используем mock-данные для демонстрации
     *
     * Для продакшена ваш сервер (бот) должен:
     *   - Принять initData
     *   - Проверить подпись (валидация от MAX)
     *   - Найти пользователя в БД
     *   - Вернуть JSON с данными (role, user, events, ...)
     */
    async function loadUserData() {
        const maxUserId = getMaxUserId();

        if (isDemoMode()) {
            return getMockData();
        }

        if (!maxUserId) {
            const error = new Error('MAX не передал id пользователя. Откройте мини-приложение из кнопки в боте.');
            error.code = 'registration_required';
            throw error;
        }

        // Запрос к API бота
        try {
            const response = await fetch(
                `${API_BASE_URL}/api/user?max_user_id=${encodeURIComponent(maxUserId)}`
            );
            if (response.ok) {
                return await response.json();
            }

            const payload = await readJsonResponse(response);
            if (response.status === 404) {
                const error = new Error('Вы ещё не зарегистрированы в боте.');
                error.code = 'registration_required';
                throw error;
            }

            throw new Error(payload.error || payload.message || 'Не удалось загрузить профиль.');
        } catch (error) {
            if (error.code === 'registration_required') {
                throw error;
            }
            console.warn('API request failed:', error);
            throw new Error('Не удалось подключиться к серверу мини-приложения.');
        }
    }

    function isDemoMode() {
        return new URLSearchParams(window.location.search).get('demo') === '1';
    }

    function showRegistrationRequired(message) {
        loadingScreen.classList.add('fade-out');
        setTimeout(() => loadingScreen.classList.add('hidden'), 300);

        app.classList.remove('hidden');
        app.innerHTML = `
            <main class="access-gate">
                <section class="access-card">
                    <div class="access-kicker">ЭкоДесант MAX</div>
                    <h1 class="access-title">Сначала регистрация в боте</h1>
                    <p class="access-text">${escapeHtml(message || 'Чтобы открыть мини-приложение, заполните профиль через команду /start в боте.')}</p>
                    <div class="access-steps">
                        <span>1. Вернитесь в чат с ботом</span>
                        <span>2. Нажмите /start</span>
                        <span>3. Заполните профиль и откройте мини-приложение снова</span>
                    </div>
                    <button class="btn-primary" id="btn-close-access">Вернуться в MAX</button>
                </section>
            </main>
        `;

        $('#btn-close-access')?.addEventListener('click', closeApp);
    }

    function showLoadError(message) {
        loadingScreen.classList.add('fade-out');
        setTimeout(() => loadingScreen.classList.add('hidden'), 300);

        app.classList.remove('hidden');
        app.innerHTML = `
            <main class="access-gate">
                <section class="access-card access-card-error">
                    <div class="access-kicker">Сервер не ответил</div>
                    <h1 class="access-title">Не удалось открыть мини-приложение</h1>
                    <p class="access-text">${escapeHtml(message)}</p>
                    <button class="btn-primary" id="btn-reload-access">Попробовать ещё раз</button>
                </section>
            </main>
        `;

        $('#btn-reload-access')?.addEventListener('click', () => window.location.reload());
    }

    function normalizeEventList(eventsList) {
        return (eventsList || []).map(normalizeEvent);
    }

    function normalizeEvent(event) {
        return {
            ...event,
            volunteers_registered: Number(event.volunteers_registered || 0),
            volunteers_needed: Number(event.volunteers_needed || 0),
            duration_hours: Number(event.duration_hours || 0),
            inventory: event.inventory || '',
            certificate_type: event.certificate_type || 'none',
            status: event.status || 'open',
            is_registered: Boolean(event.is_registered)
        };
    }

    function getApiBaseUrl() {
        const urlParams = new URLSearchParams(window.location.search);
        const apiBaseUrl = urlParams.get('api_base_url');

        if (apiBaseUrl) {
            return apiBaseUrl.replace(/\/$/, '');
        }

        return window.location.origin.replace(/\/$/, '');
    }

    function getMaxUserId() {
        const bridgeData = window.WebApp && window.WebApp.initDataUnsafe
            ? window.WebApp.initDataUnsafe
            : null;

        const startParam = normalizeMaxUserId(bridgeData && bridgeData.start_param);
        if (startParam) {
            return startParam;
        }

        const bridgeUserId = normalizeMaxUserId(
            bridgeData && bridgeData.user ? bridgeData.user.id : null
        );
        if (bridgeUserId) {
            return bridgeUserId;
        }

        try {
            if (window.WebApp && window.WebApp.initData) {
                const params = new URLSearchParams(window.WebApp.initData);
                const initDataUserId = normalizeMaxUserId(
                    params.get('start_param') || params.get('payload') || params.get('max_user_id')
                );
                if (initDataUserId) {
                    return initDataUserId;
                }
            }
        } catch (e) {
            console.log('MAX Bridge initData is not available:', e);
        }

        const urlParams = new URLSearchParams(window.location.search);
        return normalizeMaxUserId(
            urlParams.get('start_param') || urlParams.get('max_user_id')
        );
    }

    function normalizeMaxUserId(value) {
        if (value === null || value === undefined) {
            return null;
        }

        const normalized = String(value).trim();
        return /^\d+$/.test(normalized) ? normalized : null;
    }

    function notifyWebAppReady() {
        try {
            if (window.WebApp && typeof window.WebApp.ready === 'function') {
                window.WebApp.ready();
            }
        } catch (e) {
            console.warn('WebApp.ready error:', e);
        }
    }

    // ============ UI Setup ============

    function setupUI() {
        if (userAvatar) {
            userAvatar.textContent = getInitials(currentUser.name);
        }

        if (currentRole === 'volunteer') {
            setupVolunteerUI();
        } else {
            setupOrganizerUI();
        }
    }

    function getFullName(user) {
        return [user.surname, user.name, user.patronymic].filter(Boolean).join(' ');
    }

    function formatPhone(phone) {
        const s = String(phone);
        if (s.length === 11) {
            return `+${s[0]} (${s.substring(1,4)}) ${s.substring(4,7)}-${s.substring(7,9)}-${s.substring(9,11)}`;
        }
        return s;
    }

    function setupVolunteerUI() {
        // Show volunteer nav
        $('#nav-volunteer').classList.remove('hidden');

        // Profile card
        const fullName = getFullName(currentUser);
        $('#vol-avatar').textContent = getInitials(fullName);
        $('#vol-name').textContent = fullName;
        $('#vol-events-count').textContent = history.length;
        $('#vol-hours').textContent = history.reduce((sum, h) => sum + (h.hours || 0), 0);
        $('#vol-rating').textContent = '⭐ ' + (currentUser.rating || 0).toFixed(1);

        // Personal info
        $('#vol-full-name').textContent = fullName;
        $('#vol-city').textContent = currentUser.city || '—';
        $('#vol-phone').textContent = currentUser.phone ? formatPhone(currentUser.phone) : '—';
        $('#vol-birth-date').textContent = currentUser.birth_date ? formatBirthDate(currentUser.birth_date) : '—';
        $('#vol-rating-info').textContent = (currentUser.rating || 0).toFixed(1);

        // Badges
        const visibleEvents = getVolunteerVisibleEvents(events);
        const registeredEvents = getVolunteerRegisteredEvents(events);
        $('#vol-available-count').textContent = visibleEvents.length;
        $('#vol-history-count').textContent = history.length;
        $('#vol-registered-count').textContent = registeredEvents.length;

        // Render events
        renderVolunteerEvents(visibleEvents);
        renderVolunteerRegisteredEvents(registeredEvents);
        renderVolunteerRegisteredPreview(registeredEvents);
        renderHistory(history);

        // Show dashboard
        navigateTo('volunteer-dashboard', 'Волонтёрство');
    }

    function setupOrganizerUI() {
        // Show organizer nav
        $('#nav-organizer').classList.remove('hidden');

        // Profile card
        const orgFullName = getFullName(currentUser);
        $('#org-avatar').textContent = getInitials(orgFullName);
        $('#org-name').textContent = orgFullName;
        refreshOrganizerWorkspace();

        // Show dashboard
        navigateTo('organizer-dashboard', 'Волонтёрство');
    }

    // ============ Rendering ============

    function getVolunteerVisibleEvents(eventsList) {
        return (eventsList || []).filter(event => (
            !isEventExpired(event)
            && event.status !== 'completed'
            && event.status !== 'cancelled'
        ));
    }

    function getVolunteerRegisteredEvents(eventsList) {
        return getVolunteerVisibleEvents(eventsList).filter(event => event.is_registered);
    }

    function refreshVolunteerWorkspace() {
        const visibleEvents = getVolunteerVisibleEvents(events);
        const registeredEvents = getVolunteerRegisteredEvents(events);

        $('#vol-available-count').textContent = visibleEvents.length;
        $('#vol-registered-count').textContent = registeredEvents.length;

        renderVolunteerEvents(visibleEvents);
        renderVolunteerRegisteredEvents(registeredEvents);
        renderVolunteerRegisteredPreview(registeredEvents);
    }

    function getOrganizerVisibleEvents(eventsList) {
        return (eventsList || []).filter(event => (
            !isEventExpired(event)
            && event.status !== 'completed'
            && event.status !== 'cancelled'
        ));
    }

    function refreshOrganizerWorkspace() {
        const visibleEvents = getOrganizerVisibleEvents(myEvents);

        $('#org-events-total').textContent = myEvents.length;
        $('#org-volunteers-total').textContent = myEvents.reduce((s, e) => s + (e.volunteers_registered || 0), 0);
        $('#org-active-count').textContent = visibleEvents.filter(e => e.status === 'open').length;
        $('#org-my-events-count').textContent = visibleEvents.length;

        renderOrganizerEvents(visibleEvents);
        renderOrgRecentEvents(visibleEvents.slice(0, 3));
    }

    function renderVolunteerEvents(eventsList) {
        const container = $('#vol-events-list');
        container.innerHTML = '';

        if (eventsList.length === 0) {
            container.innerHTML = renderEmptyState('Нет мероприятий', 'В вашем городе пока нет доступных мероприятий');
            return;
        }

        eventsList.forEach(event => {
            container.appendChild(createEventCard(event, true));
        });
    }

    function renderVolunteerRegisteredEvents(eventsList) {
        const container = $('#vol-registered-list');
        if (!container) {
            return;
        }

        container.innerHTML = '';

        if (eventsList.length === 0) {
            container.innerHTML = renderEmptyState('Нет активных записей', 'Когда вы запишетесь на мероприятие, оно появится здесь');
            return;
        }

        eventsList.forEach(event => {
            container.appendChild(createEventCard(event, true));
        });
    }

    function renderVolunteerRegisteredPreview(eventsList) {
        const container = $('#vol-registered-preview');
        if (!container) {
            return;
        }

        container.innerHTML = '';

        if (eventsList.length === 0) {
            container.innerHTML = '<p class="registered-empty">Вы пока не записаны на активные мероприятия</p>';
            return;
        }

        eventsList.slice(0, 3).forEach(event => {
            const d = parseDate(event.event_date);
            const item = document.createElement('button');
            item.className = 'registered-preview-item';
            item.type = 'button';
            item.innerHTML = `
                <span class="registered-preview-main">
                    <strong>${escapeHtml(event.title)}</strong>
                    <small>${d.day} ${MONTHS_SHORT[d.month]} · ${escapeHtml(event.city || '')}</small>
                </span>
                <span class="event-status ${getStatusClass(event.status)}">${getStatusLabel(event.status)}</span>
            `;
            item.addEventListener('click', () => showEventDetail(event));
            container.appendChild(item);
        });
    }

    function renderHistory(historyList) {
        const container = $('#vol-history-list');
        container.innerHTML = '';

        if (historyList.length === 0) {
            container.innerHTML = renderEmptyState('Пока пусто', 'Вы ещё не участвовали в мероприятиях');
            return;
        }

        historyList.forEach(item => {
            const card = document.createElement('div');
            card.className = 'history-card glass-card';
            const d = parseDate(item.event_date || item.completed_at);
            card.innerHTML = `
                <div class="history-header">
                    <span class="history-title">${escapeHtml(item.title)}</span>
                    <span class="history-date">${d.day} ${MONTHS_SHORT[d.month]}</span>
                </div>
                <div class="history-details">
                    <span class="history-detail-item">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                        ${item.hours} ч.
                    </span>
                    <span class="history-detail-item">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>
                        ${CATEGORY_LABELS[item.category] || item.category}
                    </span>
                </div>
            `;
            container.appendChild(card);
        });
    }

    function renderOrganizerEvents(eventsList) {
        eventsList = getOrganizerVisibleEvents(eventsList);
        const container = $('#org-events-list');
        container.innerHTML = '';

        if (eventsList.length === 0) {
            container.innerHTML = renderEmptyState('Нет актуальных мероприятий', 'Завершённые и отменённые мероприятия здесь не отображаются');
            return;
        }

        eventsList.forEach(event => {
            const card = createEventCard(event, false);
            // Add volunteer count row
            const volRow = document.createElement('div');
            volRow.className = 'org-event-volunteers';
            volRow.innerHTML = `
                <span class="org-vol-label">Записей:</span>
                <span class="org-vol-count">${event.volunteers_registered} / ${event.volunteers_needed}</span>
            `;
            card.querySelector('.event-info').appendChild(volRow);
            container.appendChild(card);
        });
    }

    function renderOrgRecentEvents(eventsList) {
        eventsList = getOrganizerVisibleEvents(eventsList);
        const container = $('#org-recent-events');
        container.innerHTML = '';

        if (eventsList.length === 0) {
            container.innerHTML = '<p style="color: var(--text-muted); font-size: 0.875rem; padding: 8px 0;">Нет актуальных мероприятий</p>';
            return;
        }

        eventsList.forEach(event => {
            const item = document.createElement('div');
            item.className = 'info-item';
            item.style.cursor = 'pointer';
            item.innerHTML = `
                <span class="info-label" style="flex:1; text-align:left; font-weight:500; color: var(--text-primary); font-size: 0.8125rem;">${escapeHtml(event.title)}</span>
                <span class="event-status ${getStatusClass(event.status)}" style="margin:0;">${getStatusLabel(event.status)}</span>
            `;
            item.addEventListener('click', () => showEventDetail(event));
            container.appendChild(item);
        });
    }

    function renderVolunteersPanel(volunteers) {
        if (!volunteers.length) {
            return renderEmptyState('Пока никто не записался', 'Когда волонтёры запишутся, они появятся здесь');
        }

        return `
            <div class="participants-list">
                <h4 class="panel-title">Записавшиеся волонтёры</h4>
                ${volunteers.map(volunteer => {
                    const fullName = [volunteer.surname, volunteer.name, volunteer.patronymic]
                        .filter(Boolean)
                        .join(' ');
                    return `
                        <div class="participant-card">
                            <div class="participant-main">
                                <div class="participant-name">${escapeHtml(fullName || 'Без имени')}</div>
                                <div class="participant-meta">
                                    ${escapeHtml(volunteer.city || 'Город не указан')} · ${escapeHtml(formatPhone(volunteer.phone || ''))}
                                </div>
                                <div class="participant-meta">
                                    Записан: ${escapeHtml(volunteer.registered_at || '—')}
                                </div>
                            </div>
                            <div class="participant-actions">
                                <span class="participant-status ${volunteer.is_confirmed ? 'confirmed' : ''}">
                                    ${volunteer.is_confirmed ? 'Подтверждён' : 'Ожидает'}
                                </span>
                                ${volunteer.is_confirmed ? '' : `
                                <button class="btn-inline" data-confirm-volunteer="${volunteer.max_user_id}">
                                    Подтвердить
                                </button>`}
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }

    function createEventCard(event, clickable) {
        const card = document.createElement('div');
        card.className = 'event-card glass-card';
        const d = parseDate(event.event_date);
        const pct = event.volunteers_needed > 0
            ? Math.min(Math.round((event.volunteers_registered / event.volunteers_needed) * 100), 100)
            : 0;
        const seatsLeft = Math.max((event.volunteers_needed || 0) - (event.volunteers_registered || 0), 0);
        const certificateLabel = CERTIFICATE_LABELS[event.certificate_type] || 'Не выдаётся';

        card.innerHTML = `
            <div class="event-card-topline">
                <div class="event-date-badge">
                    <div class="event-date-day">${d.day}</div>
                    <div class="event-date-month">${MONTHS_SHORT[d.month]}</div>
                </div>
                <span class="event-status ${getStatusClass(event.status)}">${getStatusLabel(event.status)}</span>
            </div>
            <div class="event-info">
                <div class="event-category-pill">${CATEGORY_LABELS[event.category] || event.category}</div>
                <div class="event-title">${escapeHtml(event.title)}</div>
                <div class="event-meta">
                    <span class="event-meta-item">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                        ${escapeHtml(event.city || '')}
                    </span>
                    <span class="event-meta-item">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                        ${event.event_time || ''}
                    </span>
                </div>
                <div class="event-card-tags">
                    <span class="event-tag event-tag-certificate">${escapeHtml(certificateLabel)}</span>
                    <span class="event-tag">${event.duration_hours ? `${event.duration_hours} ч.` : 'Время уточняется'}</span>
                    <span class="event-tag">${seatsLeft > 0 ? `${seatsLeft} мест свободно` : 'Мест нет'}</span>
                </div>
                ${event.inventory ? `<div class="event-inventory-preview">${escapeHtml(event.inventory)}</div>` : ''}
                <div class="event-card-progress">
                    <div class="event-card-progress-track">
                        <div class="event-card-progress-fill" style="width: ${pct}%"></div>
                    </div>
                    <span>${event.volunteers_registered} / ${event.volunteers_needed}</span>
                </div>
            </div>
        `;

        if (clickable) {
            card.addEventListener('click', () => showEventDetail(event));
        } else {
            card.style.cursor = 'pointer';
            card.addEventListener('click', () => showEventDetail(event));
        }

        return card;
    }

    function showEventDetail(event) {
        const container = $('#event-detail-content');
        const d = parseDate(event.event_date);
        const pct = event.volunteers_needed > 0
            ? Math.round((event.volunteers_registered / event.volunteers_needed) * 100)
            : 0;

        container.innerHTML = `
            <div class="event-detail-header">
                <div class="event-detail-category">${CATEGORY_LABELS[event.category] || event.category}</div>
                <h2 class="event-detail-title">${escapeHtml(event.title)}</h2>
                <div class="event-detail-status">
                    <span class="event-status ${getStatusClass(event.status)}">${getStatusLabel(event.status)}</span>
                </div>
            </div>

            <div class="event-detail-info">
                <div class="detail-row">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                    <div class="detail-row-content">
                        <div class="detail-label">Дата и время</div>
                        <div class="detail-value">${d.day} ${MONTHS_SHORT[d.month]} ${d.year}, ${event.event_time || ''}</div>
                    </div>
                </div>
                <div class="detail-row">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                    <div class="detail-row-content">
                        <div class="detail-label">Место</div>
                        <div class="detail-value">${escapeHtml(event.city || '')}, ${escapeHtml(event.address || '')}</div>
                    </div>
                </div>
                ${event.organizer_name ? `
                <div class="detail-row">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                    <div class="detail-row-content">
                        <div class="detail-label">Организатор</div>
                        <div class="detail-value">${escapeHtml(event.organizer_name)}</div>
                    </div>
                </div>` : ''}
                <div class="detail-row">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    <div class="detail-row-content">
                        <div class="detail-label">Длительность</div>
                        <div class="detail-value">${event.duration_hours ? `${event.duration_hours} ч.` : 'Не указана'}</div>
                    </div>
                </div>
                <div class="detail-row">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15l-3.5 2 1-4-3-2.7 4-.3L12 6.5l1.5 3.5 4 .3-3 2.7 1 4z"/><path d="M8 21h8"/></svg>
                    <div class="detail-row-content">
                        <div class="detail-label">Сертификат</div>
                        <div class="detail-value">${CERTIFICATE_LABELS[event.certificate_type] || 'Не выдаётся'}</div>
                    </div>
                </div>
            </div>

            <div class="event-detail-description">
                <h4>Описание</h4>
                <p>${escapeHtml(event.description)}</p>
            </div>

            ${event.inventory ? `
            <div class="event-detail-description">
                <h4>Инвентарь</h4>
                <p>${escapeHtml(event.inventory)}</p>
            </div>` : ''}

            <div class="volunteer-progress">
                <div class="progress-header">
                    <span class="progress-label">Волонтёров</span>
                    <span class="progress-value">${event.volunteers_registered} / ${event.volunteers_needed}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${Math.min(pct, 100)}%"></div>
                </div>
            </div>

            ${currentRole === 'volunteer' ? renderVolunteerEventAction(event) : renderOrganizerEventActions(event)}
        `;

        const joinBtn = container.querySelector('#btn-join-event');
        if (joinBtn) {
            joinBtn.addEventListener('click', () => handleJoinEvent(event));
        }

        const cancelRegistrationBtn = container.querySelector('#btn-cancel-registration');
        if (cancelRegistrationBtn) {
            cancelRegistrationBtn.addEventListener('click', () => handleCancelRegistration(event));
        }

        const loadVolunteersBtn = container.querySelector('#btn-load-volunteers');
        if (loadVolunteersBtn) {
            loadVolunteersBtn.addEventListener('click', () => handleLoadVolunteers(event));
        }

        const cancelEventBtn = container.querySelector('#btn-cancel-event');
        if (cancelEventBtn) {
            cancelEventBtn.addEventListener('click', () => handleCancelEvent(event));
        }

        const scanQrBtn = container.querySelector('#btn-scan-qr');
        if (scanQrBtn) {
            scanQrBtn.addEventListener('click', () => showQrScanner(event));
        }

        navigateTo('event-detail', escapeHtml(event.title));
    }

    function renderEmptyState(title, text) {
        return `
            <div class="empty-state">
                <div class="empty-icon">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                </div>
                <h3 class="empty-title">${title}</h3>
                <p class="empty-text">${text}</p>
            </div>
        `;
    }

    // ============ Navigation ============

    function setupNavigation() {
        // Nav buttons
        $$('.nav-item').forEach(btn => {
            btn.addEventListener('click', () => {
                const page = btn.dataset.page;
                if (page) {
                    pageHistory = [];
                    navigateTo(page, getTitleForPage(page));
                    updateNavActive(btn);
                }
            });
        });

        // Back button
        btnBack.addEventListener('click', () => {
            if (pageHistory.length > 0) {
                const prev = pageHistory.pop();
                showPage(prev.page, prev.title);
                if (pageHistory.length === 0) {
                    btnBack.classList.add('hidden');
                }
            }
        });
    }

    function navigateTo(pageId, title) {
        if (currentPage && currentPage !== pageId) {
            // Save to page history for back navigation
            const isMainPage = pageId.includes('dashboard') || isNavPage(pageId);
            if (!isMainPage && !pageHistory.find(p => p.page === currentPage)) {
                pageHistory.push({ page: currentPage, title: headerTitle.textContent });
            }
            if (isMainPage) {
                pageHistory = [];
            }
        }
        showPage(pageId, title);
        btnBack.classList.toggle('hidden', pageHistory.length === 0);
    }

    function showPage(pageId, title) {
        if (pageId !== 'event-detail') {
            stopQrScanner();
        }

        // Hide all pages
        $$('.page').forEach(p => p.classList.add('hidden'));

        // Show target
        const target = $(`#page-${pageId}`);
        if (target) {
            target.classList.remove('hidden');
            // Re-trigger animation
            target.style.animation = 'none';
            target.offsetHeight;
            target.style.animation = '';
        }

        currentPage = pageId;
        headerTitle.textContent = title || 'Волонтёрство';
    }

    function updateNavActive(activeBtn) {
        const navContainer = activeBtn.closest('.nav-volunteer, .nav-organizer');
        if (navContainer) {
            navContainer.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
            activeBtn.classList.add('active');
        }
    }

    function isNavPage(pageId) {
        const navPages = [
            'volunteer-dashboard', 'volunteer-events', 'volunteer-history',
            'organizer-dashboard', 'organizer-events', 'organizer-create'
        ];
        return navPages.includes(pageId);
    }

    function getTitleForPage(pageId) {
        const titles = {
            'volunteer-dashboard': 'Волонтёрство',
            'volunteer-events': 'Мероприятия',
            'volunteer-registered': 'Мои записи',
            'volunteer-history': 'История',
            'organizer-dashboard': 'Волонтёрство',
            'organizer-events': 'Мои мероприятия',
            'organizer-create': 'Новое мероприятие'
        };
        return titles[pageId] || 'Волонтёрство';
    }

    // ============ Event Listeners ============

    function setupEventListeners() {
        // Accordion toggles
        $$('[data-toggle]').forEach(header => {
            header.addEventListener('click', () => {
                const targetId = header.dataset.toggle;
                const body = $(`#${targetId}`);
                if (body) {
                    body.classList.toggle('collapsed');
                    header.classList.toggle('expanded');

                    // Animate max-height
                    if (!body.classList.contains('collapsed')) {
                        body.style.maxHeight = body.scrollHeight + 'px';
                        body.style.opacity = '1';
                    } else {
                        body.style.maxHeight = '0';
                        body.style.opacity = '0';
                    }
                }
            });
        });

        // Volunteer quick actions
        const btnVolEvents = $('#btn-vol-events');
        if (btnVolEvents) {
            btnVolEvents.addEventListener('click', () => {
                navigateTo('volunteer-events', 'Мероприятия');
                // Sync nav
                const nav = $('#nav-volunteer .nav-item[data-page="volunteer-events"]');
                if (nav) updateNavActive(nav);
            });
        }

        const btnVolHistory = $('#btn-vol-history');
        if (btnVolHistory) {
            btnVolHistory.addEventListener('click', () => {
                navigateTo('volunteer-history', 'История');
                const nav = $('#nav-volunteer .nav-item[data-page="volunteer-history"]');
                if (nav) updateNavActive(nav);
            });
        }

        const btnVolRegisteredAll = $('#btn-vol-registered-all');
        if (btnVolRegisteredAll) {
            btnVolRegisteredAll.addEventListener('click', () => {
                navigateTo('volunteer-registered', 'Мои записи');
            });
        }

        // Organizer quick actions
        const btnOrgEvents = $('#btn-org-events');
        if (btnOrgEvents) {
            btnOrgEvents.addEventListener('click', () => {
                navigateTo('organizer-events', 'Мои мероприятия');
                const nav = $('#nav-organizer .nav-item[data-page="organizer-events"]');
                if (nav) updateNavActive(nav);
            });
        }

        const btnOrgCreate = $('#btn-org-create');
        if (btnOrgCreate) {
            btnOrgCreate.addEventListener('click', () => {
                navigateTo('organizer-create', 'Новое мероприятие');
                const nav = $('#nav-organizer .nav-item[data-page="organizer-create"]');
                if (nav) updateNavActive(nav);
            });
        }

        // FAB create
        const fabCreate = $('#fab-create-event');
        if (fabCreate) {
            fabCreate.addEventListener('click', () => {
                navigateTo('organizer-create', 'Новое мероприятие');
                const nav = $('#nav-organizer .nav-item[data-page="organizer-create"]');
                if (nav) updateNavActive(nav);
            });
        }

        // Search events
        const searchInput = $('#search-events');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const query = e.target.value.toLowerCase().trim();
                const filtered = getVolunteerVisibleEvents(events).filter(ev =>
                    ev.title.toLowerCase().includes(query) ||
                    ev.city.toLowerCase().includes(query) ||
                    (CATEGORY_LABELS[ev.category] || '').toLowerCase().includes(query)
                );
                renderVolunteerEvents(filtered);
            });
        }

        // Create event form
        const createForm = $('#create-event-form');
        if (createForm) {
            createForm.addEventListener('submit', handleCreateEvent);
        }
    }

    // ============ Handlers ============

    async function handleJoinEvent(event) {
        const btn = $('#btn-join-event');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Записываем...';
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/join`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    max_user_id: currentUser.max_user_id,
                    event_id: event.id
                })
            });

            const payload = await readJsonResponse(response);

            if (response.ok) {
                syncEventAfterJoin(event.id, payload);
                showToast(payload.message || 'Вы записались на мероприятие!');
                return;
            }

            syncEventAfterJoin(event.id, payload);
            showToast(payload.error || payload.message || 'Не удалось записаться');
            resetJoinButton(btn);
        } catch (e) {
            console.warn('Join event error:', e);
            showToast('Ошибка сети');
            resetJoinButton(btn);
        }
    }

    async function handleCancelRegistration(event) {
        if (!window.confirm('Отменить запись на это мероприятие?')) {
            return;
        }

        const btn = $('#btn-cancel-registration');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Отменяем...';
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/cancel-registration`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    max_user_id: currentUser.max_user_id,
                    event_id: event.id
                })
            });

            const payload = await readJsonResponse(response);
            syncEventAfterRegistrationChange(event.id, payload);

            if (response.ok) {
                showToast(payload.message || 'Запись отменена');
                return;
            }

            showToast(payload.error || payload.message || 'Не удалось отменить запись');
        } catch (e) {
            console.warn('Cancel registration error:', e);
            showToast('Ошибка сети');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = 'Отменить запись';
            }
        }
    }

    async function handleLoadVolunteers(event) {
        const panel = $('#event-volunteers-panel');
        if (!panel) return;

        panel.classList.remove('hidden');
        panel.innerHTML = '<div class="panel-loading">Загружаем список...</div>';

        try {
            const response = await fetch(
                `${API_BASE_URL}/api/events/${event.id}/volunteers?max_user_id=${encodeURIComponent(currentUser.max_user_id)}`
            );
            const payload = await readJsonResponse(response);

            if (!response.ok) {
                panel.innerHTML = renderEmptyState('Не удалось загрузить', payload.error || payload.message || 'Попробуйте позже');
                return;
            }

            panel.innerHTML = renderVolunteersPanel(payload.volunteers || []);
            panel.querySelectorAll('[data-confirm-volunteer]').forEach(button => {
                button.addEventListener('click', () => {
                    handleConfirmParticipation(event, {
                        volunteer_max_user_id: button.dataset.confirmVolunteer
                    });
                });
            });
        } catch (e) {
            console.warn('Load volunteers error:', e);
            panel.innerHTML = renderEmptyState('Ошибка сети', 'Не удалось получить список волонтёров');
        }
    }

    async function handleCancelEvent(event) {
        if (!window.confirm('Отменить мероприятие? Волонтёры больше не смогут на него записаться.')) {
            return;
        }

        const btn = $('#btn-cancel-event');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Отменяем...';
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/events/${event.id}/cancel`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ max_user_id: currentUser.max_user_id })
            });
            const payload = await readJsonResponse(response);

            if (response.ok) {
                syncOrganizerEvent(event.id, { status: payload.event_status || 'cancelled' });
                showToast(payload.message || 'Мероприятие отменено');
                const updatedEvent = myEvents.find(ev => ev.id === event.id);
                if (updatedEvent) {
                    showEventDetail(updatedEvent);
                }
                return;
            }

            showToast(payload.error || payload.message || 'Не удалось отменить мероприятие');
        } catch (e) {
            console.warn('Cancel event error:', e);
            showToast('Ошибка сети');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = 'Отменить мероприятие';
            }
        }
    }

    function showQrScanner(event) {
        const panel = $('#qr-scanner-panel');
        if (!panel) return;

        panel.classList.remove('hidden');
        panel.innerHTML = `
            <div class="scanner-card">
                <h4 class="panel-title">Подтверждение по QR</h4>
                <p class="panel-text">
                    Наведите камеру на QR-код волонтёра или вставьте данные вручную.
                </p>
                <video id="qr-video" class="qr-video" playsinline muted></video>
                <div class="scanner-actions">
                    <button class="btn-secondary" id="btn-start-scanner">Включить камеру</button>
                    <button class="btn-secondary" id="btn-stop-scanner">Остановить</button>
                </div>
                <div class="manual-confirm">
                    <input class="form-input" id="qr-manual-input" placeholder="max_user_id или данные QR-кода">
                    <button class="btn-primary" id="btn-confirm-manual">Подтвердить вручную</button>
                </div>
                <p class="scanner-hint" id="scanner-hint"></p>
            </div>
        `;

        $('#btn-start-scanner')?.addEventListener('click', () => startQrScanner(event));
        $('#btn-stop-scanner')?.addEventListener('click', stopQrScanner);
        $('#btn-confirm-manual')?.addEventListener('click', () => {
            const value = $('#qr-manual-input')?.value.trim();
            if (!value) {
                showToast('Введите данные QR-кода');
                return;
            }
            handleConfirmParticipation(event, { qr_payload: value });
        });
    }

    async function startQrScanner(event) {
        const hint = $('#scanner-hint');
        const video = $('#qr-video');

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            if (hint) hint.textContent = 'Камера недоступна в этом браузере. Используйте ручной ввод ниже.';
            return;
        }

        if (!('BarcodeDetector' in window)) {
            if (hint) hint.textContent = 'Встроенный QR-сканер не поддерживается. Используйте ручной ввод ниже.';
            return;
        }

        stopQrScanner();

        try {
            scannerStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' },
                audio: false
            });
            video.srcObject = scannerStream;
            await video.play();

            const detector = new BarcodeDetector({ formats: ['qr_code'] });
            if (hint) hint.textContent = 'Сканирование запущено. Наведите камеру на QR-код.';

            const scan = async () => {
                if (!scannerStream) return;

                try {
                    const codes = await detector.detect(video);
                    if (codes.length > 0) {
                        const rawValue = codes[0].rawValue;
                        stopQrScanner();
                        await handleConfirmParticipation(event, { qr_payload: rawValue });
                        return;
                    }
                } catch (e) {
                    console.warn('QR detect error:', e);
                }

                scannerFrameId = requestAnimationFrame(scan);
            };

            scan();
        } catch (e) {
            console.warn('Start scanner error:', e);
            if (hint) hint.textContent = 'Не удалось открыть камеру. Проверьте разрешения или используйте ручной ввод.';
        }
    }

    function stopQrScanner() {
        if (scannerFrameId) {
            cancelAnimationFrame(scannerFrameId);
            scannerFrameId = null;
        }

        if (scannerStream) {
            scannerStream.getTracks().forEach(track => track.stop());
            scannerStream = null;
        }

        const video = $('#qr-video');
        if (video) {
            video.srcObject = null;
        }
    }

    async function handleConfirmParticipation(event, data) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/events/${event.id}/confirm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    max_user_id: currentUser.max_user_id,
                    ...data
                })
            });

            const payload = await readJsonResponse(response);
            if (response.ok) {
                showToast(payload.message || 'Участие подтверждено');
                await handleLoadVolunteers(event);
                return;
            }

            showToast(payload.error || payload.message || 'Не удалось подтвердить участие');
        } catch (e) {
            console.warn('Confirm participation error:', e);
            showToast('Ошибка сети');
        }
    }

    async function handleCreateEvent(e) {
        e.preventDefault();

        const formData = {
            title: $('#event-title').value.trim(),
            description: $('#event-description').value.trim(),
            event_date: $('#event-date').value,
            event_time: $('#event-time').value,
            city: $('#event-city').value.trim(),
            address: $('#event-address').value.trim(),
            volunteers_needed: parseInt($('#event-volunteers').value, 10),
            category: $('#event-category').value,
            inventory: $('#event-inventory').value.trim(),
            duration_hours: parseInt($('#event-duration').value, 10) || 0,
            certificate_type: $('#event-certificate').value || 'none',
            organizer_max_user_id: currentUser.max_user_id
        };

        // Validate
        if (!formData.title || !formData.event_date || !formData.city) {
            showToast('Заполните все обязательные поля');
            return;
        }

        // Отправляем в API
        try {
            const response = await fetch(`${API_BASE_URL}/api/events`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                const result = await response.json();

                // Добавляем в локальный список
                const newEvent = {
                    ...formData,
                    id: result.event_id || Date.now(),
                    volunteers_registered: 0,
                    status: 'open',
                    organizer_id: currentUser.id,
                    is_registered: false
                };
                myEvents.unshift(normalizeEvent(newEvent));
                refreshOrganizerWorkspace();

                // Обновляем статистику

                // Сбрасываем форму
                e.target.reset();
                showToast('Мероприятие создано! 🎉');

                // Переходим к списку
                setTimeout(() => {
                    navigateTo('organizer-events', 'Мои мероприятия');
                    const nav = $('#nav-organizer .nav-item[data-page="organizer-events"]');
                    if (nav) updateNavActive(nav);
                }, 1000);
            } else {
                const err = await response.json();
                showToast(err.error || 'Не удалось создать мероприятие');
            }
        } catch (err) {
            console.warn('Create event error:', err);
            showToast('Ошибка сети при создании мероприятия');
        }
    }

    // ============ MAX Bridge ============

    /**
     * Отправка данных боту через MAX Bridge.
     * В продакшене данные будут доставлены в обработчик бота.
     */
    function sendDataToBot(data) {
        try {
            if (window.WebApp && typeof window.WebApp.sendData === 'function') {
                window.WebApp.sendData(JSON.stringify(data));
            } else {
                console.log('[Mock] sendData to bot:', data);
            }
        } catch (e) {
            console.warn('WebApp.sendData error:', e);
        }
    }

    /**
     * Закрытие мини-приложения.
     */
    function closeApp() {
        try {
            if (window.WebApp && typeof window.WebApp.close === 'function') {
                window.WebApp.close();
            }
        } catch (e) {
            console.warn('WebApp.close error:', e);
        }
    }

    // ============ Helpers ============

    function getInitials(name) {
        if (!name) return '?';
        const parts = name.trim().split(/\s+/);
        return parts.map(p => p[0]).slice(0, 2).join('').toUpperCase();
    }

    function formatBirthDate(dateStr) {
        if (!dateStr) return '—';
        const parts = dateStr.split('-');
        if (parts.length < 3) return dateStr;
        const [y, m, d] = parts;
        return `${parseInt(d, 10)} ${MONTHS_SHORT[parseInt(m, 10) - 1]} ${y}`;
    }

    function parseDate(dateStr) {
        if (!dateStr) return { year: 0, month: 0, day: 0 };
        // Handle ISO datetime strings like '2026-03-22T18:00:00'
        const datePart = dateStr.split('T')[0];
        const [year, month, day] = datePart.split('-').map(Number);
        return { year, month: month - 1, day };
    }

    function isEventExpired(event) {
        if (!event.event_date) return false;

        const eventTime = event.event_time || '23:59';
        const eventDateTime = new Date(`${event.event_date}T${eventTime}`);
        if (Number.isNaN(eventDateTime.getTime())) {
            return false;
        }

        return eventDateTime < new Date();
    }

    function getStatusClass(status) {
        const map = {
            open: 'status-open',
            closed: 'status-closed',
            completed: 'status-completed',
            cancelled: 'status-cancelled'
        };
        return map[status] || 'status-open';
    }

    function getStatusLabel(status) {
        const map = {
            open: 'Открыто',
            closed: 'Набор закрыт',
            completed: 'Завершено',
            cancelled: 'Отменено'
        };
        return map[status] || status;
    }

    function renderVolunteerEventAction(event) {
        if (event.is_registered) {
            if (event.status === 'completed') {
                return '<button class="btn-secondary" disabled>Мероприятие завершено</button>';
            }
            if (event.status === 'cancelled') {
                return '<button class="btn-secondary" disabled>Мероприятие отменено</button>';
            }
            return `
                <div class="event-actions-stack">
                    <button class="btn-secondary" disabled>Вы записаны</button>
                    <button class="btn-danger" id="btn-cancel-registration" data-event-id="${event.id}">
                        Отменить запись
                    </button>
                </div>
            `;
        }

        if (event.status === 'closed') {
            return '<button class="btn-secondary" disabled>Набор завершён</button>';
        }

        if (event.status === 'completed') {
            return '<button class="btn-secondary" disabled>Мероприятие завершено</button>';
        }

        return `
            <button class="btn-primary" id="btn-join-event" data-event-id="${event.id}">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>
                Записаться
            </button>
        `;
    }

    function renderOrganizerEventActions(event) {
        return `
            <div class="organizer-actions">
                <button class="btn-primary" id="btn-load-volunteers" data-event-id="${event.id}">
                    Кто записался
                </button>
                <button class="btn-secondary" id="btn-scan-qr" data-event-id="${event.id}">
                    Сканировать QR волонтёра
                </button>
                ${event.status !== 'completed' && event.status !== 'cancelled' ? `
                <button class="btn-danger" id="btn-cancel-event" data-event-id="${event.id}">
                    Отменить мероприятие
                </button>` : ''}
                <div class="event-volunteers-panel hidden" id="event-volunteers-panel"></div>
                <div class="qr-scanner-panel hidden" id="qr-scanner-panel"></div>
            </div>
        `;
    }

    async function readJsonResponse(response) {
        const text = await response.text();
        if (!text) {
            return {};
        }

        try {
            return JSON.parse(text);
        } catch (e) {
            return { error: text };
        }
    }

    function resetJoinButton(btn) {
        if (!btn) {
            return;
        }

        btn.disabled = false;
        btn.textContent = 'Записаться';
    }

    function syncEventAfterJoin(eventId, payload) {
        syncEventAfterRegistrationChange(eventId, payload);
    }

    function syncEventAfterRegistrationChange(eventId, payload) {
        const updates = {};

        if (payload.code === 'joined' || payload.code === 'already_joined') {
            updates.is_registered = true;
        }

        if (payload.code === 'registration_cancelled' || payload.is_registered === false) {
            updates.is_registered = false;
        }

        if (typeof payload.volunteers_registered === 'number') {
            updates.volunteers_registered = payload.volunteers_registered;
        }

        if (payload.event_status) {
            updates.status = payload.event_status;
        }

        if (Object.keys(updates).length === 0) {
            return;
        }

        events = events.map(event => (
            event.id === eventId ? normalizeEvent({ ...event, ...updates }) : event
        ));

        if (currentPage === 'event-detail') {
            const updatedEvent = events.find(event => event.id === eventId);
            if (updatedEvent) {
                showEventDetail(updatedEvent);
            }
        }

        refreshVolunteerWorkspace();
    }

    function syncOrganizerEvent(eventId, updates) {
        myEvents = myEvents.map(event => (
            event.id === eventId ? normalizeEvent({ ...event, ...updates }) : event
        ));
        events = events.map(event => (
            event.id === eventId ? normalizeEvent({ ...event, ...updates }) : event
        ));

        refreshOrganizerWorkspace();
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function showToast(message) {
        toastMessage.textContent = message;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('show'), 10);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.classList.add('hidden'), 300);
        }, 3000);
    }

    // ============ Start ============

    document.addEventListener('DOMContentLoaded', init);

})();
