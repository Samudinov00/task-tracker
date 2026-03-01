"""
Views для проектов, задач, комментариев и уведомлений.

Управление доступом:
  manager  — полный CRUD проектов и задач; видит все задачи своих проектов
  executor — редактирует только свои задачи (статус + комментарии)
  client   — только чтение задач своих проектов + комментарии
"""
import json

from django.db.models import Count, Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import CommentForm, ProjectForm, TaskForm, TaskStatusForm
from .models import Comment, Notification, Project, Task


# ─────────────────────────── Хелперы ──────────────────────────────────────────

class ManagerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_manager()

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('accounts:login')
        messages.error(self.request, 'Доступ запрещён. Требуются права менеджера.')
        return redirect('projects:dashboard')


def _check_project_access(user, project):
    """Выбрасывает PermissionDenied, если пользователь не имеет доступа к проекту."""
    if user.is_manager():
        if project.manager != user:
            raise PermissionDenied
    elif user.is_client():
        if not user.client_projects.filter(pk=project.pk).exists():
            raise PermissionDenied
    elif user.is_executor():
        # Исполнитель видит проект если он в списке команды ИЛИ назначен на задачу
        in_team = user.executor_projects.filter(pk=project.pk).exists()
        has_task = project.tasks.filter(assignee=user).exists()
        if not (in_team or has_task):
            raise PermissionDenied


def _notify(users, task, ntype, message):
    """Создаёт уведомления для списка пользователей."""
    if not hasattr(users, '__iter__') or isinstance(users, str):
        users = [users]
    for u in users:
        if u:
            Notification.objects.create(
                user=u, task=task,
                notification_type=ntype, message=message,
            )


# ─────────────────────────── Дашборд ──────────────────────────────────────────

@login_required
def dashboard(request):
    user = request.user

    if not user.is_manager():
        return redirect('projects:project_list')

    projects = Project.objects.filter(manager=user).prefetch_related('tasks')
    tasks = Task.objects.filter(project__manager=user).select_related('assignee', 'project')

    statuses = [
        {'key': key, 'label': label,
         'count': tasks.filter(status=key).count(),
         'badge': Task.STATUS_BADGE.get(key, 'secondary')}
        for key, label in Task.STATUS_CHOICES
    ]
    overdue = [t for t in tasks if t.is_overdue()]

    ctx = {
        'projects': projects,
        'total_projects': projects.count(),
        'total_tasks': tasks.count(),
        'production_count': tasks.filter(status='production').count(),
        'overdue_count': len(overdue),
        'statuses': statuses,
        'recent_tasks': tasks.order_by('-updated_at')[:8],
    }
    return render(request, 'projects/dashboard.html', ctx)


# ─────────────────────────── Проекты ──────────────────────────────────────────

class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'projects/project_list.html'
    context_object_name = 'projects'

    def get_queryset(self):
        user = self.request.user
        if user.is_manager():
            return Project.objects.filter(manager=user)
        if user.is_client():
            return user.client_projects.all()
        if user.is_executor():
            # Проекты из команды + проекты с назначенными задачами
            return Project.objects.filter(
                Q(executors=user) | Q(tasks__assignee=user)
            ).distinct()
        return Project.objects.none()


class ProjectCreateView(ManagerRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_form.html'

    def form_valid(self, form):
        form.instance.manager = self.request.user
        messages.success(self.request, f'Проект «{form.instance.name}» создан.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('projects:kanban', kwargs={'project_pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Новый проект'
        return ctx


class ProjectUpdateView(ManagerRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_form.html'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.manager != self.request.user:
            raise PermissionDenied
        return obj

    def get_success_url(self):
        return reverse('projects:project_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Редактировать проект'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Проект обновлён.')
        return super().form_valid(form)


class ProjectDeleteView(ManagerRequiredMixin, DeleteView):
    model = Project
    template_name = 'projects/project_confirm_delete.html'
    success_url = reverse_lazy('projects:project_list')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.manager != self.request.user:
            raise PermissionDenied
        return obj

    def form_valid(self, form):
        messages.success(self.request, 'Проект удалён.')
        return super().form_valid(form)


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    _check_project_access(request.user, project)

    tasks = project.tasks.select_related('assignee')
    if request.user.is_executor():
        tasks = tasks.filter(assignee=request.user)
    ctx = {
        'project': project,
        'tasks': tasks,
        'not_started_count': tasks.filter(status='not_started').count(),
        'in_work_count': tasks.filter(status__in=['cell_reg', 'design', 'controls', 'tables']).count(),
        'test_count': tasks.filter(status__in=['test_nsk', 'test_district']).count(),
        'production_count': tasks.filter(status='production').count(),
    }
    return render(request, 'projects/project_detail.html', ctx)


# ─────────────────────────── Канбан-доска ─────────────────────────────────────

@login_required
def kanban(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    _check_project_access(request.user, project)

    qs = project.tasks.select_related('assignee').prefetch_related('comments')
    if request.user.is_executor():
        qs = qs.filter(assignee=request.user)
    kanban_columns = [
        {
            'key': 'not_started', 'label': 'Не начата',
            'color': 'secondary', 'icon': 'bi-circle',
            'tasks': qs.filter(status='not_started').order_by('order'),
        },
        {
            'key': 'cell_reg', 'label': 'Регистрация ячеек',
            'color': 'info', 'icon': 'bi-grid-3x3',
            'tasks': qs.filter(status='cell_reg').order_by('order'),
        },
        {
            'key': 'design', 'label': 'Разработка дизайна',
            'color': 'primary', 'icon': 'bi-palette',
            'tasks': qs.filter(status='design').order_by('order'),
        },
        {
            'key': 'controls', 'label': 'Разработка контролей',
            'color': 'primary', 'icon': 'bi-sliders',
            'tasks': qs.filter(status='controls').order_by('order'),
        },
        {
            'key': 'tables', 'label': 'Выходные таблицы',
            'color': 'primary', 'icon': 'bi-table',
            'tasks': qs.filter(status='tables').order_by('order'),
        },
        {
            'key': 'test_nsk', 'label': 'Тест НСК',
            'color': 'warning', 'icon': 'bi-bug',
            'tasks': qs.filter(status='test_nsk').order_by('order'),
        },
        {
            'key': 'test_district', 'label': 'Тест район',
            'color': 'warning', 'icon': 'bi-geo-alt-fill',
            'tasks': qs.filter(status='test_district').order_by('order'),
        },
        {
            'key': 'production', 'label': 'Промышленная эксплуатация',
            'color': 'success', 'icon': 'bi-check-circle-fill',
            'tasks': qs.filter(status='production').order_by('order'),
        },
    ]
    return render(request, 'projects/kanban.html', {
        'project': project,
        'kanban_columns': kanban_columns,
    })


# ─────────────── AJAX: перемещение задачи в Канбане ───────────────────────────

@login_required
@require_POST
def task_move(request, task_pk):
    task = get_object_or_404(Task, pk=task_pk)
    user = request.user

    # Клиент не может двигать карточки
    if user.is_client():
        return JsonResponse({'error': 'Нет доступа'}, status=403)
    # Исполнитель — только свои задачи
    if user.is_executor() and task.assignee != user:
        return JsonResponse({'error': 'Нет доступа'}, status=403)
    # Менеджер — только свои проекты
    if user.is_manager() and task.project.manager != user:
        return JsonResponse({'error': 'Нет доступа'}, status=403)

    data = json.loads(request.body)
    new_status  = data.get('status')
    column_ids  = data.get('column_ids', [])   # упорядоченный список ID задач в колонке

    valid_statuses = [s[0] for s in Task.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return JsonResponse({'error': 'Неверный статус'}, status=400)

    old_status   = task.status
    task.status  = new_status
    task.save(update_fields=['status', 'updated_at'])

    # Обновить порядок всей колонки
    for idx, tid in enumerate(column_ids):
        Task.objects.filter(pk=tid, project=task.project).update(order=idx)

    # Уведомления при смене статуса
    if old_status != new_status:
        label = dict(Task.STATUS_CHOICES).get(new_status)
        recipients = set()
        if task.assignee and task.assignee != user:
            recipients.add(task.assignee)
        if task.project.manager != user:
            recipients.add(task.project.manager)
        _notify(
            recipients, task, Notification.TYPE_TASK_STATUS,
            f'Статус задачи «{task.title}» изменён на «{label}»',
        )

    return JsonResponse({'success': True})


# ─────────────────────────── Задачи ───────────────────────────────────────────

@login_required
def task_detail(request, pk):
    task = get_object_or_404(
        Task.objects.select_related('assignee', 'project', 'created_by')
                    .prefetch_related('comments__author'),
        pk=pk,
    )
    user = request.user
    _check_project_access(user, task.project)

    # Исполнитель видит только свои задачи
    if user.is_executor() and task.assignee != user:
        raise PermissionDenied

    comment_form = CommentForm()

    if request.method == 'POST' and 'comment_submit' in request.POST:
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.task   = task
            comment.author = user
            comment.save()

            # Уведомления
            recipients = set()
            if task.assignee and task.assignee != user:
                recipients.add(task.assignee)
            if task.project.manager != user:
                recipients.add(task.project.manager)
            _notify(
                recipients, task, Notification.TYPE_COMMENT,
                f'{user.get_display_name()} прокомментировал задачу «{task.title}»',
            )

            messages.success(request, 'Комментарий добавлен.')
            return redirect('projects:task_detail', pk=task.pk)

    can_edit = user.is_manager() or (user.is_executor() and task.assignee == user)
    return render(request, 'projects/task_detail.html', {
        'task': task,
        'comment_form': comment_form,
        'can_edit': can_edit,
    })


@login_required
def task_create(request, project_pk):
    if not request.user.is_manager():
        raise PermissionDenied

    project = get_object_or_404(Project, pk=project_pk, manager=request.user)

    if request.method == 'POST':
        form = TaskForm(project=project, data=request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.project    = project
            task.created_by = request.user
            task.save()

            if task.assignee:
                _notify(
                    task.assignee, task, Notification.TYPE_TASK_ASSIGNED,
                    f'Вам назначена задача «{task.title}» в проекте «{project.name}»',
                )

            messages.success(request, f'Задача «{task.title}» создана.')
            return redirect('projects:kanban', project_pk=project.pk)
    else:
        form = TaskForm(project=project)

    return render(request, 'projects/task_form.html', {
        'form': form,
        'project': project,
        'title': 'Новая задача',
    })


@login_required
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk)
    user = request.user
    project = task.project

    if user.is_client():
        raise PermissionDenied
    if user.is_executor() and task.assignee != user:
        raise PermissionDenied
    if user.is_manager() and project.manager != user:
        raise PermissionDenied

    # Исполнитель меняет только статус/под-этап
    FormClass = TaskStatusForm if user.is_executor() else TaskForm
    form_kwargs = {} if user.is_executor() else {'project': project}

    if request.method == 'POST':
        form = FormClass(**form_kwargs, data=request.POST, instance=task)
        if form.is_valid():
            old_status = task.status
            saved_task = form.save()

            if user.is_manager():
                # Уведомить исполнителя при смене назначения
                if saved_task.assignee and 'assignee' in form.changed_data:
                    _notify(
                        saved_task.assignee, saved_task, Notification.TYPE_TASK_ASSIGNED,
                        f'Вам назначена задача «{saved_task.title}»',
                    )

            if old_status != saved_task.status:
                label = dict(Task.STATUS_CHOICES).get(saved_task.status)
                recipients = set()
                if saved_task.assignee and saved_task.assignee != user:
                    recipients.add(saved_task.assignee)
                if project.manager != user:
                    recipients.add(project.manager)
                _notify(
                    recipients, saved_task, Notification.TYPE_TASK_STATUS,
                    f'Статус задачи «{saved_task.title}» изменён на «{label}»',
                )

            messages.success(request, 'Задача обновлена.')
            return redirect('projects:task_detail', pk=saved_task.pk)
    else:
        form = FormClass(**form_kwargs, instance=task)

    return render(request, 'projects/task_form.html', {
        'form': form,
        'task': task,
        'project': project,
        'title': 'Редактировать задачу',
    })


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not request.user.is_manager() or task.project.manager != request.user:
        raise PermissionDenied

    project_pk = task.project.pk
    if request.method == 'POST':
        task.delete()
        messages.success(request, 'Задача удалена.')
        return redirect('projects:kanban', project_pk=project_pk)

    return render(request, 'projects/task_confirm_delete.html', {'task': task})


# ─────────────────────────── Уведомления ──────────────────────────────────────

@login_required
def notifications_list(request):
    notifications = request.user.notifications.select_related('task__project').all()
    # Помечаем все как прочитанные при открытии страницы
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'projects/notifications.html', {
        'notifications': notifications,
    })


@login_required
def notifications_count_api(request):
    count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'count': count})


@login_required
def notifications_recent_api(request):
    items = request.user.notifications.filter(is_read=False).select_related('task')[:6]
    data = []
    for n in items:
        data.append({
            'id': n.pk,
            'message': n.message,
            'created_at': n.created_at.strftime('%d.%m %H:%M'),
            'task_id': n.task.pk if n.task else None,
            'task_url': reverse('projects:task_detail', kwargs={'pk': n.task.pk}) if n.task else None,
        })
    total = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'notifications': data, 'count': total})


@login_required
@require_POST
def notifications_mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return JsonResponse({'success': True})
