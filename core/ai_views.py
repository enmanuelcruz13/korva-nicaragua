from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import KorvaAIConfig, AIConversation, AIMessage
from django.conf import settings
import requests
import json

@login_required(login_url='login')
def ai_tutorial(request):
    """Tutorial de Korva IA para nuevos usuarios"""
    return render(request, 'ai/tutorial.html')


@login_required(login_url='login')
def korva_ai(request):
    """Vista principal del Asistente IA Korva"""
    try:
        profile = request.user.profile
        ai_config = profile.ai_config
        conversations = AIConversation.objects.filter(user=profile).order_by('-updated_at')[:10]
        
        # Verificar si necesita tutorial (sin API key configurada)
        needs_tutorial = not ai_config.uses_personal_key and not getattr(settings, 'GEMINI_API_KEY', None)
        
        # Estadísticas rápidas para el hub
        total_conversations = AIConversation.objects.filter(user=profile).count()
        total_messages = AIMessage.objects.filter(conversation__user=profile).count()
        has_api = bool(ai_config.uses_personal_key and ai_config.user_api_key) or bool(getattr(settings, 'GEMINI_API_KEY', None))
        
        context = {
            'ai_config': ai_config,
            'conversations': conversations,
            'needs_tutorial': needs_tutorial,
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'has_api': has_api,
        }
        
        return render(request, 'ai/korva_ai.html', context)
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('home')


@login_required(login_url='login')
def create_conversation(request):
    """Crear una nueva conversación con IA (acepta prompt inicial opcional)"""
    try:
        if request.method == 'POST':
            profile = request.user.profile
            title = request.POST.get('title', '').strip() or 'Nueva Conversación'
            initial_prompt = request.POST.get('prompt', '').strip()
            
            conversation = AIConversation.objects.create(
                user=profile,
                title=title if not initial_prompt else (title if title != 'Nueva Conversación' else initial_prompt[:60])
            )
            
            # Enviar el prompt inicial si viene incluido (desde preguntas rápidas)
            if initial_prompt:
                user_message = AIMessage.objects.create(
                    conversation=conversation,
                    role='user',
                    content=initial_prompt
                )
                try:
                    generate_ai_response(conversation, initial_prompt, user_message)
                except Exception as e:
                    messages.error(request, f'Error al conectar con la IA: {str(e)}')
            
            return redirect('conversation_chat', conversation_id=conversation.pk)
        
        return redirect('korva_ai')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('korva_ai')


@login_required(login_url='login')
def conversation_chat(request, conversation_id):
    """Vista para chatear en una conversación"""
    try:
        profile = request.user.profile
        conversation = AIConversation.objects.get(pk=conversation_id, user=profile)
        messages_list = conversation.messages.all().order_by('timestamp')
        ai_config = profile.ai_config
        
        context = {
            'conversation': conversation,
            'messages': messages_list,
            'ai_config': ai_config,
        }
        
        return render(request, 'ai/conversation_chat.html', context)
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('korva_ai')


@login_required(login_url='login')
@require_POST
def send_ai_message(request, conversation_id):
    """Enviar un mensaje a la IA (AJAX o formulario clásico)"""
    profile = request.user.profile
    conversation = AIConversation.objects.get(pk=conversation_id, user=profile)
    
    content = request.POST.get('message', '').strip()
    
    if not content:
        return JsonResponse({'error': 'El mensaje no puede estar vacío'}, status=400)
    
    # Guardar mensaje del usuario
    user_message = AIMessage.objects.create(
        conversation=conversation,
        role='user',
        content=content
    )
    
    try:
        response_text = generate_ai_response(conversation, content, user_message)
        
        # Actualizar conversación
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=['updated_at'])
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'response': response_text,
                'message_id': user_message.pk
            })
        
        return redirect('conversation_chat', conversation_id=conversation.pk)
        
    except Exception as e:
        error_message = f"Error al procesar tu solicitud: {str(e)}"
        user_message.delete()  # no dejar mensajes huérfanos si falla
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': error_message}, status=500)
        
        messages.error(request, error_message)
        return redirect('conversation_chat', conversation_id=conversation.pk)


def generate_ai_response(conversation, content, user_message):
    """Llama a Gemini (API REST) y guarda la respuesta. Devuelve el texto."""
    profile = conversation.user
    ai_config = profile.ai_config
    
    # Configurar API de Google Gemini
    if ai_config.uses_personal_key and ai_config.user_api_key:
        api_key = ai_config.user_api_key
    else:
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            raise ValueError("No hay clave de API configurada")
    
    system_instruction = (
        "Eres Korva IA, un asistente virtual especializado en negocios y emprendimiento "
        "para PyMEs en Nicaragua. "
        "SOLO puedes responder sobre: planes de negocio, marketing, finanzas, impuestos, "
        "registro de empresas, RUC, estrategias de ventas, atención al cliente, productos, "
        "servicios, y temas relacionados con el mundo empresarial nicaragüense.\n\n"
        "REGLAS ESTRICTAS:\n"
        "- NO puedes insultar, usar lenguaje ofensivo o discriminatorio\n"
        "- NO puedes hablar de temas +18, sexuales, violencia, drogas, política partidista, religión\n"
        "- NO puedes hacer tareas académicas, resolver exámenes o trabajar por el usuario\n"
        "- NO puedes dar consejos médicos, legales (sin aclarar que no eres abogado) o financieros de inversión\n"
        "- Si el usuario insiste en temas no permitidos, responde amablemente que solo ayudas con temas empresariales\n"
        "- Mantén un tono profesional, amable y servicial\n"
        "- Responde SIEMPRE en español"
    )
    
    # Construir historial de conversación (sin el nuevo mensaje, que va al final)
    contents = []
    for msg in conversation.messages.exclude(pk=user_message.pk).order_by('timestamp'):
        contents.append({
            'role': msg.role,
            'parts': [{'text': msg.content}]
        })
    contents.append({
        'role': 'user',
        'parts': [{'text': content}]
    })
    
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    payload = {
        'systemInstruction': {
            'parts': [{'text': system_instruction}]
        },
        'contents': contents,
    }
    
    # Gemini a veces satura (503 por alta demanda); reintentar con backoff
    import time
    response = None
    for attempt in range(3):
        response = requests.post(
            url,
            params={'key': api_key},
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=60,
        )
        if response.status_code == 503 or response.status_code == 429:
            time.sleep(2 * (attempt + 1))
            continue
        break
    response.raise_for_status()
    data = response.json()
    
    if not data.get('candidates'):
        raise ValueError("La IA no devolvió respuesta")
    
    response_text = data['candidates'][0]['content']['parts'][0]['text']
    
    # Guardar respuesta de IA
    AIMessage.objects.create(
        conversation=conversation,
        role='assistant',
        content=response_text
    )
    
    # Registrar tokens usados
    try:
        usage = data.get('usageMetadata', {})
        token_count = (usage.get('promptTokenCount', 0) or 0) + (usage.get('candidatesTokenCount', 0) or 0)
        if token_count:
            ai_config.add_tokens_used(token_count)
    except Exception:
        pass
    
    return response_text


@login_required(login_url='login')
def update_ai_config(request):
    """Actualizar configuración de IA del usuario"""
    if request.method == 'POST':
        profile = request.user.profile
        ai_config = profile.ai_config
        
        api_key = request.POST.get('user_api_key', '').strip()
        uses_personal_key = request.POST.get('uses_personal_key', False) == 'on'
        
        if api_key:
            ai_config.user_api_key = api_key
            ai_config.uses_personal_key = True
        else:
            ai_config.uses_personal_key = False
        
        ai_config.save()
        messages.success(request, 'Configuración de IA actualizada.')
        return redirect('korva_ai')
    
    return redirect('korva_ai')


@login_required(login_url='login')
def quick_prompts(request):
    """Prompts rápidos predefinidos para consultas comunes"""
    
    quick_prompts_list = [
        {
            'title': 'Plan de Negocio',
            'prompt': '¿Cuáles son los pasos principales para crear un plan de negocio exitoso?',
            'icon': 'fa-chart-line'
        },
        {
            'title': 'Registro RUC',
            'prompt': '¿Cómo registro mi empresa en el RUC de Nicaragua?',
            'icon': 'fa-document'
        },
        {
            'title': 'Envíos Nacionales',
            'prompt': '¿Cuáles son las mejores opciones para envíos a nivel nacional en Nicaragua?',
            'icon': 'fa-truck'
        },
        {
            'title': 'Impuestos',
            'prompt': '¿Cuáles son mis obligaciones fiscales como PyME en Nicaragua?',
            'icon': 'fa-percentage'
        },
        {
            'title': 'Marketing Digital',
            'prompt': '¿Cómo puedo mejorar mi presencia digital y alcanzar más clientes?',
            'icon': 'fa-bullhorn'
        },
        {
            'title': 'Estrategia Korva',
            'prompt': '¿Cómo puedo aprovechar al máximo la plataforma Korva para crecer?',
            'icon': 'fa-rocket'
        },
    ]
    
    return JsonResponse({'prompts': quick_prompts_list})
