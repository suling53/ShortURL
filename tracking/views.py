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
            start_dt = now - timedelta(hours=24)
            end_dt = now
            rng = '24h'

        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(minutes=1)

        tz = timezone.get_current_timezone()
        tz_utc = timezone.utc

        base_qs = Click.objects.filter(link=link, clicked_at__gte=start_dt, clicked_at__lte=end_dt)

        # 1. 当前短码：按小时（保持 UTC 聚合，Python 侧转本地 ISO 字符串）
        qs_hour = (
            base_qs
            .annotate(hour=TruncHour('clicked_at', tzinfo=tz_utc))
            .values('hour')
            .annotate(clicks=Count('id'))
            .order_by('hour')
        )
        hourly = [{
            'hour': timezone.localtime(h['hour'], tz).isoformat() if h['hour'] else '',
            'clicks': h['clicks']
        } for h in qs_hour] if (end_dt - start_dt) <= timedelta(days=2) else []

        # 2. 当前短码：按天（【关键修改】从小时数据汇总到本地日期，解决只显示一天的问题）
        daily_dict = {}
        for h in qs_hour:
            if h['hour']:
                # 将 UTC 的小时转为本地时间，再取日期
                local_date = timezone.localtime(h['hour'], tz).date()
                date_str = local_date.strftime('%Y-%m-%d')
                daily_dict[date_str] = daily_dict.get(date_str, 0) + h['clicks']
        
        daily = [{'date': d, 'clicks': c} for d, c in sorted(daily_dict.items())]

        # 3. 来源 Referer & UA Top10
        ref_qs = base_qs.values('referer').annotate(clicks=Count('id')).order_by('-clicks')[:10]
        referer_top = [{'name': (r['referer'] or '(direct)')[:120], 'clicks': r['clicks']} for r in ref_qs]

        ua_qs = base_qs.values('user_agent').annotate(clicks=Count('id')).order_by('-clicks')[:10]
        ua_top = [{'name': (u['user_agent'] or '(unknown)')[:120], 'clicks': u['clicks']} for u in ua_qs]

        # 4. 同一原始URL下的 Siblings 统计
        siblings_base = Click.objects.filter(
            link__original_url=link.original_url,
            clicked_at__gte=start_dt,
            clicked_at__lte=end_dt,
        )

        siblings_qs = siblings_base.values('link__short_code', 'link__title').annotate(clicks=Count('id')).order_by('-clicks')
        siblings_top = [{
            'short_code': s['link__short_code'],
            'title': s['link__title'] or s['link__short_code'],
            'clicks': s['clicks'],
        } for s in siblings_qs]

        # 5. 统一按小时拉取再分发，规避时区表报错
        siblings_h_qs = (
            siblings_base
            .annotate(h_utc=TruncHour('clicked_at', tzinfo=tz_utc))
            .values('h_utc', 'link__short_code', 'link__title')
            .annotate(clicks=Count('id'))
            .order_by('h_utc')
        )

        siblings_hourly = []
        s_daily_dict = {}

        for r in siblings_h_qs:
            if r['h_utc']:
                local_dt = timezone.localtime(r['h_utc'], tz)
                date_str = local_dt.strftime('%Y-%m-%d')
                
                # 填充 hourly 列表
                siblings_hourly.append({
                    'date': date_str,
                    'hour': local_dt.hour,
                    'short_code': r['link__short_code'],
                    'title': r['link__title'] or r['link__short_code'],
                    'clicks': r['clicks'],
                })

                # 累加到 daily 字典
                key = (date_str, r['link__short_code'], r['link__title'])
                s_daily_dict[key] = s_daily_dict.get(key, 0) + r['clicks']

        siblings_daily = [{
            'date': k[0],
            'short_code': k[1],
            'title': k[2] or k[1],
            'clicks': v
        } for k, v in sorted(s_daily_dict.items())]

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
            'siblings_daily': siblings_daily,
            'siblings_hourly': siblings_hourly,
            'referer_top': referer_top,
            'ua_top': ua_top,
        })