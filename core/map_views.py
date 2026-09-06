from django.http import JsonResponse
from django.shortcuts import render
from users.models import Profile


def _businesses_data():
    """Retorna lista de negocios con coordenadas para el mapa"""
    businesses = []
    for p in Profile.objects.exclude(latitude=None).exclude(longitude=None) \
            .exclude(user__username__iexact='admin').select_related('user'):
        logo_url = None
        if p.logo:
            logo_url = p.logo.url
        members = getattr(p, 'followers_count', 0) or 0
        businesses.append({
            'id': p.user.username,
            'name': p.business_name,
            'city': p.get_city_display(),
            'sector': p.get_sector_display(),
            'lat': p.latitude,
            'lng': p.longitude,
            'logo': logo_url,
            'verified': p.verified,
            'tier': p.tier,
            'tier_display': p.tier_display,
            'popularity': p.popularity_score,
            'profile_url': f'/profile/{p.user.username}/',
        })
    return businesses


def business_map(request):
    """Página del mapa de negocios"""
    businesses = _businesses_data()
    businesses_json = [
        b for b in businesses
    ]
    return render(request, 'map/map.html', {
        'businesses_json': businesses_json,
        'total': len(businesses_json),
        'title': 'Mapa de Negocios',
    })


def business_map_data(request):
    """API JSON con los negocios para el mapa"""
    return JsonResponse({'businesses': _businesses_data()})