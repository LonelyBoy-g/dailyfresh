from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client
from django.conf import settings


class FDFSStorage(Storage):
    """fast DFS文件存储类"""

    def __init__(self, client_conf=None, base_url=None):
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf

        if base_url is None:
            base_url = settings.FDFS_URL
        self.base_url = base_url

    def open(self, name, mode='rb'):
        pass

    def save(self, name, content, max_length=None):
        client = Fdfs_client('.utils/fastDFS/client.conf')

        res = client.upload_by_filename('test')

        if res.get('Status') != 'Upload successed':
            raise Exception('上传文件到fast DFS失败')
        filename = res.get('Remote file_id')
        return filename

    def exists(self, name):
        return False

    def url(self, name):
        return 'http://10.128.106.240:9999' + name
