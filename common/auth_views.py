from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from rest_framework.permissions import AllowAny
from django.core.cache import cache
from common.authentication import CsrfExemptSessionAuthentication
import uuid, random, string, io, base64
from PIL import Image, ImageDraw, ImageFont


CAPTCHA_CACHE_PREFIX = 'captcha:'
CAPTCHA_EXPIRE_SECONDS = 300  # 5 分钟


def _gen_captcha_code(length=4):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def _gen_captcha_image(code: str) -> str:
    """生成简单图片验证码，返回 base64 data url"""
    width, height = 100, 36
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 尝试加载系统字体，失败则用默认字体
    try:
        font = ImageFont.truetype('arial.ttf', 24)
    except Exception:
        font = ImageFont.load_default()

    # 计算文字尺寸（兼容不同 Pillow 版本）
    try:
        # 优先使用 textbbox（新版本 Pillow 推荐）
        bbox = draw.textbbox((0, 0), code, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except Exception:
        # 回退到 font.getsize（旧接口）
        try:
            text_w, text_h = font.getsize(code)
        except Exception:
            text_w, text_h = 40, 20  # 保底值，避免报错

    # 居中绘制
    x = (width - text_w) / 2
    y = (height - text_h) / 2
    draw.text((x, y), code, font=font, fill=(0, 0, 0))

    # 简单干扰线
    for _ in range(3):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line(((x1, y1), (x2, y2)), fill=(150, 150, 150), width=1)

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f'data:image/png;base64,{b64}'


def verify_captcha(captcha_id: str, user_code: str) -> bool:
    """从缓存校验验证码，成功后删除，失败不告知具体原因。"""
    if not captcha_id or not user_code:
        return False
    key = f"{CAPTCHA_CACHE_PREFIX}{captcha_id}"
    real_code = cache.get(key)
    if not real_code:
        return False
    # 大小写不敏感
    if real_code.upper() != str(user_code).upper():
        return False
    # 校验通过后删除，避免重放
    cache.delete(key)
    return True


class CaptchaView(APIView):
    """获取图片验证码：GET /api/auth/captcha
    返回 { captcha_id, image }
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        code = _gen_captcha_code()
        captcha_id = uuid.uuid4().hex
        key = f"{CAPTCHA_CACHE_PREFIX}{captcha_id}"
        cache.set(key, code, timeout=CAPTCHA_EXPIRE_SECONDS)
        img_b64 = _gen_captcha_image(code)
        return Response({
            'captcha_id': captcha_id,
            'image': img_b64,
            'expire_seconds': CAPTCHA_EXPIRE_SECONDS,
        })


class MeView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        if request.user and request.user.is_authenticated:
            return Response({
                'authenticated': True,
                'username': request.user.username,
                'is_staff': request.user.is_staff,
                'is_superuser': request.user.is_superuser,
            })
        return Response({'authenticated': False})


class RegisterView(APIView):
    """用户注册：用户名唯一，邮箱可选但如提供则也需唯一。"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        email = (request.data.get('email') or '').strip()
        password = (request.data.get('password') or '').strip()
        captcha_id = (request.data.get('captcha_id') or '').strip()
        captcha = (request.data.get('captcha') or '').strip()

        if not verify_captcha(captcha_id, captcha):
            return Response({'error': '验证码错误或已过期'}, status=status.HTTP_400_BAD_REQUEST)

        if not username or not password:
            return Response({'error': '用户名和密码不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({'error': '用户名已存在'}, status=status.HTTP_400_BAD_REQUEST)

        if email and User.objects.filter(email=email).exists():
            return Response({'error': '该邮箱已被使用'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, email=email or None, password=password)

        # 自动登录
        login(request, user)
        return Response({'success': True, 'username': user.username})


class LoginView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        password = (request.data.get('password') or '').strip()
        captcha_id = (request.data.get('captcha_id') or '').strip()
        captcha = (request.data.get('captcha') or '').strip()

        if not verify_captcha(captcha_id, captcha):
            return Response({'error': '验证码错误或已过期'}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({'error': '用户名或密码错误'}, status=status.HTTP_401_UNAUTHORIZED)
        login(request, user)
        return Response({'success': True, 'username': user.username})


class LogoutView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response({'success': True})
