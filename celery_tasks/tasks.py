
import os
# # 任务处理者加载项模板
# import django
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dailyfresh.settings")
# django.setup()

import time
from django_redis import get_redis_connection
from django.conf import settings
from django.core.mail import send_mail
from django.template import loader

from celery import Celery
from goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
app = Celery('celery_tasks.tasks', broker='redis://127.0.0.1:6379/8')


@app.task
def send_register_active_mail(to_mail, username, token):
    """发送激活邮件"""
    subject = '欢迎信息'
    message = ''
    sender = settings.EMAIL_FROM
    receiver = [to_mail]
    html_message = '<h1>%s,欢迎你成为注册会员</h1>请点击下列链接激活账户<br/>' \
                   '<a href="http://127.0.0.1:8000/user/active/%s">' \
                   'http://127.0.0.1:8000/user/active/%s</a>' % (username, token, token)
    send_mail(subject, message, sender, receiver, html_message=html_message)
    time.sleep(5)



def generate_static_index_html():
    """产生首页静态界面"""
    types = GoodsType.objects.all()

    # 获取首页轮播商品信息
    goods_banners = IndexGoodsBanner.objects.all().order_by('index')

    # 获取首页促销商品信息
    promotion_banners = IndexPromotionBanner.objects.all().order_by('index')

    # 获取分类商品展示信息
    for type in types:
        image_goods_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1)
        font_goods_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0)
        type.image_goods_banners = image_goods_banners
        type.font_goods_banners = font_goods_banners

    # 组织上下文
    context = {
        'types': types,
        'goods_banners': goods_banners,
        'promotion_goods': promotion_banners,
    }

    # s使用模板
    # 1. 加载模板文件，返回模板对象
    temp = loader.get_template('index.html')
    # 2. 渲染模板
    static_index_html = temp.render(context)

    # 生成对应静态文件
    save_path = os.path.join(settings.BASE_DIR, 'static/index.html')
    with open(save_path, 'w') as f:
        f.write(static_index_html)

