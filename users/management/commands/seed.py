from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
from django.apps import apps
from django.contrib.auth.models import User
from users.models import Profile
from core.geocode import CITY_COORDS
import os

# Un negocio de ejemplo por departamento/región (cubren las 17 unidades administrativas)
DEPARTMENT_BUSINESSES = [
    ('tostadora_matagalpa', 'Tostadora Matagalpa Café', 'matagalpa', 'alimentos',
     'Tostamos café de altura de las cumbres de Matagalpa para toda Nicaragua.', 2700),
    ('cafe_jinotepe', 'Café Fincas de Jinotepe', 'jinotepe', 'agropecuario',
     'Café de sombra cultivado en las fincas del departamento de Carazo.', 1400),
    ('ganadera_boaco', 'Ganadería Boaco Norte', 'boaco', 'agropecuario',
     'Ganadería de doble propósito con siglos de tradición en las llanuras de Boaco.', 900),
    ('carnicos_juigalpa', 'Cárnicos Juigalpa', 'juigalpa', 'alimentos',
     'Carnes y embutidos de la ganadería de Chontales, la capital de la carne.', 1100),
    ('termales_somoto', 'Termales Somoto', 'somoto', 'servicios',
     'Aguas termales y turismo de aventura en el cañón de Somoto, Madriz.', 1800),
    ('cafe_segoviano', 'Café Segoviano Ocotal', 'ocotal', 'agropecuario',
     'Café de altura del norte de Nueva Segovia, premiado internacionalmente.', 3200),
    ('agroturismo_ometepe', 'Agroturismo Ometepe', 'rivas', 'servicios',
     'Fincas y senderismo en la isla de Ometepe, Rivas. Dos volcanes, una isla.', 4400),
    ('pescaderia_corinto', 'Pescadería Corinto', 'chinandega', 'alimentos',
     'Mariscos frescos del puerto de Corinto, Chinandega.', 1300),
    ('ecoturismo_san_carlos', 'Ecoturismo Río San Juan', 'san_carlos', 'servicios',
     'Explora el río San Juan y la reserva de El Castillo, Río San Juan.', 800),
    ('pesquera_bluefields', 'Pesquera Mar Caribe Bluefields', 'bluefields', 'alimentos',
     'Pesca artesanal y camarones del Caribe Sur, Bluefields.', 5600),
    ('miskitos_bilwi', 'Productos Miskitos Bilwi', 'bilwi', 'artesanias',
     'Artesanía y productos de la costa caribeña norte, Bilwi (Puerto Cabezas).', 1150),
    ('maderas_nueva_guinea', 'Maderas Nueva Guinea', 'nueva_guinea', 'otros',
     'Maderas finas y aserradero en el corazón de la RAAS, Nueva Guinea.', 950),
    ('agro_tipitapa', 'Agro Tipitapa', 'tipitapa', 'agropecuario',
     'Granos y ventas agropecuarias en la puerta de Managua.', 750),
    ('servicios_ciudad_sandino', 'Servicios Ciudad Sandino', 'ciudad_sandino', 'servicios',
     'Servicios profesionales para hogares y empresas de Ciudad Sandino.', 850),
]


class Command(BaseCommand):
    help = 'Carga datos seed (usuarios, productos, posts, mensajes) desde el fixture JSON. Idempotente.'

    def handle(self, *args, **options):
        fixture_path = os.path.join(settings.BASE_DIR, '_fixture_seed.json')
        Product = apps.get_model('marketplace', 'Product')
        if Product.objects.exists():
            self.stdout.write(self.style.WARNING('Ya existen productos, se omite seed para evitar duplicados.'))
        elif not os.path.exists(fixture_path):
            self.stdout.write(self.style.WARNING('No se encontró _fixture_seed.json, se omite seed.'))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING('Cargando datos seed...'))
            try:
                call_command('loaddata', fixture_path, verbosity=0)
                self.stdout.write(self.style.SUCCESS('Datos seed cargados correctamente.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error cargando seed: {e}'))

        self._ensure_department_businesses()

    def _ensure_department_businesses(self):
        """Garantiza un negocio por departamento (idempotente por nombre de usuario)."""
        created = 0
        updated = 0
        for idx, spec in enumerate(DEPARTMENT_BUSINESSES, start=1):
            username, name, city, sector, bio, score = spec
            profile = Profile.objects.filter(user__username__iexact=username).first()
            if profile and not profile.ruc.startswith('TMP'):
                # Ya fue sembrado correctamente en una corrida previa
                continue
            user = profile.user if profile else \
                User.objects.filter(username__iexact=username).first()
            if not user:
                user = User.objects.create_user(
                    username=username,
                    email=f'{username}@korva.ni'.replace('_', ''),
                    password='test1234',
                    first_name=name,
                )
                created += 1
            else:
                updated += 1
            coords = CITY_COORDS.get(city)
            if not coords:
                self.stdout.write(self.style.WARNING(f'  Sin coordenadas para {city}, se omite {username}.'))
                continue
            lat, lng = coords
            profile = profile or user.profile
            profile.business_name = name
            profile.city = city
            profile.sector = sector
            profile.bio = bio
            profile.popularity_score = score
            profile.latitude = lat
            profile.longitude = lng
            profile.verified = True
            profile.ruc = f'J0200{202400000000 + idx * 1000}'
            profile.followers_count = 20 + idx * 3
            profile.associates_count = 2 + idx
            profile.collaborations_count = 1 + idx
            profile.save()
            # El guardado del sello de verificación puede añadir +1000 pts; se reafirma el score exacto
            Profile.objects.filter(pk=profile.pk).update(popularity_score=score)
            self.stdout.write(self.style.SUCCESS(f'  ✓ {username} ({city})'))
        self.stdout.write(self.style.SUCCESS(f'Negocios por departamento listos (creados: {created}, actualizados: {updated}).'))