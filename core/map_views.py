import unicodedata

from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from users.models import Profile
from core.geocode import CITY_COORDS


def _norm(s):
    """Normaliza texto: minúsculas y sin acentos para búsqueda tolerante"""
    s = unicodedata.normalize('NFD', str(s))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower()


def _query_profiles(city=None, sector=None, q=None):
    """Query de perfiles con filtros aplicados"""
    profiles = Profile.objects.select_related('user') \
        .exclude(user__username__iexact='admin')

    if city:
        profiles = profiles.filter(city=city)
    if sector:
        profiles = profiles.filter(sector=sector)
    return profiles


def _filter_by_query(businesses, q):
    """Filtra negocios por texto (nombre, ciudad, sector), sin distinguir tildes"""
    if not q:
        return businesses
    ql = _norm(q)
    return [b for b in businesses
            if ql in _norm(b['name']) or ql in _norm(b['city_display'])
            or ql in _norm(b['sector_display'])]


def _businesses_data(profiles):
    """Convierte queryset de perfiles a listas para el mapa"""
    businesses = []
    for p in profiles:
        if p.latitude is None or p.longitude is None:
            coords = CITY_COORDS.get(p.city)
            if not coords:
                continue
            lat, lng = coords
        else:
            lat, lng = p.latitude, p.longitude

        logo_url = p.logo.url if p.logo else None
        businesses.append({
            'id': p.user.username,
            'name': p.business_name,
            'city': p.city,
            'city_display': p.get_city_display(),
            'sector': p.sector,
            'sector_display': p.get_sector_display(),
            'lat': lat,
            'lng': lng,
            'logo': logo_url,
            'verified': p.verified,
            'tier': p.tier,
            'tier_display': p.tier_display,
            'popularity': p.popularity_score,
            'followers': p.followers_count,
            'products_count': getattr(p, 'products_count', 0),
            'bio': (p.bio or '')[:120],
            'profile_url': f'/profile/{p.user.username}/',
        })
    return businesses


def business_map(request):
    """Página del mapa de negocios con filtros"""
    city = request.GET.get('city', '')
    sector = request.GET.get('sector', '')
    q = request.GET.get('q', '').strip()

    profiles = Profile.objects.select_related('user') \
        .exclude(user__username__iexact='admin') \
        .annotate(products_count=Count('products'))

    if city:
        profiles = profiles.filter(city=city)
    if sector:
        profiles = profiles.filter(sector=sector)

    # Filtrar por texto (nombre + bio + ciudad display) en python para simplificar
    businesses = _filter_by_query(_businesses_data(profiles), q)

    return render(request, 'map/map.html', {
        'city': city,
        'sector': sector,
        'q': q,
        'profile_cities': Profile.CITY_CHOICES,
        'profile_sectors': Profile.SECTOR_CHOICES,
        'map_data_url': '/mapa/data/',
        'title': 'Mapa de Negocios',
    })


def business_map_data(request):
    """API JSON con los negocios para el mapa"""
    city = request.GET.get('city', '')
    sector = request.GET.get('sector', '')
    q = request.GET.get('q', '').strip()

    profiles = Profile.objects.select_related('user') \
        .exclude(user__username__iexact='admin') \
        .annotate(products_count=Count('products'))
    if city:
        profiles = profiles.filter(city=city)
    if sector:
        profiles = profiles.filter(sector=sector)

    businesses = _filter_by_query(_businesses_data(profiles), q)

    return JsonResponse({
        'businesses': businesses,
        'total': len(businesses),
    })