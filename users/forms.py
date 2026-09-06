from django import forms
from django.contrib.auth.models import User
from .models import Profile

class UserRegistrationForm(forms.Form):
    """Formulario para registrar nuevos usuarios"""
    
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'korva-input w-full',
            'placeholder': 'Nombre de usuario'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'korva-input w-full',
            'placeholder': 'Correo electrónico'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'korva-input w-full',
            'placeholder': 'Contraseña'
        })
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'korva-input w-full',
            'placeholder': 'Confirmar contraseña'
        })
    )
    business_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'korva-input w-full',
            'placeholder': 'Nombre comercial de tu empresa'
        })
    )
    ruc = forms.CharField(
        max_length=17,
        widget=forms.TextInput(attrs={
            'class': 'korva-input w-full',
            'placeholder': 'RUC (ej: J0310000123456)'
        })
    )
    city = forms.ChoiceField(
        choices=Profile.CITY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'korva-input w-full'
        })
    )
    sector = forms.ChoiceField(
        choices=Profile.SECTOR_CHOICES,
        widget=forms.Select(attrs={
            'class': 'korva-input w-full'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        username = cleaned_data.get('username')
        
        if password and password_confirm:
            if password != password_confirm:
                raise forms.ValidationError("Las contraseñas no coinciden.")
        
        if username:
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("El nombre de usuario ya está en uso.")
        
        return cleaned_data


class ProfileUpdateForm(forms.ModelForm):
    """Formulario para actualizar el perfil"""
    
    class Meta:
        model = Profile
        fields = ['business_name', 'logo', 'banner', 'ruc', 'city', 'sector', 'bio', 'latitude', 'longitude']
        widgets = {
            'business_name': forms.TextInput(attrs={
                'class': 'korva-input w-full',
                'placeholder': 'Nombre comercial'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'korva-input w-full',
                'placeholder': 'Cuéntanos sobre tu empresa',
                'rows': 4
            }),
            'logo': forms.FileInput(attrs={
                'class': 'block w-full text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-korva-success file:text-white hover:file:bg-green-600'
            }),
            'banner': forms.FileInput(attrs={
                'class': 'block w-full text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-korva-success file:text-white hover:file:bg-green-600'
            }),
            'city': forms.Select(attrs={
                'class': 'korva-input w-full'
            }),
            'sector': forms.Select(attrs={
                'class': 'korva-input w-full'
            }),
            'latitude': forms.HiddenInput(attrs={'id': 'id_latitude'}),
            'longitude': forms.HiddenInput(attrs={'id': 'id_longitude'}),
        }
