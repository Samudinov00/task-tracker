from django import forms
from .models import Project, Task, Comment, TimeLog
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
        fields = ['title', 'description', 'status', 'priority', 'assignee', 'clients', 'deadline']
        labels = {
            'title': 'Название',
            'description': 'Описание',
            'status': 'Статус',
            'priority': 'Приоритет',
            'assignee': 'Исполнитель',
            'deadline': 'Дедлайн',
        }
        widgets = {
            'title':       forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'status':      forms.Select(attrs={'class': 'form-select'}),
            'priority':    forms.Select(attrs={'class': 'form-select'}),
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


# ── Вложение (PDF) ────────────────────────────────────────────────────────────
class AttachmentForm(forms.Form):
    file = forms.FileField(label='PDF файл')

    def clean_file(self):
        f = self.cleaned_data['file']
        if not f.name.lower().endswith('.pdf'):
            raise forms.ValidationError('Разрешены только PDF файлы.')
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError('Файл не должен превышать 10 МБ.')
        return f


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


# ── Лог времени ───────────────────────────────────────────────────────────────
class TimeLogForm(forms.ModelForm):
    class Meta:
        model = TimeLog
        fields = ['minutes', 'description']
        labels = {
            'minutes': 'Потрачено (мин)',
            'description': 'Описание',
        }
        widgets = {
            'minutes': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 1440,
                'placeholder': 'Например: 60',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Что было сделано...',
            }),
        }

    def clean_minutes(self):
        minutes = self.cleaned_data.get('minutes')
        if minutes is not None and minutes <= 0:
            raise forms.ValidationError('Укажите положительное количество минут.')
        return minutes
