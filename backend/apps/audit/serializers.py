from rest_framework import serializers

from .models import OperationLog


class OperationLogSerializer(serializers.ModelSerializer):
    actorUsername = serializers.CharField(source='actor_username', read_only=True)
    actorDisplayName = serializers.CharField(source='actor_display_name', read_only=True)
    actorRoleName = serializers.CharField(source='actor_role_name', read_only=True)
    tenantName = serializers.CharField(source='tenant.name', read_only=True, default=None)
    statusCode = serializers.IntegerField(source='status_code', read_only=True)
    description = serializers.CharField(read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = OperationLog
        fields = (
            'id',
            'actor',
            'actorUsername',
            'actorDisplayName',
            'actorRoleName',
            'tenant',
            'tenantName',
            'action',
            'method',
            'path',
            'description',
            'statusCode',
            'createdAt',
        )
        read_only_fields = fields
