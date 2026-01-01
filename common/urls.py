from django.urls import path
from .auth_views import LoginView, LogoutView, MeView, RegisterView, CaptchaView

urlpatterns = [
    path('captcha', CaptchaView.as_view(), name='captcha'),
    path('register', RegisterView.as_view(), name='register'),
    path('login', LoginView.as_view(), name='login'),
    path('logout', LogoutView.as_view(), name='logout'),
    path('me', MeView.as_view(), name='me'),
]