from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from links.models import Link
from tracking.models import Click

@method_decorator(csrf_exempt, name='dispatch')
class RedirectView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, short_code, format=None):
        link = get_object_or_404(Link, short_code=short_code)
        # 过期检查
        if link.expires_at and link.expires_at < timezone.now():
            return Response({"error": "This short link has expired"}, status=status.HTTP_410_GONE)
        # 密码检查
        if link.password:
            accept = request.META.get('HTTP_ACCEPT', '') or ''
            wants_html = 'text/html' in accept or '*/*' in accept
            if wants_html:
                return self._password_html(short_code, error=None, status_code=200)
            return Response({"error": "Password required"}, status=status.HTTP_401_UNAUTHORIZED)
        # 记录点击并重定向
        self._record_click(request, link)
        return redirect(link.original_url)

    def post(self, request, short_code, format=None):
        link = get_object_or_404(Link, short_code=short_code)
        if link.expires_at and link.expires_at < timezone.now():
            return Response({"error": "This short link has expired"}, status=status.HTTP_410_GONE)
        if not link.password:
            return Response({"error": "This link is not password protected"}, status=status.HTTP_400_BAD_REQUEST)

        accept = request.META.get('HTTP_ACCEPT', '') or ''
        ctype = request.META.get('CONTENT_TYPE', '') or ''
        wants_html = 'text/html' in accept or ctype.startswith('application/x-www-form-urlencoded') or ctype.startswith('multipart/form-data')

        # 兼容从 JSON、表单、原始体读取密码
        pwd = request.data.get('password') if hasattr(request, 'data') else None
        if pwd is None:
            try:
                pwd = request.POST.get('password')
            except Exception:
                pwd = None
        if pwd is None:
            try:
                from urllib.parse import parse_qs
                body = (request.body or b'').decode('utf-8', errors='ignore')
                if body:
                    qs = parse_qs(body)
                    pwd = (qs.get('password', [None])[0])
            except Exception:
                pwd = None
        input_pwd = (pwd or '').strip()
        stored_pwd = (link.password or '').strip()

        if input_pwd != stored_pwd:
            if wants_html:
                return self._password_html(short_code, error='密码错误，请重试', status_code=401)
            return Response({"error": "Invalid password"}, status=status.HTTP_401_UNAUTHORIZED)

        # 验证通过，记录点击
        self._record_click(request, link)
        if wants_html:
            # 表单提交走 302 跳转
            return redirect(link.original_url)
        # API 调用走 JSON 返回
        return Response({"original_url": link.original_url}, status=status.HTTP_200_OK)

    def _password_html(self, short_code, error=None, status_code=200):
        err_html = f"<p style='color:#ef4444;margin:8px 0'>{error}</p>" if error else ""
        html = f"""
<!DOCTYPE html>
<html lang='zh-CN'>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>输入访问密码</title>
  <style>
    body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#f7f7fb;}}
    .wrap{{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:16px;}}
    .card{{width:100%;max-width:420px;background:#fff;border:1px solid #e5e7eb;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.06);padding:20px;}}
    h1{{font-size:18px;margin:0 0 8px;}}
    p.tip{{margin:0 0 12px;color:#6b7280;font-size:14px;}}
    input[type=password]{{width:100%;padding:10px 12px;border:1px solid #e5e7eb;border-radius:8px;font-size:14px;}}
    .row{{display:flex;gap:8px;margin-top:12px;}}
    button{{flex:1;padding:10px 12px;border:1px solid #e5e7eb;border-radius:8px;background:#0ea5e9;color:#fff;cursor:pointer;font-size:14px;}}
    .sec{{background:#fff;color:#111827;}}
    .err{{color:#ef4444;}}
    .mute{{color:#6b7280;font-size:12px;margin-top:8px}}
  </style>
</head>
<body>
  <div class='wrap'>
    <div class='card'>
      <h1>该短链已加密</h1>
      <p class='tip'>请输入访问密码以继续</p>
      {err_html}
      <form method='post' action='/{short_code}/'>
        <input type='password' name='password' placeholder='输入访问密码' autofocus />
        <div class='row'>
          <button type='submit'>确认并跳转</button>
          <button type='button' class='sec' onclick='history.back()'>返回</button>
        </div>
      </form>
      <p class='mute'>安全提示：请勿在不受信任的页面输入密码</p>
    </div>
  </div>
</body>
</html>
        """
        return HttpResponse(html, status=status_code, content_type='text/html; charset=utf-8')

    def _record_click(self, request, link):
        ip_address = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        referer = request.META.get('HTTP_REFERER', '')
        Click.objects.create(link=link, ip_address=ip_address, user_agent=user_agent, referer=referer)
        link.click_count += 1
        link.save()
