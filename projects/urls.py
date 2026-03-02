from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    # Дашборд
    path('',  views.dashboard, name='dashboard'),

    # Проекты
    path('projects/',                               views.ProjectListView.as_view(),   name='project_list'),
    path('projects/create/',                        views.ProjectCreateView.as_view(), name='project_create'),
    path('projects/<int:pk>/',                      views.project_detail,              name='project_detail'),
    path('projects/<int:pk>/edit/',                 views.ProjectUpdateView.as_view(), name='project_edit'),
    path('projects/<int:pk>/delete/',               views.ProjectDeleteView.as_view(), name='project_delete'),

    # Канбан
    path('projects/<int:project_pk>/kanban/',       views.kanban,                      name='kanban'),

    # Задачи
    path('projects/<int:project_pk>/tasks/create/', views.task_create,                 name='task_create'),
    path('tasks/<int:pk>/',                         views.task_detail,                 name='task_detail'),
    path('tasks/<int:pk>/edit/',                    views.task_edit,                   name='task_edit'),
    path('tasks/<int:pk>/delete/',                  views.task_delete,                 name='task_delete'),

    # AJAX: drag & drop
    path('tasks/<int:task_pk>/move/',               views.task_move,                   name='task_move'),

    # Вложения
    path('attachments/<int:pk>/delete/',            views.attachment_delete,            name='attachment_delete'),

    # Логи статусов
    path('status-logs/', views.status_logs, name='status_logs'),

    # Уведомления
    path('notifications/',                          views.notifications_list,           name='notifications'),
    path('notifications/count/',                    views.notifications_count_api,      name='notifications_count'),
    path('notifications/recent/',                   views.notifications_recent_api,     name='notifications_recent'),
    path('notifications/mark-all-read/',            views.notifications_mark_all_read,  name='notifications_mark_all_read'),
]
