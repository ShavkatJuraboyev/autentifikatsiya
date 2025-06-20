from datetime import datetime
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
import secrets

class IntegrationApplication(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    redirect_uri = models.URLField()
    description = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    client_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    client_secret = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name = "Integratsiya dasturi"
        verbose_name_plural = "Integratsiya dasturlari"

    def approve(self):
        self.is_approved = True
        self.client_id = secrets.token_hex(16)
        self.client_secret = secrets.token_hex(32)
        self.save()

    def __str__(self):
        return self.name

class CustomUser(AbstractUser):
    face_image = models.ImageField(upload_to='faces/', null=True, blank=True)
    face_encoding = models.BinaryField(null=True, blank=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)  # ✅ Qo‘shilgan

    def __str__(self):
        return self.username

class AccessToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    app = models.ForeignKey(IntegrationApplication, on_delete=models.CASCADE)
    token = models.CharField(max_length=255)
    created = models.DateTimeField(auto_now_add=True)
    expires_in = models.IntegerField(default=3600)  # sekundlarda

    def is_expired(self):
        return (datetime.now() - self.created).total_seconds() > self.expires_in
    
    def __str__(self):
        return f"{self.user.username} - {self.app.name}"
    
