import json

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .models import Notification, WebPushSubscription


@login_required
def notifications_page(request):
    """Página completa de notificaciones."""
    qs = Notification.objects.filter(recipient=request.user) \
        .select_related('sender') \
        .order_by('-created_at')
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()

    return render(request, 'notifications/list.html', {
        'page_obj': page,
        'paginator': paginator,
        'notifications': page.object_list,
        'unread': unread,
        'total': qs.count(),
    })


@login_required
def notifications_list(request):
    """Lista de notificaciones para el panel desplegable (JSON)."""
    limit = int(request.GET.get('limit', 30))
    notifications = list(
        Notification.objects.filter(recipient=request.user)
        .select_related('sender')
        .order_by('-created_at')[:limit]
    )
    unread = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()

    data = [{
        'id': n.id,
        'type': n.notification_type,
        'title': n.title,
        'message': n.message,
        'sender': n.sender.username if n.sender else None,
        'sender_avatar': (
            n.sender.profile.logo.url
            if n.sender and hasattr(n.sender, 'profile') and n.sender.profile.logo
            else None
        ),
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat(),
        'related_object_id': n.related_object_id,
        'related_object_type': n.related_object_type,
        'url': n.url or '#',
        'icon': n.icon,
    } for n in notifications]

    return JsonResponse({
        'notifications': data,
        'unread': unread,
        'total': Notification.objects.filter(recipient=request.user).count(),
    })


@login_required
@require_POST
def notifications_mark_read(request, notification_id):
    """Marca una notificación como leída."""
    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'ok': True, 'unread': unread})


@login_required
@require_POST
def notifications_mark_all_read(request):
    """Marca todas las notificaciones como leídas."""
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'ok': True, 'unread': 0})


@login_required
@require_POST
def push_subscribe(request):
    """Registra la suscripción push del navegador del usuario."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    endpoint = data.get('endpoint', '').strip()
    keys = data.get('keys', {})
    p256dh = (keys or {}).get('p256dh', '').strip()
    auth = (keys or {}).get('auth', '').strip()

    if not endpoint or not p256dh or not auth:
        return JsonResponse({'error': 'Faltan datos de la suscripción'}, status=400)

    sub, created = WebPushSubscription.objects.update_or_create(
        user=request.user,
        endpoint=endpoint,
        defaults={
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
        },
    )
    return JsonResponse({'ok': True, 'created': created})


@login_required
@require_POST
def push_unsubscribe(request):
    """Elimina la suscripción push del usuario."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}
    endpoint = (data or {}).get('endpoint', '').strip()
    qs = WebPushSubscription.objects.filter(user=request.user)
    if endpoint:
        qs = qs.filter(endpoint=endpoint)
    deleted, _ = qs.delete()
    return JsonResponse({'ok': True, 'deleted': deleted})


@login_required
@require_POST
def push_test(request):
    """Envía una notificación de prueba al usuario actual."""
    from .services import send_push_to_user
    sent = send_push_to_user(
        request.user,
        'Korva Nicaragua',
        '¡Notificaciones activadas correctamente!',
        url='/',
    )
    return JsonResponse({'ok': True, 'sent': sent})