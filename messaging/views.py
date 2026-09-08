from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.timesince import timesince
from .models import Message, Conversation
from .forms import MessageForm
from users.models import Profile


def _format_msg_time(timestamp):
    """Formatea la hora de un mensaje: Hoy/ayer con hora, o fecha corta."""
    if not timestamp:
        return None
    now = timezone.now()
    today = now.date()
    ts = timezone.localtime(timestamp)
    if ts.date() == today:
        return ts.strftime('%I:%M %p').lstrip('0')
    elif ts.date() == today - timezone.timedelta(days=1):
        return 'Ayer'
    else:
        return ts.strftime('%b %d')


@login_required(login_url='login')
def messages_view(request):
    """Vista de lista de conversaciones"""
    try:
        user_profile = request.user.profile
        
        # Obtener todas las conversaciones del usuario
        conversations = Conversation.objects.filter(
            Q(user1=user_profile) | Q(user2=user_profile)
        ).order_by('-updated_at')
        
        # Enriquecer cada conversación con el otro usuario, último mensaje y no leídos
        conv_data = []
        for conv in conversations:
            other = conv.get_other_user(user_profile)
            last_msg = conv.get_messages().last()
            unread_count = conv.get_messages().filter(
                recipient=user_profile,
            ).exclude(read_by=user_profile).count()
            # Marcar si el último mensaje es de imagen o video
            last_label = None
            if last_msg:
                if last_msg.image:
                    last_label = '📷 Foto'
                elif last_msg.video:
                    last_label = '🎥 Video'
                else:
                    last_label = last_msg.content
            conv_data.append({
                'conversation': conv,
                'other_user': other,
                'last_message': last_msg,
                'unread_count': unread_count,
                'last_message_text': (last_label[:80] + '…') if last_label and len(str(last_label)) > 80 else last_label,
                'last_time': _format_msg_time(last_msg.timestamp) if last_msg else None,
            })
        
        # Contactos frecuentes (otros perfiles para sugerencias)
        frequent_contacts = Profile.objects.exclude(
            pk__in=Profile.objects.filter(user__username=request.user.username).values_list('pk', flat=True)
        ).order_by('-popularity_score')[:4]
        
        context = {
            'conversations': conv_data,
            'frequent_contacts': frequent_contacts,
        }
        
        return render(request, 'messaging/messages.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar mensajes: {str(e)}')
        return redirect('home')


@login_required(login_url='login')
def conversation_detail(request, conversation_id):
    """Vista de una conversación específica"""
    try:
        conversation = get_object_or_404(Conversation, pk=conversation_id)
        user_profile = request.user.profile
        
        # Verificar permiso
        if conversation.user1 != user_profile and conversation.user2 != user_profile:
            messages.error(request, 'No tienes acceso a esta conversación.')
            return redirect('messages')
        
        # Obtener los mensajes de la conversación
        chat_messages = conversation.get_messages()
        
        # AJAX: comprobar nuevos mensajes
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Marcar como leídos los mensajes recibidos
            for m in chat_messages.filter(recipient=user_profile):
                if not m.is_read_by(user_profile):
                    m.mark_as_read(user_profile)
            last_msg_id = request.GET.get('last_msg_id')
            if last_msg_id:
                new_messages = chat_messages.filter(id__gt=last_msg_id)
                if new_messages.exists():
                    data = [{
                        'id': m.pk,
                        'content': m.content or '',
                        'image_url': m.image.url if m.image else '',
                        'video_url': m.video.url if m.video else '',
                        'timestamp': m.timestamp.strftime('%H:%M'),
                        'mine': m.sender == user_profile,
                        'read': m.recipient == user_profile and m.is_read_by(user_profile),
                    } for m in new_messages]
                    return JsonResponse({'new_messages': True, 'messages': data})
            return JsonResponse({'new_messages': False, 'messages': []})
        
        # Marcar mensajes como leídos por el usuario actual
        for msg in chat_messages.filter(recipient=user_profile):
            if not msg.is_read_by(user_profile):
                msg.mark_as_read(user_profile)
        
        if request.method == 'POST':
            form = MessageForm(request.POST, request.FILES)
            if form.is_valid():
                message = form.save(commit=False)
                message.sender = user_profile
                
                # Determinar el destinatario
                if conversation.user1 == user_profile:
                    message.recipient = conversation.user2
                else:
                    message.recipient = conversation.user1
                
                message.save()
                conversation.updated_at = message.timestamp
                conversation.save()
                
                return redirect('conversation_detail', conversation_id=conversation.pk)
        else:
            form = MessageForm()
        
        # Obtener el otro usuario en la conversación
        other_user = conversation.get_other_user(user_profile)
        
        context = {
            'conversation': conversation,
            'other_user': other_user,
            'chat_messages': chat_messages,
            'form': form,
        }
        
        return render(request, 'messaging/conversation_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('messages')


@login_required(login_url='login')
def start_conversation(request, username):
    """Iniciar una nueva conversación con un usuario"""
    try:
        user_profile = request.user.profile
        recipient_user = get_object_or_404(Profile, user__username=username)
        
        if recipient_user == user_profile:
            messages.error(request, 'No puedes iniciar una conversación contigo mismo.')
            return redirect('profile', username=username)
        
        # Buscar o crear conversación
        conversation = Conversation.objects.filter(
            (Q(user1=user_profile, user2=recipient_user) |
             Q(user1=recipient_user, user2=user_profile))
        ).first()
        
        if not conversation:
            conversation = Conversation.objects.create(
                user1=user_profile,
                user2=recipient_user
            )
        
        return redirect('conversation_detail', conversation_id=conversation.pk)
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('messages')


@login_required(login_url='login')
def send_message(request):
    """Enviar un mensaje (puede ser AJAX)"""
    try:
        if request.method == 'POST':
            recipient_id = request.POST.get('recipient_id')
            content = request.POST.get('content')
            
            user_profile = request.user.profile
            recipient = get_object_or_404(Profile, pk=recipient_id)
            
            if not content and not request.FILES.get('image') and not request.FILES.get('video'):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'ok': False, 'error': 'Mensaje vacío'}, status=400)
                messages.error(request, 'Escribe un mensaje para enviar.')
                return redirect('messages')
            
            message = Message.objects.create(
                sender=user_profile,
                recipient=recipient,
                content=content
            )
            if request.FILES.get('image'):
                message.image = request.FILES['image']
            if request.FILES.get('video'):
                message.video = request.FILES['video']
            message.save()
            
            # Actualizar o crear conversación
            conversation = Conversation.objects.filter(
                (Q(user1=user_profile, user2=recipient) |
                 Q(user1=recipient, user2=user_profile))
            ).first()
            
            if conversation:
                conversation.updated_at = message.timestamp
                conversation.save()
            else:
                Conversation.objects.create(
                    user1=user_profile,
                    user2=recipient
                )

            # Notificación en tiempo real + push (estilo Facebook)
            try:
                from notifications.services import notify
                notify(
                    user=recipient.user,
                    notification_type='message',
                    title=f'Nuevo mensaje de {user_profile.user.username}',
                    message=content[:150] if content else ('📎 Imagen' if message.image else '🎥 Video'),
                    url='/messages/',
                    sender=request.user,
                    related_object_id=message.pk,
                    related_object_type='message',
                )
            except Exception:
                pass
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.utils import timezone
                return JsonResponse({
                    'ok': True,
                    'id': message.pk,
                    'content': message.content or '',
                    'image_url': message.image.url if message.image else '',
                    'video_url': message.video.url if message.video else '',
                    'timestamp': message.timestamp.strftime('%H:%M'),
                })
            
            return redirect('messages')
        
        return redirect('messages')
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)
        messages.error(request, f'Error: {str(e)}')
        return redirect('messages')

