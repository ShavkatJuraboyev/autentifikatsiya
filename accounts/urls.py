from django.urls import path
from .views import register_face, register_voice, login_with_face, login_with_voice

urlpatterns = [
    path("register_face/", register_face, name="register_face"),
    path("register_voice/", register_voice, name="register_voice"),
    path("login_face/", login_with_face, name="login_face"),
    path("login_voice/", login_with_voice, name="login_voice"),
]
