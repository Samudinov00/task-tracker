from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    # Дашборд
    path('', views.dashboard, name='dashboard'),

    # Проекты
    path('p/',                              views.ProjectListView.as_view(),   name='project_list'),
    path('p/create/',                       views.ProjectCreateView.as_view(), name='project_create'),
    path('p/<uuid:uuid>/',                  views.project_detail,              name='project_detail'),
    path('p/<uuid:uuid>/edit/',             views.ProjectUpdateView.as_view(), name='project_edit'),
    path('p/<uuid:uuid>/delete/',           views.ProjectDeleteView.as_view(), name='project_delete'),

    # Доска
    path('p/<uuid:project_uuid>/board/',    views.kanban,                      name='kanban'),

    # Задачи
    path('p/<uuid:project_uuid>/new/',      views.task_create,                 name='task_create'),
    path('t/<uuid:uuid>/',                  views.task_detail,                 name='task_detail'),
    path('t/<uuid:uuid>/edit/',             views.task_edit,                   name='task_edit'),
    path('t/<uuid:uuid>/delete/',           views.task_delete,                 name='task_delete'),

    # AJAX: drag & drop
    path('t/<uuid:task_uuid>/move/',        views.task_move,                   name='task_move'),

    # Вложения
    path('a/<int:pk>/delete/',              views.attachment_delete,            name='attachment_delete'),

    # Логи статусов
    path('logs/',                           views.status_logs,                 name='status_logs'),

    # Уведомления
    path('notifications/',                  views.notifications_list,           name='notifications'),
    path('notifications/count/',            views.notifications_count_api,      name='notifications_count'),
    path('notifications/recent/',           views.notifications_recent_api,     name='notifications_recent'),
    path('notifications/mark-all-read/',    views.notifications_mark_all_read,  name='notifications_mark_all_read'),
]
