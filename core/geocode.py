import json
import logging
import time
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

# Coordenadas aproximadas del centro del municipio (fallback)
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
    'san_carlos': (11.4308, -84.7776),
    'bilwi': (14.0358, -83.3786),
}

_CACHE = {}
_LAST_REQUEST = 0.0


def _rate_limit():
    """Respetar la política de uso de Nominatim: max ~1 petición/segundo."""
    global _LAST_REQUEST
    elapsed = time.monotonic() - _LAST_REQUEST
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _LAST_REQUEST = time.monotonic()


def geocode_city(city_display, country='Nicaragua'):
    """Geocodifica una ciudad usando OSM Nominatim. Resultados cacheados."""
    key = (city_display, country)
    if key in _CACHE:
        return _CACHE[key]
    _CACHE[key] = None
    if not city_display or city_display.lower() == 'otra':
        return None

    _rate_limit()
    params = urllib.parse.urlencode({
        'q': f'{city_display}, {country}',
        'format': 'json',
        'limit': 1,
        'accept-language': 'es',
    })
    url = 'https://nominatim.openstreetmap.org/search?' + params
    user_agent = getattr(
        settings, 'NOMINATIM_USER_AGENT',
        'KorvaNicaragua/2.0 (mapa de negocios; contacto: dev@korva.ni)',
    )
    req = urllib.request.Request(url, headers={'User-Agent': user_agent})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if data:
            lat, lng = float(data[0]['lat']), float(data[0]['lon'])
            _CACHE[key] = (lat, lng)
            return lat, lng
    except Exception as e:
        logger.warning('Geocoding falló para "%s": %s', city_display, e)
    return None


def city_coords(city_key):
    """Coordenadas aproximadas de un municipio (fallback rápido, sin red)."""
    return CITY_COORDS.get(city_key)


def resolve_profile_coords(profile):
    """Devuelve (lat, lng) con prioridad: coords del perfil > geocodificación > ciudad aprox. No escribe BD."""
    if profile.latitude is not None and profile.longitude is not None:
        return profile.latitude, profile.longitude
    coords = geocode_city(profile.get_city_display())
    return coords if coords else CITY_COORDS.get(profile.city)


def ensure_geo(profile, persist=True):
    """Completa lat/lng del perfil si faltan (geocodificación real con fallback al municipio)."""
    if profile.latitude is not None and profile.longitude is not None:
        return profile.latitude, profile.longitude
    if profile.city == 'otra':
        return None
    coords = geocode_city(profile.get_city_display())
    if not coords:
        coords = CITY_COORDS.get(profile.city)
    if coords and persist:
        profile.latitude, profile.longitude = coords
        try:
            profile.save(update_fields=['latitude', 'longitude'])
        except Exception as e:
            logger.warning('No se pudo persistir coordenadas de %s: %s', profile, e)
    return coords