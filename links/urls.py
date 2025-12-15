from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import LinkViewSet

router = DefaultRouter()
router.register(r'links', LinkViewSet, basename='links')

urlpatterns = [
    path('', include(router.urls)),
]

