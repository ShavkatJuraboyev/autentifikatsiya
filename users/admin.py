from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from users.models import CustomUser, IntegrationApplication

admin.site.register(CustomUser, UserAdmin)

@admin.register(IntegrationApplication)
class IntegrationApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_approved', 'client_id', 'client_secret')
    list_filter = ('is_approved',)
    readonly_fields = ('client_id', 'client_secret')

    def save_model(self, request, obj, form, change):
        if obj.is_approved:
            # ✅ Yangi tasdiqlanganda tokenlar yaratiladi
            if not obj.client_id:
                obj.approve()
        else:
            # ✅ Agar tasdiqlash bekor qilinsa, tokenlar tozalanadi
            obj.client_id = ''
            obj.client_secret = ''
        super().save_model(request, obj, form, change)
