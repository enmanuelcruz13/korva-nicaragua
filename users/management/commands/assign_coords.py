from django.core.management.base import BaseCommand
from django.apps import apps


class Command(BaseCommand):
    help = 'Asigna coordenadas (lat/lng) a los perfiles según su ciudad. Para el mapa de negocios.'

    # Coordenadas aprox. de ciudades de Nicaragua (centro del municipio)
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
        'ochomogo': (12.0100, -85.9500),
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

    def handle(self, *args, **options):
        Profile = apps.get_model('users', 'Profile')
        updated = 0
        skipped = 0
        for profile in Profile.objects.all():
            coords = self.CITY_COORDS.get(profile.city)
            if coords:
                profile.latitude, profile.longitude = coords
                profile.save(update_fields=['latitude', 'longitude'])
                updated += 1
                self.stdout.write(f"  ✓ {profile.business_name} ({profile.get_city_display()}) -> {coords}")
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f"  ? {profile.business_name}: ciudad '{profile.city}' sin coordenadas - usar 'otra' manualmente"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"\nListo: {updated} perfiles con ubicación asignada, {skipped} sin coincidencia."
        ))