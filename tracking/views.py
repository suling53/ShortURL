from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta, datetime
from django.utils.dateparse import parse_datetime
from django.db.models import Count
from django.db.models.functions import TruncHour, TruncDate

from links.models import Link
from tracking.models import Click

class AnalyticsView(APIView):
    """
    GET /api/analytics/<short_code>/?range=24h|7d|30d|custom&start=ISO&end=ISO
    返回：
    - hourly: [{hour: 'YYYY-MM-DD HH:00', clicks}]
    - daily:  [{date: 'YYYY-MM-DD', clicks}]
    - referer_top: [{name, clicks}]  (前10)
    - ua_top: [{name, clicks}]       (前10)
    """
    def get(self, request, short_code):
        # 校验短码存在
        try:
            link = Link.objects.get(short_code=short_code)
        except Link.DoesNotExist:
            return Response({"error": "Short link not found"}, status=status.HTTP_404_NOT_FOUND)

        rng = (request.query_params.get('range') or '24h').lower()
        start_q = request.query_params.get('start')
        end_q = request.query_params.get('end')

        now = timezone.now()
        if rng == '24h':
            start_dt = now - timedelta(hours=24)
            end_dt = now
        elif rng == '7d':
            start_dt = now - timedelta(days=7)
            end_dt = now
        elif rng == '30d':
            start_dt = now - timedelta(days=30)
            end_dt = now
        elif rng == 'custom' and start_q and end_q:
            start_dt = parse_datetime(start_q) or datetime.fromisoformat(start_q)
            end_dt = parse_datetime(end_q) or datetime.fromisoformat(end_q)
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
            if timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt, timezone.get_current_timezone())
        else:
            # 默认24h
            start_dt = now - timedelta(hours=24)
            end_dt = now
            rng = '24h'

        # 归一化：保证 start < end
        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(minutes=1)

        base_qs = Click.objects.filter(link=link, clicked_at__gte=start_dt, clicked_at__lte=end_dt)

        # 小于等于2天提供按小时序列；否则提供按天
        if (end_dt - start_dt) <= timedelta(days=2):
            qs_hour = (base_qs
                       .annotate(hour=TruncHour('clicked_at'))
                       .values('hour')
                       .annotate(clicks=Count('id'))
                       .order_by('hour'))
            hourly = [{
                'hour': h['hour'].strftime('%Y-%m-%d %H:00') if h['hour'] else '',
                'clicks': h['clicks']
            } for h in qs_hour]
        else:
            hourly = []

        qs_day = (base_qs
                  .annotate(day=TruncDate('clicked_at'))
                  .values('day')
                  .annotate(clicks=Count('id'))
                  .order_by('day'))
        daily = [{
            'date': d['day'].strftime('%Y-%m-%d') if d['day'] else '',
            'clicks': d['clicks']
        } for d in qs_day]

        # 来源 Referer Top10
        ref_qs = (base_qs
                  .values('referer')
                  .annotate(clicks=Count('id'))
                  .order_by('-clicks')[:10])
        referer_top = [{
            'name': (r['referer'] or '(direct)')[:120],
            'clicks': r['clicks']
        } for r in ref_qs]

        # UA Top10
        ua_qs = (base_qs
                 .values('user_agent')
                 .annotate(clicks=Count('id'))
                 .order_by('-clicks')[:10])
        ua_top = [{
            'name': (u['user_agent'] or '(unknown)')[:120],
            'clicks': u['clicks']
        } for u in ua_qs]

        # 同一原始URL下，不同短链的点击排名
        siblings_qs = (Click.objects
                       .filter(link__original_url=link.original_url,
                               clicked_at__gte=start_dt,
                               clicked_at__lte=end_dt)
                       .values('link__short_code', 'link__title')
                       .annotate(clicks=Count('id'))
                       .order_by('-clicks'))
        siblings_top = [{
            'short_code': s['link__short_code'],
            'title': s['link__title'] or s['link__short_code'],
            'clicks': s['clicks']
        } for s in siblings_qs]

        return Response({
            'success': True,
            'short_code': short_code,
            'original_url': link.original_url,
            'range': rng,
            'start': start_dt.isoformat(),
            'end': end_dt.isoformat(),
            'hourly': hourly,
            'daily': daily,
            'siblings_top': siblings_top,
            'referer_top': referer_top,
        })
