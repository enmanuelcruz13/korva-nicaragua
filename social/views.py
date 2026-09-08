from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from .models import Post, Comment, PostImage, Vote
from .forms import PostForm, CommentForm, PostImageForm
from users.models import Profile, ProfileFollow
from marketplace.models import Product

def home(request):
    """Vista principal - Landing si no autenticado, Muro Social si autenticado"""
    if not request.user.is_authenticated:
        return render(request, 'landing.html')
    
    try:
        posts = Post.objects.select_related('author').all()
        
        # Buscar posts
        search_query = request.GET.get('q')
        if search_query:
            posts = posts.filter(
                Q(title__icontains=search_query) |
                Q(content__icontains=search_query) |
                Q(author__business_name__icontains=search_query)
            )
        
        # Productos destacados del marketplace y posts de alianza
        products = Product.objects.filter(is_active=True).select_related('user')
        alliance_posts = Post.objects.filter(
            Q(tags__name__icontains='alianza') |
            Q(tags__name__icontains='oportunidad') |
            Q(title__icontains='alianza') |
            Q(content__icontains='alianza')
        ).select_related('author').distinct()[:6]

        # Para el muro: cada post muestra la imagen real de un producto del
        # marketplace perteneciente al autor del post (no imágenes aleatorias)
        post_authors = set(p.author_id for p in posts)
        products_by_author = {}
        for prod in Product.objects.filter(user_id__in=post_authors, image__isnull=False).select_related('user'):
            products_by_author.setdefault(prod.user_id, []).append(prod)
        for p in posts:
            author_products = products_by_author.get(p.author_id, [])
            if author_products:
                p.product_image_url = author_products[0].image.url

        # Estadísticas generales para el índice del muro
        stats = {
            'empresas': Profile.objects.count(),
            'productos': Product.objects.filter(is_active=True).count(),
            'publicaciones': Post.objects.count(),
            'alianzas': Post.objects.filter(
                Q(tags__name__icontains='alianza') |
                Q(tags__name__icontains='oportunidad')
            ).distinct().count(),
        }

        # Conversaciones recientes del usuario
        from messaging.models import Conversation, Message
        conversations = []
        user_profile = request.user.profile
        conv_qs = Conversation.objects.filter(
            Q(user1=user_profile) | Q(user2=user_profile)
        ).select_related('user1', 'user2').order_by('-updated_at')[:6]

        for conv in conv_qs:
            other = conv.get_other_user(user_profile)
            last_msg = conv.get_messages().last()
            conversations.append({
                'conv': conv,
                'other': other,
                'last_message': last_msg.content[:90] if last_msg and last_msg.content else
                                ('📷 Imagen' if last_msg and last_msg.image else
                                 ('🎬 Video' if last_msg and last_msg.video else 'Sin mensajes')),
                'last_ts': last_msg.timestamp if last_msg else conv.updated_at,
                'last_sender_name': last_msg.sender.business_name if last_msg else '',
            })

        # Recomendaciones: negocios del mismo sector y ciudad, para seguir
        recommended = []
        following_ids = list(
            ProfileFollow.objects.filter(follower=user_profile).values_list('following_id', flat=True)
        )
        base_qs = Profile.objects.exclude(pk=user_profile.pk)
        if following_ids:
            base_qs = base_qs.exclude(pk__in=following_ids)

        sector_qs = base_qs.filter(sector=user_profile.sector).order_by('-popularity_score')[:3]
        recommended.extend(sector_qs)
        chosen_ids = [p.pk for p in recommended]

        city_qs = base_qs.exclude(pk__in=chosen_ids).filter(city=user_profile.city).order_by('-popularity_score')[:3]
        recommended.extend(city_qs)
        chosen_ids = [p.pk for p in recommended]

        if len(recommended) < 6:
            extras = base_qs.exclude(pk__in=chosen_ids).order_by('-popularity_score')[: 6 - len(recommended)]
            recommended.extend(extras)

        context = {
            'posts': posts,
            'search_query': search_query,
            'products': products,
            'alliance_posts': alliance_posts,
            'stats': stats,
            'conversations': conversations,
            'recommended': recommended,
        }
        
        return render(request, 'social/home.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar el muro: {str(e)}')
        return redirect('home')


@login_required(login_url='login')
def alliances(request):
    """Página de Alianzas - posts de alianza y oportunidades de negocio"""
    posts = Post.objects.filter(
        Q(tags__name__icontains='alianza') |
        Q(tags__name__icontains='oportunidad') |
        Q(title__icontains='alianza') |
        Q(content__icontains='alianza')
    ).select_related('author').distinct().order_by('-timestamp')

    search_query = request.GET.get('q')
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query) |
            Q(author__business_name__icontains=search_query)
        )

    context = {
        'alliance_posts': posts,
        'search_query': search_query,
    }
    return render(request, 'social/alliances.html', context)


@login_required(login_url='login')
def create_post(request):
    """Vista para crear un nuevo post"""
    try:
        if request.method == 'POST':
            form = PostForm(request.POST, request.FILES)
            if form.is_valid():
                post = form.save(commit=False)
                post.author = request.user.profile
                post.save()
                form.save_m2m()  # Guardar tags
                
                # Guardar imágenes adicionales (galería)
                gallery_images = request.FILES.getlist('gallery')
                for img in gallery_images:
                    PostImage.objects.create(post=post, image=img)
                
                messages.success(request, 'Post publicado exitosamente.')
                return redirect('home')
        else:
            form = PostForm()
            if request.GET.get('tipo') == 'alianza':
                form.fields['tags'].initial = 'alianza, oportunidad'
                form.fields['title'].widget.attrs['placeholder'] = 'Título de tu alianza (ej: Buscamos proveedor de...)'
        
        return render(request, 'social/create_post.html', {'form': form})
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('home')


def post_detail(request, post_id):
    """Vista de detalle de un post"""
    try:
        post = get_object_or_404(Post, pk=post_id)
        comments = post.comments.all()
        
        if request.method == 'POST' and request.user.is_authenticated:
            form = CommentForm(request.POST)
            if form.is_valid():
                comment = form.save(commit=False)
                comment.post = post
                comment.author = request.user.profile
                comment.save()
                messages.success(request, 'Comentario publicado.')

                # Notificación al autor del post
                if post.author.user != request.user:
                    try:
                        from notifications.services import notify
                        notify(
                            user=post.author.user,
                            notification_type='comment',
                            title=f'{request.user.username} comentó en tu publicación',
                            message=comment.content[:150],
                            url=f'/comunidad/post/{post.pk}/',
                            sender=request.user,
                            related_object_id=comment.pk,
                            related_object_type='comment',
                        )
                    except Exception:
                        pass

                return redirect('post_detail', post_id=post.pk)
        else:
            form = CommentForm()
        
        context = {
            'post': post,
            'comments': comments,
            'form': form,
        }
        
        return render(request, 'social/post_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('home')


@login_required(login_url='login')
@require_POST
def upvote_post(request, post_id):
    """Aumentar votos positivos en un post (un voto por usuario)"""
    try:
        post = get_object_or_404(Post, pk=post_id)
        user_profile = request.user.profile
        
        # Verificar si ya votó
        existing_vote = Vote.objects.filter(user=user_profile, post=post).first()
        
        if existing_vote:
            if existing_vote.vote_type == 'up':
                # Ya votó up, quitar voto
                existing_vote.delete()
                post.upvotes = max(0, post.upvotes - 1)
                post.author.popularity_score = max(0, post.author.popularity_score - 10)
                vote_action = 'removed'
            else:
                # Cambió de down a up
                existing_vote.vote_type = 'up'
                existing_vote.save()
                post.upvotes += 1
                post.downvotes = max(0, post.downvotes - 1)
                post.author.popularity_score += 15  # +10 up +5 por quitar down
                vote_action = 'changed_to_up'
        else:
            # Nuevo voto up
            Vote.objects.create(user=user_profile, post=post, vote_type='up')
            post.upvotes += 1
            post.author.popularity_score += 10
            vote_action = 'upvoted'
        
        post.author.save()
        post.save()

        # Notificación de nuevo me gusta (solo cuando se agrega el voto)
        if vote_action in ('upvoted', 'changed_to_up') and post.author.user != request.user:
            try:
                from notifications.services import notify
                notify(
                    user=post.author.user,
                    notification_type='like',
                    title=f'{request.user.username} reaccionó a tu publicación',
                    message=post.content[:150] if post.content else 'Te ha dado un me gusta',
                    url=f'/comunidad/post/{post.pk}/',
                    sender=request.user,
                    related_object_id=post.pk,
                    related_object_type='post',
                )
            except Exception:
                pass
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'upvotes': post.upvotes,
                'downvotes': post.downvotes,
                'author_score': post.author.popularity_score,
                'action': vote_action,
                'user_vote': 'up' if vote_action in ['upvoted', 'changed_to_up'] else None
            })
        
        return redirect('post_detail', post_id=post.pk)
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': str(e)}, status=400)
        messages.error(request, f'Error: {str(e)}')
        return redirect('post_detail', post_id=post_id)


@login_required(login_url='login')
@require_POST
def downvote_post(request, post_id):
    """Disminuir votos en un post"""
    try:
        post = get_object_or_404(Post, pk=post_id)
        post.downvotes += 1
        post.author.popularity_score = max(0, post.author.popularity_score - 5)
        post.author.save()
        post.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'upvotes': post.upvotes,
                'downvotes': post.downvotes,
                'author_score': post.author.popularity_score
            })
        
        return redirect('post_detail', post_id=post.pk)
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': str(e)}, status=400)
        messages.error(request, f'Error: {str(e)}')
        return redirect('post_detail', post_id=post_id)


@login_required(login_url='login')
def edit_post(request, post_id):
    """Editar un post existente"""
    try:
        post = get_object_or_404(Post, pk=post_id)
        
        if post.author != request.user.profile:
            messages.error(request, 'No tienes permiso para editar este post.')
            return redirect('post_detail', post_id=post.pk)
        
        if request.method == 'POST':
            form = PostForm(request.POST, request.FILES, instance=post)
            if form.is_valid():
                post = form.save(commit=False)
                post.save()
                form.save_m2m()
                
                # Guardar imágenes adicionales (galería)
                gallery_images = request.FILES.getlist('gallery')
                for img in gallery_images:
                    PostImage.objects.create(post=post, image=img)
                
                messages.success(request, 'Post actualizado.')
                return redirect('post_detail', post_id=post.pk)
        else:
            form = PostForm(instance=post)
        
        return render(request, 'social/edit_post.html', {'form': form, 'post': post})
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('home')


@login_required(login_url='login')
def delete_post(request, post_id):
    """Eliminar un post"""
    try:
        post = get_object_or_404(Post, pk=post_id)
        
        if post.author != request.user.profile:
            messages.error(request, 'No tienes permiso para eliminar este post.')
            return redirect('post_detail', post_id=post.pk)
        
        if request.method == 'POST':
            post.delete()
            messages.success(request, 'Post eliminado.')
            return redirect('home')
        
        return render(request, 'social/confirm_delete.html', {'post': post})
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('home')

