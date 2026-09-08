from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=None)
def push_on_notification(sender, instance, created, **kwargs):
    """Envía push web cuando se crea una Notification nueva."""
    if not created:
        return
    try:
        from .models import Notification
        from .services import send_push_to_user
        if not isinstance(instance, Notification):
            return
        send_push_to_user(
            instance.recipient,
            instance.title,
            instance.message,
            url='/notifications/',
        )
    except Exception as e:
        logger.warning('Error en signal push: %s', e)