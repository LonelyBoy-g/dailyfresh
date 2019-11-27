# from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django_redis import get_redis_connection
from django.core.paginator import Paginator

from celery_tasks.tasks import send_register_active_mail
from utils.mixin import LoginRequiredMixin
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from user.models import User, Address
from goods.models import GoodsSKU
from order.models import OrderGoods, OrderInfo
import re


# user/register
class RegisterView(View):
    """注册"""

    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        # 接收收据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 数据校验
        if not all([username, password, email]):
            render(request, 'register.html', {'errmsg': '数据填写不完整'})

        if not re.match("^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$", email):
            render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            render(request, 'register.html', {'errmsg': '请同意协议'})

        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            user = None
        # 用户名已存在
        if user:
            return render(request, 'register.html', {'errmsg': '用户名已存在'})

        # 业务处理
        user = User.objects.create_user(username, email, password)
        user.is_active = 0  # 默认不激活
        user.save()

        # 发送激活邮件，包含激活链接：http://127.0.0.1:8000/user/active/user.id
        # 加密用户的身份信息，生成激活token
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode()

        # 发邮件异步celery
        send_register_active_mail.delay(email, username, token)

        # subject = '天天生鲜欢迎信息'
        # message = ''
        # sender = settings.EMAIL_FROM
        # receiver = [email]
        # html_message = '<h1>%s,欢迎你成为注册会员</h1>请点击下列链接激活账户<br/>' \
        #                '<a href="http://127.0.0.1:8000/user/active/%s">' \
        #                'http://127.0.0.1:8000/user/active/%s</a>' % (username, token, token)
        # send_mail(subject, message, sender, receiver, html_message=html_message)
        # time.sleep(5)

        # 返回应答
        return redirect(reverse('goods:index'))


# /user/active/(token)
class ActiveView(View):
    """用户激活"""

    def get(self, request, token):
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            # 获取身份激活
            user_id = info['confirm']
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            # 应答,跳转登录界面
            return redirect(reverse('user:login'))

        except SignatureExpired as e:
            return HttpResponse('激活链接过期')


# user/login
class LoginView(View):
    """用户登录"""

    def get(self, request):
        """登录显示"""
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
        else:
            username = ''
        return render(request, 'login.html', {'username': username})

    def post(self, request):
        # 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        # 数据校验
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '数据不完整'})

        # 业务处理：登录校验
        user = authenticate(username=username, password=password)
        if user is not None:
            # the password verified for the user
            if user.is_active:
                print('激活成功')
                login(request, user)

                next_url = request.GET.get('next', 'goods:index')
                response = redirect(reverse(next_url))

                # 记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    response.set_cookie('username', username, max_age=7 * 24 * 6000)
                else:
                    response.delete_cookie('username')
                return response

            else:
                return render(request, 'login.html', {'errmsg': '用户未激活'})
        else:
            # the authentication system was unable to verify the username and password
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})

        # 返回应答


class LogoutView(View):
    def get(self, request):
        # 清除用户的session信息
        logout(request)
        # Redirect to a success page.
        return redirect(reverse('goods:index'))


# user/
class UserInfoView(LoginRequiredMixin, View):
    """用户中心——信息"""

    def get(self, request):
        # request.user.is_authenticated
        # 如果用户登录返回user实例，否返回AnonymousUser

        # 获取用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user)

        # 获取用户的历史记录
        # from redis import  StrictRedis
        # StrictRedis(host='127.0.0.1', port='6379', db=9)
        con = get_redis_connection('default')
        history_id = 'history_%d' % user.id

        # 获取用户最新浏览的5条商品记录
        sku_ids = con.lrange(history_id, 0, 4)

        goods_list = []
        for i in sku_ids:
            goods = GoodsSKU.objects.get(id=i)
            goods_list.append(goods)

        content = {
            'page': 'user',
            'address': address,
            'user': user,
            'goods_list': goods_list,
        }
        return render(request, 'user_center_info.html', content)


# user/order
class UserOrderView(LoginRequiredMixin, View):
    """用户中心——订单页"""

    def get(self, request, page):
        '''显示订单页面'''
        # 获取登录对象
        user = request.user

        # 获取用户的订单信息
        orders = OrderInfo.objects.filter(user=user)

        # 遍历获取订单的商品信息
        for order in orders:
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)

            # 计算小计
            for order_sku in order_skus:
                amount = order_sku.price * order_sku.count

                # 动态加属性
                order_sku.amount = amount

            # 动态加属性
            order.order_skus = order_skus
            order.status_name = OrderInfo.ORDER_STATUS[str(order.order_status)]

        # 分页
        paginator = Paginator(orders, 1)

        # 获取第page页的对象s
        try:
            page = int(page)
        except Exception as e:
            page = 1
        order_page = paginator.page(page)

        # 进行页码控制， 页面上最多显示5个页面
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 组织上下文
        context = {
            'order_page': order_page,
            'pages': pages,
            'page': 'order',
        }

        return render(request, 'user_center_order.html', context)


# user/address
class AddressView(LoginRequiredMixin, View):
    """用户中心——地址"""

    def get(self, request):
        # 用户登录成功返回request.user对象
        user = request.user
        # try:
        #     Address.objects.get(user=user, is_default =True)
        # except Address.DoesNotExist:
        #     address = None
        address = Address.objects.get_default_address(user)
        return render(request, 'user_center_site.html', {'page': 'address', 'address': address, 'user': user})

    def post(self, request):
        # 接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        # 校验数据
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'errmsg': '数据不完整'})

        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg': '手机格式不正确'})

        # 业务处理：地址添加
        user = request.user
        address = Address.objects.get_default_address(user)

        if address:
            is_default = False
        else:
            is_default = True

        Address.objects.create(user=user, receiver=receiver, addr=addr, phone=phone,
                               zip_code=zip_code, is_default=is_default)

        # 返回应答
        return redirect(reverse('user:address'))
