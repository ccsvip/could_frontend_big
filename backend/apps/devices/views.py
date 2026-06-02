from django.core.cache import cache
from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.accounts.permissions import CanCreateDevices, CanDeleteDevices, CanUpdateDevices, CanViewDevices
from apps.tenants.mixins import TenantScopedQuerysetMixin

from .models import Device
from .serializers import DeviceDetailSerializer, DeviceSerializer, DeviceStatsSerializer


@extend_schema_view(
    list=extend_schema(tags=['Devices']),
    retrieve=extend_schema(tags=['Devices']),
    create=extend_schema(tags=['Devices']),
    update=extend_schema(tags=['Devices']),
    partial_update=extend_schema(tags=['Devices']),
    destroy=extend_schema(tags=['Devices']),
)
class DeviceViewSet(TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Device.objects.all()
    lookup_field = 'code'

    def get_permissions(self):
        permission_map = {
            'list': [CanViewDevices],
            'retrieve': [CanViewDevices],
            'stats': [CanViewDevices],
            'create': [CanCreateDevices],
            'update': [CanUpdateDevices],
            'partial_update': [CanUpdateDevices],
            'destroy': [CanDeleteDevices],
        }
        permission_classes = permission_map.get(self.action, [CanViewDevices])
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DeviceDetailSerializer
        return DeviceSerializer

    @extend_schema(responses=DeviceStatsSerializer, tags=['Devices'])
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        # 缓存键并入租户维度，避免 A 公司的统计被 B 公司命中（跨租户缓存泄漏）。
        # 超管带 ?tenant=<id> 时按该公司统计，缓存键并入 scoped:<id>，
        # 与全集统计（device_stats:all）互不串读。
        user = getattr(request, 'user', None)
        if user is not None and user.is_superuser:
            scoped_tenant_id = self.superuser_tenant_filter()
            cache_key = (
                f'device_stats:scoped:{scoped_tenant_id}'
                if scoped_tenant_id is not None
                else 'device_stats:all'
            )
        else:
            tenant = self.request_tenant
            cache_key = f'device_stats:{tenant.id if tenant else "all"}'
        stats = cache.get(cache_key)
        if not stats:
            # get_queryset() 已走 apply_tenant_scope，统计天然按当前作用域正确。
            grouped = self.get_queryset().values('status').annotate(total=Count('id'))
            stats = {
                'total': self.get_queryset().count(),
                'online': 0,
                'offline': 0,
                'maintaining': 0,
            }
            for item in grouped:
                stats[item['status']] = item['total']
            cache.set(cache_key, stats, timeout=300)
        return Response(stats)
