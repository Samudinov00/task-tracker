import time

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.conf import settings

# Пути фоновых опросов, которые не считаются активностью пользователя
_POLLING_PATHS = frozenset([
    '/notifications/count/',
    '/notifications/recent/',
    '/notifications/mark-all-read/',
])

INACTIVITY_TIMEOUT = 30 * 60  # 30 минут в секундах


class SessionInactivityMiddleware:
    """Выбрасывает пользователя после 30 минут бездействия.

    Фоновые опросы уведомлений НЕ обновляют метку последней активности,
    чтобы они не сдвигали таймер незаметно для пользователя.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = time.time()
            last = request.session.get('last_activity')

            if last and (now - last) > INACTIVITY_TIMEOUT:
                logout(request)
                return redirect(f'{settings.LOGIN_URL}?reason=timeout')

            # Обновляем метку только для «настоящих» запросов пользователя
            if request.path not in _POLLING_PATHS:
                request.session['last_activity'] = now

        return self.get_response(request)
