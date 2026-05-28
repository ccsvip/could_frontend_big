from rest_framework import serializers

from .point_models import Point


class PointSerializer(serializers.ModelSerializer):
    isActive = serializers.BooleanField(source='is_active', required=False, default=True)
    isShow = serializers.BooleanField(source='is_show', required=False, default=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Point
        fields = (
            'id',
            'name',
            'command',
            'isActive',
            'isShow',
            'createdAt',
            'updatedAt',
        )
        read_only_fields = ('id', 'createdAt', 'updatedAt')

    def validate_command(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('请输入点位命令')
        queryset = Point.objects.filter(command=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('该点位命令已存在')
        return value
