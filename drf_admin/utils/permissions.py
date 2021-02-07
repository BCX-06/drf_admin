""" 
@author   : Wang Meng
@github   : https://github.com/tianpangji 
@software : PyCharm 
@file     : permissions.py 
@create   : 2020/6/28 21:52 
"""
import re

from django.conf import settings
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission

from system.models import Permissions


class UserLock(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = '用户已被锁定,请联系管理员'
    default_code = 'not_authenticated'


class RbacPermission(BasePermission):
    """
    自定义权限认证
    """

    @staticmethod
    def pro_uri(uri):
        base_api = settings.BASE_API
        uri = '/' + base_api + '/' + uri + '/'
        return re.sub('/+', '/', uri)

    def has_permission(self, request, view):
        request_url = request.path
        # 如果请求url在白名单，放行
        for safe_url in settings.WHITE_LIST:
            if re.match(settings.REGEX_URL.format(url=safe_url), request_url):
                return True
        # 验证用户登录状态
        if not request.user.is_authenticated:
            return False
        # 验证用户是否被锁定
        if not request.user.is_active:
            raise UserLock()
        # admin账户放行
        if 'admin' in request.user.roles.values_list('name', flat=True):
            return True
        # RBAC权限验证
        request_method = request.method
        permission_urls = Permissions.objects.filter(method=request_method).values('path').distinct()
        flag = False
        flag_url = ''
        for values in permission_urls:
            if re.match(settings.REGEX_URL.format(url=self.pro_uri(values.get('path'))), request_url):
                flag = True
                flag_url = values.get('path')
                break
        if flag:
            permissions = Permissions.objects.filter(path=flag_url, method=request_method)
            # Redis验证权限
            conn = get_redis_connection('user_info')
            user_permissions = conn.hget('user_info_%s' % request.user.id, 'permissions')
            if user_permissions and permissions:
                for permission in permissions:
                    if permission.sign in user_permissions.decode().split(','):  # redis存储为bytes类型
                        return True
            return False
        else:
            return True
