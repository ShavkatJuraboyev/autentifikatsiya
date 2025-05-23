from django.urls import path
from .views import UserInfoAPI
urlpatterns = [
    path('userinfo/', UserInfoAPI.as_view(), name='user_info'),
]
