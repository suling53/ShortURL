from django.urls import path
from .views import AnalyticsView

urlpatterns = [
    path('analytics/<str:short_code>/', AnalyticsView.as_view(), name='analytics'),
]

