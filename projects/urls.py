from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'projects'

urlpatterns = [
    # Корень → список проектов
    path('', RedirectView.as_view(pattern_name='projects:project_list', permanent=False), name='home'),

    # Аналитика
    path('analytics/', views.analytics, name='analytics'),

    # Экспорт
    path('export/tasks/csv/',   views.export_tasks_csv,   name='export_tasks_csv'),
    path('export/tasks/excel/', views.export_tasks_excel, name='export_tasks_excel'),

    # Проекты
    path('p/',                              views.ProjectListView.as_view(),   name='project_list'),
    path('p/create/',                       views.ProjectCreateView.as_view(), name='project_create'),
    path('p/<uuid:uuid>/',                  views.project_detail,              name='project_detail'),
    path('p/<uuid:uuid>/edit/',             views.ProjectUpdateView.as_view(), name='project_edit'),
    path('p/<uuid:uuid>/delete/',           views.ProjectDeleteView.as_view(), name='project_delete'),

    # Доска
    path('p/<uuid:project_uuid>/board/',        views.kanban,             name='kanban'),
    path('p/<uuid:project_uuid>/kanban-state/', views.kanban_state_api,   name='kanban_state'),

    # Задачи
    path('p/<uuid:project_uuid>/new/', views.task_create, name='task_create'),
    path('t/<uuid:uuid>/',             views.task_detail, name='task_detail'),
    path('t/<uuid:uuid>/edit/',        views.task_edit,   name='task_edit'),
    path('t/<uuid:uuid>/delete/',      views.task_delete, name='task_delete'),

    # AJAX: drag & drop
    path('t/<uuid:task_uuid>/move/', views.task_move, name='task_move'),

    # AJAX: менеджер назначает себя исполнителем
    path('t/<uuid:task_uuid>/self-assign/', views.task_self_assign, name='task_self_assign'),

    # Трекер времени
    path('t/<uuid:task_uuid>/log-time/', views.log_time, name='log_time'),

    # Bulk операции
    path('bulk-update/', views.bulk_task_update, name='bulk_task_update'),

    # Вложения
    path('a/<int:pk>/delete/', views.attachment_delete, name='attachment_delete'),

    # Логи статусов
    path('logs/', views.status_logs, name='status_logs'),

    # Уведомления
    path('notifications/',               views.notifications_list,          name='notifications'),
    path('notifications/count/',         views.notifications_count_api,     name='notifications_count'),
    path('notifications/recent/',        views.notifications_recent_api,    name='notifications_recent'),
    path('notifications/mark-all-read/', views.notifications_mark_all_read, name='notifications_mark_all_read'),
]
