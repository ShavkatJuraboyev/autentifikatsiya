from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, Group, Permission
from django.db import models

class CustomUser(AbstractBaseUser, PermissionsMixin):
    face_encoding = models.TextField(blank=True, null=True)  # Yuz uchun ma'lumot
    voice_sample = models.FileField(upload_to="voices/", blank=True, null=True)  # Ovoz fayli
    groups = models.ManyToManyField(
        Group,
        related_name="customuser_groups",  # Nomzodni to‘g‘rilash uchun
        blank=True
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="customuser_permissions",  # Nomzodni to‘g‘rilash uchun
        blank=True
    )