from django.conf import settings


def korva_push(request):
    """Inyecta la VAPID public key para el frontend de notificaciones push."""
    return {
        'korva_vapid_public_key': settings.VAPID_PUBLIC_KEY,
    }