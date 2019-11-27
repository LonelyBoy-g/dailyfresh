from django.conf.urls import url
from apps.goods.views import IndexView, ListView, DetailView

urlpatterns = [

    url(r'^$', IndexView.as_view(), name='index'),  # 首页
    url('^goods/(?P<goods_id>\d+)$', DetailView.as_view(), name='detail'),  # 详情页
    url('^goods/list/(?P<type_id>\d+)/(?P<page>\d+)$', ListView.as_view(), name='list'),  # 列表页
]
