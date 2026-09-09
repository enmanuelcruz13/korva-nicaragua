from django.conf import settings
from django.db import migrations


def create_default_site(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    domain = getattr(settings, 'FRONTEND_URL', 'http://localhost:8000').split('://')[-1].split('/')[0]
    Site.objects.get_or_create(
        pk=1,
        defaults={'domain': domain, 'name': 'Korva Nicaragua'},
    )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_profilefollow'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(create_default_site, migrations.RunPython.noop),
    ]