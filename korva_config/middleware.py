from django.contrib.sites.models import Site

_LAST_HOST = [None]


class DynamicSiteMiddleware:
    """Mantiene el Site (pk=1) de django.contrib.sites sincronizado con el dominio actual.

    django-allauth exige un Site válido para construir las URLs de callback OAuth,
    por lo tanto se actualiza el dominio del Site cuando cambia el host. Para no
    añadir carga por request se recuerda el último host visto por proceso y la
    escritura se omite si no cambió. Cualquier error se ignora (es un detalle
    cosmético y no debe romper el request ni la suite de tests).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        if _LAST_HOST[0] != host:
            domain = host.split(':')[0]
            try:
                Site.objects.filter(pk=1).update(domain=domain, name=host)
                _LAST_HOST[0] = host
            except Exception:
                pass
        return self.get_response(request)