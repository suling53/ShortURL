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
from common.authentication import CsrfExemptSessionAuthentication


def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choice(chars) for _ in range(length))
        if not Link.objects.filter(short_code=code).exists():
            return code


def normalize_url(raw: str) -> str:
    """允许用户输入简化地址：
    - 如果以 http/https 开头，直接返回
    - 否则自动补全为 https://raw
    并做一次 urlparse 校验，非法则抛异常
    """
    raw = (raw or '').strip()
    if not raw:
        raise ValueError('original_url 不能为空')
    if not (raw.startswith('http://') or raw.startswith('https://')):
        raw = 'https://' + raw
    # 简单合法性检查
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError('original_url 非法，请检查格式')
    return raw


class LinkViewSet(viewsets.ModelViewSet):
    queryset = Link.objects.all().order_by('-created_at')
    serializer_class = LinkSerializer
    lookup_field = 'short_code'

    authentication_classes = [CsrfExemptSessionAuthentication]

    def get_queryset(self):
        """普通用户只能看到自己的链接；超级用户可以看到全部；未登录用户返回空集。"""
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated:
            return Link.objects.none()

        if user.is_superuser:
            # 超级用户：查看全部链接（包括没有 owner 的旧数据）
            return Link.objects.all().order_by('-created_at')

        # 普通用户：只能看到自己的
        return Link.objects.filter(owner=user).order_by('-created_at')

    def perform_create(self, serializer):
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated:
            raise PermissionError('请先登录再创建短链接')
        serializer.save(owner=user)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        # 规范化 original_url：允许简写，自动补全 https:// 并做合法性校验
        try:
            data['original_url'] = normalize_url(data.get('original_url') or '')
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if not data.get('short_code'):
            data['short_code'] = generate_short_code()
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except PermissionError as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['get'], url_path='codes')
    def codes(self, request):
        """轻量短码/标题搜索：普通用户只搜自己的，超级用户搜全部。"""
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
        """批量创建同一原始链接的多平台短链，仅作用于当前登录用户（包括超级用户）。"""
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated:
            return Response({'error': '请先登录'}, status=status.HTTP_403_FORBIDDEN)

        BASE_URL = request.build_absolute_uri('/').rstrip('/')
        data = request.data or {}
        raw_original_url = (data.get('original_url') or '').strip()
        titles = data.get('titles')
        password = data.get('password') or None
        expires_at_raw = data.get('expires_at')

        try:
            original_url = normalize_url(raw_original_url)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)

        if isinstance(titles, str):
            titles = [t.strip() for t in titles.split('\n') if t.strip()]
        if not isinstance(titles, list) or not titles:
            return Response({'error': 'titles 不能为空（支持数组或\n分行字符串）'}, status=400)
        if len(titles) > 100:
            return Response({'error': '一次最多创建 100 条'}, status=400)

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
                owner=user,
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
