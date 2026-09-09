from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator
from django.utils import timezone
from datetime import timedelta
import uuid

class EmailVerificationToken(models.Model):
    """Token para verificación de email"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification_token')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            from django.conf import settings
            hours = getattr(settings, 'EMAIL_VERIFICATION_TIMEOUT_HOURS', 24)
            self.expires_at = timezone.now() + timedelta(hours=hours)
        super().save(*args, **kwargs)
    
    def is_valid(self):
        return timezone.now() < self.expires_at
    
    def __str__(self):
        return f"Token para {self.user.email}"

class Profile(models.Model):
    """Modelo extendido de Usuario para PyMEs"""
    
    SECTOR_CHOICES = [
        ('alimentos', 'Alimentos'),
        ('agropecuario', 'Agropecuario'),
        ('artesanias', 'Artesanías'),
        ('tecnologia', 'Tecnología'),
        ('textil', 'Textil'),
        ('servicios', 'Servicios'),
        ('otros', 'Otros'),
    ]
    
    CITY_CHOICES = [
        ('managua', 'Managua'),
        ('ciudad_sandino', 'Ciudad Sandino'),
        ('tipitapa', 'Tipitapa'),
        ('masaya', 'Masaya'),
        ('esteli', 'Estelí'),
        ('leon', 'León'),
        ('la_paz_centro', 'La Paz Centro'),
        ('granada', 'Granada'),
        ('jinotepe', 'Jinotepe'),
        ('diriamba', 'Diriamba'),
        ('jinotega', 'Jinotega'),
        ('matagalpa', 'Matagalpa'),
        ('chinandega', 'Chinandega'),
        ('somotillo', 'Somotillo'),
        ('el_viejo', 'El Viejo'),
        ('posoltega', 'Posoltega'),
        ('boaco', 'Boaco'),
        ('juigalpa', 'Juigalpa'),
        ('rivas', 'Rivas'),
        ('somoto', 'Somoto'),
        ('ocotal', 'Ocotal'),
        ('san_carlos', 'San Carlos'),
        ('bluefields', 'Bluefields'),
        ('nueva_guinea', 'Nueva Guinea'),
        ('bilwi', 'Bilwi (Puerto Cabezas)'),
        ('otra', 'Otra'),
    ]
    
    TIER_CHOICES = [
        ('bronce', 'PyME Nivel Bronce 🟢'),
        ('plata', 'PyME Nivel Plata ⚪'),
        ('oro', 'PyME Nivel Oro 🟡'),
        ('vip', 'Corporativo VIP 🟣'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    business_name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)
    banner = models.ImageField(upload_to='banners/', null=True, blank=True)
    ruc = models.CharField(
        max_length=17,
        unique=True,
        validators=[MinLengthValidator(14)],
        help_text="Ejemplo: J0310000123456"
    )
    verified = models.BooleanField(default=False, help_text="✓ Sello Oficial de Verificación")
    city = models.CharField(max_length=50, choices=CITY_CHOICES)
    sector = models.CharField(max_length=50, choices=SECTOR_CHOICES)
    latitude = models.FloatField(null=True, blank=True, help_text="Latitud para el mapa")
    longitude = models.FloatField(null=True, blank=True, help_text="Longitud para el mapa")
    popularity_score = models.IntegerField(default=0)
    followers_count = models.IntegerField(default=0)
    associates_count = models.IntegerField(default=0)
    collaborations_count = models.IntegerField(default=0)
    bio = models.TextField(blank=True, null=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-popularity_score']
    
    def __str__(self):
        return f"{self.business_name} ({self.user.username})"
    
    @property
    def tier(self):
        """Calcula el rango dinámico basado en popularity_score"""
        if self.popularity_score >= 5000:
            return 'vip'
        elif self.popularity_score >= 2500:
            return 'oro'
        elif self.popularity_score >= 1000:
            return 'plata'
        else:
            return 'bronce'
    
    @property
    def tier_display(self):
        """Retorna el display text del tier"""
        tiers = dict(self.TIER_CHOICES)
        tier_key = self.tier
        for key, value in self.TIER_CHOICES:
            if key == tier_key:
                return value
        return self.TIER_CHOICES[0][1]
    
    def validate_ruc(self):
        """Valida el formato del RUC nicaragüense"""
        if not self.ruc:
            return False
        # RUC debe empezar con letra (J o P) y tener longitud de 14-17 caracteres
        if len(self.ruc) < 14 or len(self.ruc) > 17:
            return False
        if self.ruc[0] not in ['J', 'P']:
            return False
        return True
    
    def save(self, *args, **kwargs):
        """Sobreescribe save para otorgar bono de verificación"""
        is_new_verified = False
        
        # Verificar si es un nuevo verificado
        if self.pk:
            old_profile = Profile.objects.get(pk=self.pk)
            if not old_profile.verified and self.verified and self.validate_ruc():
                is_new_verified = True
        
        super().save(*args, **kwargs)
        
        # Otorgar bono de +1000 pts si se verifica
        if is_new_verified:
            self.popularity_score += 1000
            super().save(*args, **kwargs)


class ProfileFollow(models.Model):
    """Relación de seguir/dejar de seguir entre perfiles"""
    follower = models.ForeignKey(Profile, related_name='following_rel', on_delete=models.CASCADE)
    following = models.ForeignKey(Profile, related_name='followers_rel', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.follower.user.username} sigue a {self.following.user.username}"

