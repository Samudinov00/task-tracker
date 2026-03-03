import time

from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.http import require_POST


@login_required
@require_POST
def session_ping(request):
    """Обновляет метку последней активности по запросу фронтенда."""
    request.session['last_activity'] = time.time()
    return JsonResponse({'ok': True})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('session/ping/', session_ping, name='session_ping'),
    path('', include('projects.urls', namespace='projects')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
