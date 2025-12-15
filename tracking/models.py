from django.db import models

class Click(models.Model):
    link = models.ForeignKey('links.Link', related_name='clicks', on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    referer = models.TextField(blank=True, null=True)
    clicked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['clicked_at'], name='idx_tracking_click_clicked_at'),
        ]

    def __str__(self):
        return f'Click on {self.link.short_code} at {self.clicked_at}'
