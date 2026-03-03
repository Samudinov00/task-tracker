from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from django.contrib import messages

from django.contrib.auth import update_session_auth_hash
from .models import CustomUser
from .forms import CustomAuthenticationForm, UserCreateForm, UserUpdateForm, ProfileForm, CustomPasswordChangeForm, SetPasswordForm


# ── Миксин: доступ только менеджерам ─────────────────────────────────────────
class ManagerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_manager()

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('accounts:login')
        messages.error(self.request, 'Доступ запрещён. Требуются права менеджера.')
        return redirect('projects:project_list')


# ── Вход / выход ──────────────────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect('projects:project_list')
    form = CustomAuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get('next', 'projects:project_list'))
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    return redirect('accounts:login')


# ── Профиль текущего пользователя ────────────────────────────────────────────
@login_required
def profile_view(request):
    profile_form = ProfileForm(
        request.POST if 'save_profile' in request.POST else None,
        request.FILES or None,
        instance=request.user,
    )
    password_form = CustomPasswordChangeForm(
        request.user,
        request.POST if 'save_password' in request.POST else None,
    )

    if request.method == 'POST':
        if 'save_profile' in request.POST and request.user.is_manager() and profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Профиль успешно обновлён.')
            return redirect('accounts:profile')
        if 'save_password' in request.POST and password_form.is_valid():
            password_form.save()
            update_session_auth_hash(request, password_form.user)
            messages.success(request, 'Пароль успешно изменён.')
            return redirect('accounts:profile')

    return render(request, 'accounts/profile.html', {
        'form': profile_form,
        'password_form': password_form,
    })


# ── Управление пользователями (только менеджер) ───────────────────────────────
class UserListView(ManagerRequiredMixin, ListView):
    model = CustomUser
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        return (
            CustomUser.objects
            .exclude(pk=self.request.user.pk)
            .order_by('role', 'username')
        )


class UserCreateView(ManagerRequiredMixin, CreateView):
    model = CustomUser
    form_class = UserCreateForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Создать пользователя'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f'Пользователь «{form.instance.username}» создан.')
        return super().form_valid(form)


class UserUpdateView(ManagerRequiredMixin, UpdateView):
    model = CustomUser
    form_class = UserUpdateForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Редактировать пользователя'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Данные пользователя обновлены.')
        return super().form_valid(form)


class UserSetPasswordView(ManagerRequiredMixin, View):
    template_name = 'accounts/user_set_password.html'

    def get_user(self, pk):
        return get_object_or_404(CustomUser, pk=pk)

    def get(self, request, pk):
        target = self.get_user(pk)
        form = SetPasswordForm()
        return render(request, self.template_name, {'form': form, 'target': target})

    def post(self, request, pk):
        target = self.get_user(pk)
        form = SetPasswordForm(request.POST)
        if form.is_valid():
            target.set_password(form.cleaned_data['new_password1'])
            target.save()
            messages.success(request, f'Пароль пользователя «{target.username}» сброшен.')
            return redirect('accounts:user_list')
        return render(request, self.template_name, {'form': form, 'target': target})


class UserDeleteView(ManagerRequiredMixin, DeleteView):
    model = CustomUser
    template_name = 'accounts/user_confirm_delete.html'
    success_url = reverse_lazy('accounts:user_list')

    def form_valid(self, form):
        messages.success(self.request, 'Пользователь удалён.')
        return super().form_valid(form)
