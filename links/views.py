from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from urllib.parse import urlparse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
import string, random

from links.models import Link
from links.serializers import LinkSerializer


def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choice(chars) for _ in range(length))
        if not Link.objects.filter(short_code=code).exists():
            return code


from common.authentication import CsrfExemptSessionAuthentication

class LinkViewSet(viewsets.ModelViewSet):
    queryset = Link.objects.all().order_by('-created_at')
    serializer_class = LinkSerializer
    lookup_field = 'short_code'

    def destroy(self, request, *args, **kwargs):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return Response({'error': 'Forbidden: please login to delete'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        if not data.get('short_code'):
            data['short_code'] = generate_short_code()
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['get'], url_path='codes')
    def codes(self, request):
        """轻量短码/标题搜索，用于前端自动补全。
        GET /api/links/codes/?q=keyword
        返回: [{label, value}] 最多20条
        """
        q = request.query_params.get('q', '').strip()
        qs = self.get_queryset()
        if q:
            qs = qs.filter(Q(short_code__icontains=q) | Q(title__icontains=q))
        qs = qs.values('short_code', 'title', 'original_url').order_by('-created_at')[:20]
        items = []
        for r in qs:
            title = r['title'] or r['short_code']
            original_url = r['original_url']
            try:
                host = urlparse(original_url).hostname or ''
            except Exception:
                host = ''
            # 标签中尽量包含平台名(标题) + 主机 + 短码，便于区分同名标题
            label = f"{title} · {host} · {r['short_code']}" if host else f"{title} · {r['short_code']}"
            items.append({
                'label': label,
                'value': r['short_code'],
                'host': host,
                'original_url': original_url,
                'title': title,
            })
        return Response({'options': items})

    @action(detail=False, methods=['post'], url_path='batch')
    def batch_create(self, request):
        """批量创建同一原始链接的多平台短链
        POST /api/links/batch/
        body: {
          original_url: str,
          titles: [str] 或 字符串(按行分隔),
          password?: str,
          expires_at?: ISO8601
        }
        返回: { items: [{short_code, short_url, title}] }
        """
        BASE_URL = request.build_absolute_uri('/').rstrip('/')
        data = request.data or {}
        original_url = (data.get('original_url') or '').strip()
        titles = data.get('titles')
        password = data.get('password') or None
        expires_at_raw = data.get('expires_at')

        # 校验原始URL
        if not original_url or not (original_url.startswith('http://') or original_url.startswith('https://')):
            return Response({'error': 'original_url 必须以 http/https 开头'}, status=400)

        # 解析标题列表
        if isinstance(titles, str):
            titles = [t.strip() for t in titles.split('\n') if t.strip()]
        if not isinstance(titles, list) or not titles:
            return Response({'error': 'titles 不能为空（支持数组或\n分行字符串）'}, status=400)
        if len(titles) > 100:
            return Response({'error': '一次最多创建 100 条'}, status=400)

        # 解析过期时间
        expires_at = None
        if expires_at_raw:
            try:
                expires_at = parse_datetime(expires_at_raw)
                if expires_at and timezone.is_naive(expires_at):
                    expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
            except Exception:
                return Response({'error': 'expires_at 格式无效，需 ISO8601'}, status=400)

        items = []
        for title in titles:
            code = generate_short_code()
            link = Link.objects.create(
                short_code=code,
                original_url=original_url,
                title=title,
                password=password,
                expires_at=expires_at,
            )
            items.append({
                'short_code': link.short_code,
                'title': link.title,
                'short_url': f"{BASE_URL}/{link.short_code}",
            })

        return Response({'success': True, 'count': len(items), 'items': items}, status=201)
