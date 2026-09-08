from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = 'Notificaciones en Tiempo Real'

    def ready(self):
        from . import signals  # noqa: F401
        from .models import Notification
        from .signals import push_on_notification
        from django.db.models.signals import post_save
        post_save.connect(push_on_notification, sender=Notification)