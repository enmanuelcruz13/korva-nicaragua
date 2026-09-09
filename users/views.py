from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from .models import Profile, EmailVerificationToken, ProfileFollow
from django.core.management import call_command
from .forms import UserRegistrationForm, ProfileUpdateForm
from social.models import Post, Comment
from marketplace.models import Product
from core.models import KorvaAIConfig

def send_verification_email(user, request):
    """Envía email de verificación al usuario"""
    token_obj, created = EmailVerificationToken.objects.get_or_create(user=user)
    if not created:
        # Regenerar token si ya existe
        import uuid
        token_obj.token = uuid.uuid4()
        token_obj.save()
    
    verification_url = f"{settings.FRONTEND_URL}/verify-email/{token_obj.token}/"
    
    subject = 'Verifica tu correo electrónico - Korva Nicaragua'
    html_message = render_to_string('auth/verification_email.html', {
        'user': user,
        'verification_url': verification_url,
        'hours': settings.EMAIL_VERIFICATION_TIMEOUT_HOURS,
    })
    
    try:
        send_mail(
            subject,
            f'Verifica tu cuenta en Korva Nicaragua: {verification_url}',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        return False

def register(request):
    """Vista para registrar nuevos usuarios"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            # Crear usuario manualmente (el formulario es forms.Form, no ModelForm)
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password']
            )
            
            # Crear perfil automáticamente
            profile = Profile.objects.create(
                user=user,
                business_name=form.cleaned_data['business_name'],
                city=form.cleaned_data['city'],
                sector=form.cleaned_data['sector'],
                ruc=form.cleaned_data['ruc']
            )
            
            # Crear configuración de IA
            KorvaAIConfig.objects.create(user=profile)
            
            # Enviar email de verificación
            if send_verification_email(user, request):
                messages.success(request, 'Cuenta creada exitosamente. Hemos enviado un correo de verificación a tu email.')
            else:
                messages.warning(request, 'Cuenta creada, pero no pudimos enviar el email de verificación. Contacta a soporte.')
            
            # Iniciar sesión automáticamente
            login(request, user)
            return redirect('home')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'auth/register.html', {'form': form})

def verify_email(request, token):
    """Vista para verificar el email del usuario"""
    try:
        token_obj = EmailVerificationToken.objects.get(token=token)
    except EmailVerificationToken.DoesNotExist:
        messages.error(request, 'Token de verificación inválido.')
        return redirect('login')
    
    if not token_obj.is_valid():
        messages.error(request, 'El token de verificación ha expirado.')
        token_obj.delete()
        return redirect('login')
    
    user = token_obj.user
    user.is_active = True
    user.save()
    
    token_obj.delete()
    
    messages.success(request, '¡Correo verificado exitosamente! Ya puedes iniciar sesión.')
    return redirect('login')


def login_view(request):
    """Vista para iniciar sesión"""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        if username == 'admin':
            call_command('ensure_admin')

        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido {user.username}!')
            return redirect('home')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    
    return render(request, 'auth/login.html', {
        'korva_social_providers': korva_social_providers(),
    })


def korva_social_providers():
    """Devuelve la lista de proveedores OAuth con SocialApp configurada (login social)."""
    from allauth.socialaccount.models import SocialApp
    return list(
        SocialApp.objects
        .filter(provider__in=['google', 'facebook', 'instagram'])
        .values_list('provider', flat=True)
        .distinct()
    )


def logout_view(request):
    """Vista para cerrar sesión"""
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente.')
    return redirect('home')


def profile_view(request, username):
    """Vista para ver el perfil de un usuario"""
    try:
        user = get_object_or_404(User, username=username)
        profile = user.profile
        
        # Obtener posts y productos del usuario
        posts = profile.posts.all()[:10]
        products = profile.products.all()[:10]

        # Estado de seguimiento
        is_following = False
        if request.user.is_authenticated and request.user.profile != profile:
            is_following = ProfileFollow.objects.filter(
                follower=request.user.profile, following=profile
            ).exists()

        context = {
            'profile': profile,
            'user_obj': user,
            'posts': posts,
            'products': products,
            'is_following': is_following,
        }
        
        return render(request, 'users/profile.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar el perfil: {str(e)}')
        return redirect('home')


@login_required(login_url='login')
@require_POST
def toggle_follow(request, username):
    """Seguir o dejar de seguir a un usuario"""
    try:
        user = get_object_or_404(User, username=username)
        target = user.profile
        follower = request.user.profile

        if target == follower:
            messages.error(request, 'No puedes seguirte a ti mismo.')
            return redirect('profile', username=username)

        follow = ProfileFollow.objects.filter(follower=follower, following=target).first()
        if follow:
            follow.delete()
            target.followers_count = max(0, target.followers_count - 1)
            target.save(update_fields=['followers_count'])
            following = False
        else:
            ProfileFollow.objects.create(follower=follower, following=target)
            target.followers_count += 1
            target.save(update_fields=['followers_count'])
            following = True

            # Notificación + push de nuevo seguidor
            try:
                from notifications.services import notify
                notify(
                    user=target.user,
                    notification_type='follow',
                    title=f'{request.user.profile.business_name} empezó a seguirte',
                    message='Nuevo seguidor en Korva Nicaragua',
                    url=f'/profile/{request.user.username}/',
                    sender=request.user,
                    related_object_id=target.pk,
                    related_object_type='profile',
                )
            except Exception:
                pass

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'following': following, 'followers': target.followers_count})

        return redirect('profile', username=username)
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': str(e)}, status=400)
        messages.error(request, f'Error: {str(e)}')
        return redirect('profile', username=username)


@login_required(login_url='login')
def edit_profile(request):
    """Vista para editar el perfil del usuario"""
    profile = request.user.profile
    
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            # Si no hay coordenadas todavía, intentar geocodificar la ciudad (OSM Nominatim)
            if not profile.latitude and profile.city != 'otra':
                try:
                    from core.geocode import ensure_geo
                    ensure_geo(profile)
                except Exception:
                    pass
            messages.success(request, 'Perfil actualizado correctamente.')
            return redirect('profile', username=request.user.username)
    else:
        form = ProfileUpdateForm(instance=profile)
    
    return render(request, 'users/edit_profile.html', {'form': form, 'profile': profile})


@login_required(login_url='login')
def dashboard(request):
    """Vista del dashboard principal del usuario"""
    profile = request.user.profile
    
    context = {
        'profile': profile,
        'total_posts': profile.posts.count(),
        'total_products': profile.products.count(),
        'followers': profile.followers_count,
        'collaborations': profile.collaborations_count,
    }
    
    return render(request, 'users/dashboard.html', context)


def setup_admin(request):
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser(username='admin', email='admin@korva.com', password='admin123')
        profile = Profile.objects.get(user__username='admin')
        profile.business_name = 'Korva Admin'
        profile.ruc = 'J0310000000000'
        profile.save(update_fields=['business_name', 'ruc'])
        return HttpResponse('Admin created. <a href="/admin/">Login</a>')
    return HttpResponse('Admin already exists. <a href="/admin/">Go to admin</a>')

