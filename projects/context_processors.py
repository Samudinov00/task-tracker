def notifications_count(request):
    """Передаёт в каждый шаблон счётчик непрочитанных уведомлений."""
    if request.user.is_authenticated:
        count = request.user.notifications.filter(is_read=False).count()
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}
