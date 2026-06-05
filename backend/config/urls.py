from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView


def backend_not_found_view(request):
    return render(request, '404.html', status=404)


class ApiV1RootView(APIView):
    """API v1 根视图，列出所有主要接口端点（Browsable API 格式）"""

    def get(self, request, format=None):
        base_url = request.build_absolute_uri('/api/v1/').rstrip('/')
        return Response({
            'message': '数字人管理平台 API v1',
            'documentation': {
                'swagger': f'{base_url.replace("/api/v1", "")}/api/docs/',
                'redoc': f'{base_url.replace("/api/v1", "")}/api/redoc/',
            },
            'endpoints': {
                'auth': {
                    'login': f'{base_url}/auth/login/',
                    'refresh': f'{base_url}/auth/refresh/',
                    'me': f'{base_url}/auth/me/',
                    'account_applications': f'{base_url}/auth/account-applications/',
                    'account_applications_manage': f'{base_url}/auth/account-applications/manage/',
                },
                'devices': {
                    'list_create': f'{base_url}/devices/',
                    'stats': f'{base_url}/devices/stats/',
                },
                'resources': {
                    'images': f'{base_url}/resources/images/',
                    'videos': f'{base_url}/resources/videos/',
                    'scrolling_texts': f'{base_url}/resources/scrolling-texts/',
                    'voice_tones': f'{base_url}/resources/voice-tones/',
                    'models': f'{base_url}/resources/models/',
                },
                'commands': {
                    'groups': f'{base_url}/commands/groups/',
                    'control': f'{base_url}/commands/control/',
                    'tasks': f'{base_url}/commands/tasks/',
                    'points': f'{base_url}/commands/points/',
                    'aliyun': f'{base_url}/commands/aliyun/',
                    'data_lookup': f'{base_url}/commands/data/',
                    'export_enabled_groups': f'{base_url}/commands/export/enabled-groups/',
                    'export_commands': f'{base_url}/commands/export/commands/',
                },
                'knowledge_base': {
                    'list_create': f'{base_url}/knowledge-base/',
                    'bulk_download': f'{base_url}/knowledge-base/bulk-download/',
                },
                'ai_models': {
                    'conversations': f'{base_url}/ai-models/chat/conversations/',
                    'llm_providers': f'{base_url}/ai-models/llm-providers/',
                },
            },
        })

# 自定义 Django Admin 站点元信息（去掉默认的「Django 管理」字样）
admin.site.site_header = ''        # 登录后顶部品牌区域
admin.site.site_title = '索灵智能后台'  # 浏览器 Tab 标题
admin.site.index_title = ''        # 首页 H1 标题

urlpatterns = [
    # 浏览器/Tab 自动请求 /favicon.ico；复用 SimpleUI 自带 favicon 避免后台首屏 404 报红。
    path(
        'favicon.ico',
        RedirectView.as_view(
            url='/static/admin/simpleui-x/img/favicon.png',
            permanent=True,
        ),
        name='favicon',
    ),
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/v1/', ApiV1RootView.as_view(), name='api-root'),  # API v1 根视图，列出所有接口（Browsable API 格式）
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/', include('apps.tenants.urls')),
    path('api/v1/', include('apps.devices.urls')),
    path('api/v1/', include('apps.resources.urls')),
    path('api/v1/', include('apps.knowledge_base.urls')),
    path('api/v1/', include('apps.ai_models.urls')),
    path('api/v1/', include('apps.audit.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
elif getattr(settings, 'SERVE_LOCAL_STATIC', False):
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]

# 无 Nginx 直连后端时，允许在 DEBUG=False 下临时托管上传文件。
if settings.DEBUG or getattr(settings, 'SERVE_LOCAL_MEDIA', False):
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

urlpatterns += [
    re_path(r'^(?!api/|static/|media/).*$', backend_not_found_view, name='backend-not-found'),
]
