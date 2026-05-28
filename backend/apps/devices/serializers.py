from rest_framework import serializers

from .models import Device


class DeviceSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='code')
    lastHeartbeat = serializers.DateTimeField(source='last_heartbeat', format='%Y-%m-%d %H:%M:%S', required=False)

    class Meta:
        model = Device
        fields = ('id', 'name', 'location', 'status', 'lastHeartbeat')

    def create(self, validated_data):
        code = validated_data.pop('code')
        return Device.objects.create(code=code, **validated_data)


class DeviceDetailSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source='code')
    lastHeartbeat = serializers.DateTimeField(source='last_heartbeat', format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = Device
        fields = ('id', 'name', 'location', 'status', 'lastHeartbeat', 'created_at', 'updated_at')


class DeviceStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    online = serializers.IntegerField()
    offline = serializers.IntegerField()
    maintaining = serializers.IntegerField()
