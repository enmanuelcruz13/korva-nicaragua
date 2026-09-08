from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Product
from .forms import ProductForm

def marketplace(request):
    """Vista principal del marketplace"""
    products = Product.objects.select_related('user').filter(is_active=True)
    
    # Filtrar por categoría
    category = request.GET.get('category')
    if category:
        products = products.filter(category=category)
    
    # Buscar productos
    search_query = request.GET.get('q')
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(user__business_name__icontains=search_query)
        )
    
    # Ordenar
    sort_by = request.GET.get('sort', '-created_at')
    products = products.order_by(sort_by)
    
    context = {
        'products': products,
        'category': category,
        'search_query': search_query,
    }
    
    return render(request, 'marketplace/marketplace.html', context)


@login_required(login_url='login')
def create_product(request):
    """Vista para crear un nuevo producto"""
    try:
        if request.method == 'POST':
            form = ProductForm(request.POST, request.FILES)
            if form.is_valid():
                product = form.save(commit=False)
                product.user = request.user.profile
                product.save()
                messages.success(request, 'Producto publicado exitosamente.')
                return redirect('marketplace')
        else:
            form = ProductForm()
        
        return render(request, 'marketplace/create_product.html', {'form': form})
    except Exception as e:
        messages.error(request, f'Error al crear producto: {str(e)}')
        return redirect('marketplace')


def product_detail(request, product_id):
    """Vista de detalle de un producto"""
    try:
        product = get_object_or_404(Product, pk=product_id)
        product.views_count += 1
        product.save()
        
        # Productos similares
        similar_products = Product.objects.filter(
            category=product.category,
            is_active=True
        ).exclude(pk=product.pk)[:5]
        
        context = {
            'product': product,
            'similar_products': similar_products,
        }
        
        return render(request, 'marketplace/product_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar el producto: {str(e)}')
        return redirect('marketplace')


@login_required(login_url='login')
def edit_product(request, product_id):
    """Editar un producto"""
    try:
        product = get_object_or_404(Product, pk=product_id)
        
        if product.user != request.user.profile:
            messages.error(request, 'No tienes permiso para editar este producto.')
            return redirect('product_detail', product_id=product.pk)
        
        if request.method == 'POST':
            form = ProductForm(request.POST, request.FILES, instance=product)
            if form.is_valid():
                form.save()
                messages.success(request, 'Producto actualizado.')
                return redirect('product_detail', product_id=product.pk)
        else:
            form = ProductForm(instance=product)
        
        return render(request, 'marketplace/edit_product.html', {'form': form, 'product': product})
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('marketplace')


@login_required(login_url='login')
def delete_product(request, product_id):
    """Eliminar un producto"""
    try:
        product = get_object_or_404(Product, pk=product_id)
        
        if product.user != request.user.profile:
            messages.error(request, 'No tienes permiso para eliminar este producto.')
            return redirect('product_detail', product_id=product.pk)
        
        if request.method == 'POST':
            product.delete()
            messages.success(request, 'Producto eliminado.')
            return redirect('marketplace')
        
        return render(request, 'marketplace/confirm_delete.html', {'product': product})
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('marketplace')


@login_required(login_url='login')
def my_products(request):
    """Ver los productos del usuario actual"""
    try:
        products = request.user.profile.products.all()
        
        context = {
            'products': products,
        }
        
        return render(request, 'marketplace/my_products.html', context)
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('marketplace')


def product_contact(request, product_id):
    """Registra la consulta de un producto y redirige a WhatsApp (o a la conversación)"""
    product = get_object_or_404(Product, pk=product_id)

    if not product.is_active:
        return redirect('marketplace')

    # Registrar consulta y notificar al vendedor (solo usuarios autenticados)
    if request.user.is_authenticated and request.user.profile != product.user:
        try:
            from notifications.services import notify
            notify(
                user=product.user.user,
                notification_type='product_inquiry',
                title=f'{request.user.profile.business_name} está interesado en tu producto',
                message=product.name[:150],
                url=f'/product/{product.pk}/',
                sender=request.user,
                related_object_id=product.pk,
                related_object_type='product',
            )
        except Exception:
            pass

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})

    return redirect(product.whatsapp_message_url)

