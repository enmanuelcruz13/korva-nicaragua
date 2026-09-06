import unicodedata

from django.http import JsonResponse
from django.shortcuts import render
from users.models import Profile


def _norm(s):
    """Normaliza texto: minúsculas y sin acentos para búsqueda tolerante"""
    s = unicodedata.normalize('NFD', str(s))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower()


CITY_COORDS = {
    'managua': (12.1328, -86.2504),
    'masaya': (11.9745, -86.0961),
    'esteli': (13.0851, -86.3630),
    'leon': (12.4348, -86.8788),
    'granada': (11.9344, -85.9560),
    'jinotega': (13.0884, -85.9994),
    'matagalpa': (12.9290, -85.9151),
    'chinandega': (12.6235, -87.1273),
    'rivas': (11.4327, -85.8230),
    'bluefields': (12.0111, -83.7704),
    'juigalpa': (12.0963, -85.3705),
    'ocotal': (13.6289, -86.4845),
    'somoto': (13.4800, -86.5820),
    'boaco': (12.4700, -85.6600),
    'diriamba': (11.8586, -86.2413),
    'jinotepe': (11.8496, -86.1995),
    'nueva_guinea': (11.6932, -84.4540),
    'somotillo': (13.0500, -86.9100),
    'el_viejo': (12.6583, -87.1672),
    'tipitapa': (12.2723, -86.0530),
    'ciudad_sandino': (12.1565, -86.3529),
    'posoltega': (12.5430, -86.9790),
    'la_paz_centro': (12.3400, -86.6600),
}


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
            'profile_url': f'/profile/{p.user.username}/',
        })
    return businesses


def business_map(request):
    """Página del mapa de negocios con filtros"""
    city = request.GET.get('city', '')
    sector = request.GET.get('sector', '')
    q = request.GET.get('q', '').strip()

    profiles = Profile.objects.select_related('user') \
        .exclude(user__username__iexact='admin')

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
        .exclude(user__username__iexact='admin')
    if city:
        profiles = profiles.filter(city=city)
    if sector:
        profiles = profiles.filter(sector=sector)

    businesses = _filter_by_query(_businesses_data(profiles), q)

    return JsonResponse({'businesses': businesses})