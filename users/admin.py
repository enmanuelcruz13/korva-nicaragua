from django.contrib import admin
from .models import Profile, ProfileFollow

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['business_name', 'user', 'city', 'sector', 'verified', 'popularity_score', 'tier']
    list_filter = ['verified', 'city', 'sector', 'created_at']
    search_fields = ['business_name', 'user__username', 'ruc']
    readonly_fields = ['popularity_score', 'followers_count', 'created_at', 'updated_at']
    actions = ['verify_profiles']
    
    def verify_profiles(self, request, queryset):
        for profile in queryset:
            profile.verified = True
            profile.save()
    verify_profiles.short_description = "Verificar perfiles seleccionados"


@admin.register(ProfileFollow)
class ProfileFollowAdmin(admin.ModelAdmin):
    list_display = ['follower', 'following', 'created_at']
    search_fields = ['follower__user__username', 'following__user__username']
    list_filter = ['created_at']
