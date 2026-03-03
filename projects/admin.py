from django.contrib import admin
from .models import Project, Task, Comment, Notification, TimeLog, TaskChangeLog
from accounts.models import CustomUser


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'manager', 'created_at')
    search_fields = ('name',)
    filter_horizontal = ('executors', 'clients')

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'executors':
            kwargs['queryset'] = CustomUser.objects.filter(role='executor')
        elif db_field.name == 'clients':
            kwargs['queryset'] = CustomUser.objects.filter(role='client')
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'manager':
            kwargs['queryset'] = CustomUser.objects.filter(role='manager')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'status', 'priority', 'assignee', 'deadline')
    list_filter  = ('status', 'priority', 'project')
    search_fields = ('title',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'assignee':
            kwargs['queryset'] = CustomUser.objects.filter(role='executor')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'clients':
            kwargs['queryset'] = CustomUser.objects.filter(role='client')
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'minutes', 'logged_at')
    list_filter  = ('user',)
    search_fields = ('task__title',)


@admin.register(TaskChangeLog)
class TaskChangeLogAdmin(admin.ModelAdmin):
    list_display = ('task', 'changed_by', 'field_name', 'old_value', 'new_value', 'changed_at')
    list_filter  = ('field_name',)
    search_fields = ('task__title',)


admin.site.register(Comment)
admin.site.register(Notification)
