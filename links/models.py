from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Link(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='links', null=True, blank=True)
    short_code = models.CharField(max_length=50, unique=True, db_index=True)
    original_url = models.TextField()
    title = models.CharField(max_length=500, blank=True, null=True)
    click_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    password = models.CharField(max_length=128, blank=True, null=True)

    def __str__(self):
        return f'{self.short_code} -> {self.original_url}'
