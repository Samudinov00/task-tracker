from django import forms
from .models import Project, Task, Comment
from accounts.models import CustomUser


# ── Проект ────────────────────────────────────────────────────────────────────
class ProjectForm(forms.ModelForm):
    executors = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.filter(role='executor'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Исполнители',
    )
    clients = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.filter(role='client'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Клиенты',
    )

    class Meta:
        model = Project
        fields = ['name', 'description', 'executors', 'clients']
        labels = {
            'name': 'Название',
            'description': 'Описание',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


# ── Задача (менеджер) ─────────────────────────────────────────────────────────
class TaskForm(forms.ModelForm):
    clients = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Клиенты',
    )

    class Meta:
        model = Task
        fields = ['title', 'description', 'status', 'assignee', 'clients', 'deadline']
        labels = {
            'title': 'Название',
            'description': 'Описание',
            'status': 'Статус',
            'assignee': 'Исполнитель',
            'deadline': 'Дедлайн',
        }
        widgets = {
            'title':       forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'status':      forms.Select(attrs={'class': 'form-select'}),
            'assignee':    forms.Select(attrs={'class': 'form-select'}),
            'deadline':    forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d',
            ),
        }

    def __init__(self, project=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if project:
            self.fields['assignee'].queryset = project.executors.all()
        else:
            self.fields['assignee'].queryset = CustomUser.objects.filter(role='executor')
        self.fields['clients'].queryset = CustomUser.objects.filter(role='client')
        self.fields['assignee'].empty_label = '— Не назначен —'

        # Если редактируем, установим формат даты
        if self.instance and self.instance.deadline:
            self.initial['deadline'] = self.instance.deadline.strftime('%Y-%m-%d')


# ── Изменение статуса (исполнитель) ───────────────────────────────────────────
class TaskStatusForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['status']
        labels = {'status': 'Статус'}
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


# ── Комментарий ───────────────────────────────────────────────────────────────
class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        labels = {'text': ''}
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Введите комментарий...',
            }),
        }
