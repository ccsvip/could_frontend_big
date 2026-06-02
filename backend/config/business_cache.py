from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from django.conf import settings
from django.core.cache import cache
from rest_framework.response import Response


@dataclass(frozen=True)
class BusinessCacheNamespace:
    key: str
    label: str
    description: str


@dataclass(frozen=True)
class BusinessCacheSummary:
    namespace: str
    label: str
    description: str
    cache_key_count: int


BUSINESS_CACHE_NAMESPACES = (
    BusinessCacheNamespace(
        key='resources',
        label='图片/视频资源',
        description='缓存图片、视频资源列表与详情的文件 URL、名称、大小和分类等元数据。',
    ),
    BusinessCacheNamespace(
        key='voice_tones',
        label='音色资源',
        description='缓存音色列表与详情的图标 URL、音频 URL、文件名、大小和启用状态等元数据。',
    ),
    BusinessCacheNamespace(
        key='scrolling_texts',
        label='滚动文本',
        description='缓存滚动文本列表与详情的标题、启用状态和中英国际化文本。',
    ),
    BusinessCacheNamespace(
        key='knowledge_base',
        label='知识库文档',
        description='缓存知识库文档列表与详情的文件名、大小、状态和下载次数等元数据。',
    ),
)
BUSINESS_CACHE_NAMESPACE_MAP = {namespace.key: namespace for namespace in BUSINESS_CACHE_NAMESPACES}
BUSINESS_CACHE_KEY_PREFIX = 'business-cache'
BUSINESS_CACHE_DEFAULT_TIMEOUT = 300


def is_business_cache_enabled() -> bool:
    return bool(getattr(settings, 'BUSINESS_CACHE_ENABLED', True))


def get_business_cache_timeout() -> int:
    return int(getattr(settings, 'BUSINESS_CACHE_TIMEOUT_SECONDS', BUSINESS_CACHE_DEFAULT_TIMEOUT))


def make_response_cache_key(namespace: str, request) -> str:
    validate_business_cache_namespace(namespace)
    # 缓存键并入租户维度，避免 A 公司缓存的列表/详情被 B 公司请同一 URL 时命中。
    from apps.tenants.services import get_request_tenant
    tenant = get_request_tenant(request)
    tenant_part = tenant.id if tenant is not None else 'none'
    raw_key = f'{request.method}:{request.get_host()}:{request.get_full_path()}:t={tenant_part}'
    digest = sha256(raw_key.encode('utf-8')).hexdigest()
    return f'{BUSINESS_CACHE_KEY_PREFIX}:{namespace}:response:{digest}'


def get_business_response_cache(namespace: str, request) -> Any | None:
    if not is_business_cache_enabled():
        return None
    return cache.get(make_response_cache_key(namespace, request))


def set_business_response_cache(namespace: str, request, data: Any, timeout: int | None = None) -> str:
    if not is_business_cache_enabled():
        return ''

    cache_key = make_response_cache_key(namespace, request)
    cache.set(cache_key, data, timeout=timeout or get_business_cache_timeout())
    register_business_cache_key(namespace, cache_key)
    return cache_key


def register_business_cache_key(namespace: str, cache_key: str):
    validate_business_cache_namespace(namespace)
    registry_key = make_registry_key(namespace)
    registered_keys = set(cache.get(registry_key, []))
    registered_keys.add(cache_key)
    # 业务缓存注册表不设置过期时间，便于 admin 做模块级清理。
    cache.set(registry_key, sorted(registered_keys), timeout=None)


def clear_business_cache_namespace(namespace: str) -> int:
    validate_business_cache_namespace(namespace)
    registry_key = make_registry_key(namespace)
    registered_keys = list(cache.get(registry_key, []))
    if registered_keys:
        cache.delete_many(registered_keys)
    cache.delete(registry_key)
    return len(registered_keys)


def clear_all_business_cache() -> int:
    return sum(clear_business_cache_namespace(namespace.key) for namespace in BUSINESS_CACHE_NAMESPACES)


def get_business_cache_summaries() -> list[BusinessCacheSummary]:
    summaries = []
    for namespace in BUSINESS_CACHE_NAMESPACES:
        cache_keys = cache.get(make_registry_key(namespace.key), [])
        summaries.append(
            BusinessCacheSummary(
                namespace=namespace.key,
                label=namespace.label,
                description=namespace.description,
                cache_key_count=len(cache_keys),
            )
        )
    return summaries


def make_registry_key(namespace: str) -> str:
    validate_business_cache_namespace(namespace)
    return f'{BUSINESS_CACHE_KEY_PREFIX}:{namespace}:registry'


def validate_business_cache_namespace(namespace: str):
    if namespace not in BUSINESS_CACHE_NAMESPACE_MAP:
        raise ValueError(f'Unsupported business cache namespace: {namespace}')


class CachedBusinessResponseMixin:
    business_cache_namespace = ''

    def list(self, request, *args, **kwargs):
        cached_data = self.get_cached_business_response(request)
        if cached_data is not None:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        self.set_cached_business_response(request, response)
        return response

    def retrieve(self, request, *args, **kwargs):
        cached_data = self.get_cached_business_response(request)
        if cached_data is not None:
            return Response(cached_data)

        response = super().retrieve(request, *args, **kwargs)
        self.set_cached_business_response(request, response)
        return response

    def perform_create(self, serializer):
        instance = super().perform_create(serializer)
        self.clear_cached_business_responses()
        return instance

    def perform_update(self, serializer):
        instance = super().perform_update(serializer)
        self.clear_cached_business_responses()
        return instance

    def perform_destroy(self, instance):
        result = super().perform_destroy(instance)
        self.clear_cached_business_responses()
        return result

    def get_cached_business_response(self, request):
        if not self.business_cache_namespace:
            return None
        return get_business_response_cache(self.business_cache_namespace, request)

    def set_cached_business_response(self, request, response):
        if not self.business_cache_namespace or response.status_code != 200:
            return
        set_business_response_cache(self.business_cache_namespace, request, response.data)

    def clear_cached_business_responses(self):
        if self.business_cache_namespace:
            clear_business_cache_namespace(self.business_cache_namespace)
