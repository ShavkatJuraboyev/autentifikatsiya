from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='login'),
    path('logout/', views.logout_view, name='logout_view'),
    path('register/', views.register, name='register'),
    path('face-register/', views.face_register, name='face_register'),
    path('face-login/', views.face_login, name='face_login'),
    path('profile/', views.profile_view, name='profile'),

    # Face login va callback
    path('face-auth-start/', views.face_auth_start, name='face_auth_start'),
    path('face-login-api/', views.face_login_callback, name='face_login_callback'),

    # Dasturchilar uchun integratsiya arizasi
    path('submit-application/', views.submit_application, name='submit_application'),

    path('application-list/', views.application_list, name='application_list'),

    # Admin arizani tasdiqlash (faqat admin)
    path('approve-application/<int:app_id>/', views.approve_application, name='approve_application'),

    path('my-applications/', views.user_applications, name='user_applications'),

]
