from rest_framework import serializers
from links.models import Link
from common.utils import generate_qr_code_base64

class LinkSerializer(serializers.ModelSerializer):
    short_url = serializers.SerializerMethodField()
    qr_code = serializers.SerializerMethodField()
    has_password = serializers.SerializerMethodField()

    class Meta:
        model = Link
        fields = [
            'short_code',
            'original_url',
            'title',
            'click_count',
            'created_at',
            'expires_at',
            'password',
            'short_url',
            'qr_code',
            'has_password',
        ]
        read_only_fields = ['click_count', 'created_at', 'short_url']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def get_short_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/{obj.short_code}')
        return f'/{obj.short_code}'

    def get_qr_code(self, obj):
        short_url = self.get_short_url(obj)
        return generate_qr_code_base64(short_url)

    def get_has_password(self, obj):
        return bool(obj.password)

