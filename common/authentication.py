from rest_framework.authentication import SessionAuthentication, BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
import os

class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return

class APITokenAuthentication(BaseAuthentication):
    """简单的头部令牌认证：仅当设置了 API_TOKEN 时生效。
    未设置 API_TOKEN 时返回 None（不参与），避免影响会话登录。
    """
    def authenticate(self, request):
        api_token = os.getenv('API_TOKEN')
        if not api_token:
            return None
        auth_header = request.headers.get('Authorization')
        if not auth_header or auth_header != api_token:
            raise AuthenticationFailed('Invalid or missing API Token')
        return (None, None)
