from pywebpush import webpush, WebPushException
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
import json
import logging

logger = logging.getLogger(__name__)


def send_notification_email(notification):
    """Envía un email con la notificación si el usuario tiene email activado para ese tipo."""
    user = notification.recipient
    if not user.email:
        return False

    from .models import NotificationPreference
    try:
        pref = NotificationPreference.objects.get(user=user)
        field = f"email_{notification.notification_type}"
        if not getattr(pref, field, True):
            return False
    except NotificationPreference.DoesNotExist:
        pass

    subject = f'{notification.title} - Korva Nicaragua'
    base = settings.FRONTEND_URL.rstrip('/')
    url = notification.url
    if url.startswith('/'):
        url = f'{base}{url}'
    html_message = render_to_string('notifications/email_notification.html', {
        'notification': notification,
        'user': user,
        'url': url,
        'app_name': 'Korva Nicaragua',
    })
    try:
        send_mail(
            subject,
            notification.message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=True,
        )
        return True
    except Exception as e:
        logger.warning('Error enviando email de notificación: %s', e)
        return False


def notify(user, notification_type, title, message, url='#', sender=None, related_object_id=None, related_object_type=''):
    """Crea una notificación (BD), la difunde por WebSocket, dispara push y email. Devuelve la instancia."""
    from .models import Notification
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    notification = Notification.objects.create(
        recipient=user,
        sender=sender if sender is not None and sender.id != user.id else None,
        notification_type=notification_type,
        title=title,
        message=message,
        url=url or '#',
        related_object_id=related_object_id,
        related_object_type=related_object_type,
    )

    # Broadcast en tiempo real al usuario (si su WebSocket está conectado)
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{user.id}',
            {
                'type': 'notification_message',
                'notification': {
                    'id': notification.id,
                    'type': notification.notification_type,
                    'title': notification.title,
                    'message': notification.message,
                    'url': notification.url,
                    'icon': notification.icon,
                    'created_at': notification.created_at.isoformat(),
                },
            }
        )
    except Exception as e:
        logger.warning('Error broadcasting notificación: %s', e)

    # Push web (si el usuario se suscribió)
    try:
        send_push_to_user(user, title, message, url=url)
    except Exception as e:
        logger.warning('Error push de notificación: %s', e)

    # Email (si el usuario lo tiene activado para ese tipo)
    try:
        send_notification_email(notification)
    except Exception as e:
        logger.warning('Error email de notificación: %s', e)

    return notification


def send_push(subscription, title, body, url='/'):
    """Envía una notificación push a una suscripción individual.

    Retorna True si se envió, False si la suscripción es inválida (para borrar).
    """
    if not settings.VAPID_PUBLIC_KEY or not settings.VAPID_PRIVATE_KEY:
        logger.warning('VAPID keys no configuradas; push omitido.')
        return True

    payload = {
        'title': title,
        'body': body,
        'url': url,
        'icon': '/static/pwa/icon-192.png',
        'badge': '/static/pwa/icon-192.png',
        'tag': 'korva-notification',
    }
    try:
        webpush(
            subscription_info=subscription.subscription_info(),
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={
                'sub': 'mailto:soporte@korva.ni',
            },
            ttl=86400,
        )
        return True
    except WebPushException as e:
        # 404/410 = suscripción expiró o fue removida
        if e.response is not None and e.response.status_code in (404, 410):
            logger.info('Suscripción push inválida (404/410); se marcará para borrar.')
            return False
        logger.warning('Error enviando push: %s', e)
        return True
    except Exception as e:
        logger.warning('Error inesperado enviando push: %s', e)
        return True


def send_push_to_user(user, title, body, url='/'):
    """Envía un push a todas las suscripciones activas del usuario.

    Registra en la campaña push del navegador. Cada Notification dispare esto.
    """
    from .models import WebPushSubscription
    subs = WebPushSubscription.objects.filter(user=user)
    if not subs.exists():
        return 0

    sent = 0
    expired = []
    for sub in subs:
        ok = send_push(sub, title, body, url)
        if ok:
            sent += 1
        else:
            expired.append(sub.pk)
    if expired:
        WebPushSubscription.objects.filter(pk__in=expired).delete()
    return sent