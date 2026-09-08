from django.core.management.base import BaseCommand

from core.geocode import CITY_COORDS, _rate_limit, geocode_city


class Command(BaseCommand):
    help = ('Geocodifica (OSM Nominatim) los perfiles sin lat/lng para ubicarlos con precisión en el mapa. '
            'Falla de forma segura al centro del municipio.')

    def handle(self, *args, **options):
        from django.apps import apps
        Profile = apps.get_model('users', 'Profile')

        pending = Profile.objects.filter(
            latitude__isnull=True
        ).exclude(user__username__iexact='admin')

        total = pending.count()
        self.stdout.write(f'Perfiles por ubicar: {total}')

        ok = geocoded = fallback = failed = 0
        for profile in pending.iterator():
            city_display = profile.get_city_display()

            _rate_limit()
            coords = geocode_city(city_display)
            source = 'geo'
            if not coords:
                coords = CITY_COORDS.get(profile.city)
                source = 'ciudad'
            if coords:
                profile.latitude, profile.longitude = coords
                profile.save(update_fields=['latitude', 'longitude'])
                ok += 1
                if source == 'geo':
                    geocoded += 1
                else:
                    fallback += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ {profile.business_name} ({city_display}) [{source}] -> '
                    f'{coords[0]:.4f}, {coords[1]:.4f}'
                ))
            else:
                failed += 1
                self.stdout.write(self.style.WARNING(
                    f'  ? {profile.business_name} ({city_display}): sin coordenadas'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'\nListo: {ok} ubicados ({geocoded} geocodificados, {fallback} por municipio), '
            f'{failed} sin resultado.'
        ))