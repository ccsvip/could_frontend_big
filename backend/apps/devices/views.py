from django.core.cache import cache
from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from apps.accounts.permissions import CanCreateDevices, CanDeleteDevices, CanUpdateDevices, CanViewDevices

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
class DeviceViewSet(viewsets.ModelViewSet):
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
        stats = cache.get('device_stats')
        if not stats:
            grouped = self.get_queryset().values('status').annotate(total=Count('id'))
            stats = {
                'total': self.get_queryset().count(),
                'online': 0,
                'offline': 0,
                'maintaining': 0,
            }
            for item in grouped:
                stats[item['status']] = item['total']
            cache.set('device_stats', stats, timeout=300)
        return Response(stats)
