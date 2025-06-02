from django.urls import path
from .views import UserInfoAPI, AuthorizeEndpoint, TokenEndpoint

urlpatterns = [
    path('userinfo/', UserInfoAPI.as_view(), name='user_info'),
    path('authorize/', AuthorizeEndpoint.as_view(), name='authorize'),
    path('token/', TokenEndpoint.as_view(), name='token'),
]
