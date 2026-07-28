from rest_framework import serializers

from .catalogue import RealtimeErrorDefinition


class ErrorCodeSerializer(serializers.Serializer):
    code = serializers.CharField(read_only=True)
    defaultMessage = serializers.CharField(source='default_message', read_only=True)
    category = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    recommendedAction = serializers.CharField(source='recommended_action', read_only=True)
    transports = serializers.ListField(child=serializers.CharField(), read_only=True)
    legacyStatusCode = serializers.IntegerField(source='legacy_status_code', allow_null=True, read_only=True)

    def to_representation(self, instance: RealtimeErrorDefinition) -> dict[str, object]:
        return super().to_representation(instance)
