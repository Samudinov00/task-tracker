from django.contrib import admin
from .models import Project, Task, Comment, Notification


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'manager', 'created_at')
    search_fields = ('name',)
    filter_horizontal = ('executors', 'clients')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'status', 'assignee', 'deadline')
    list_filter  = ('status', 'project')
    search_fields = ('title',)


admin.site.register(Comment)
admin.site.register(Notification)
