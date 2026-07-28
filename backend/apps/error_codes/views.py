from django.http import Http404
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apps.accounts.permissions import IsSuperUser

from .catalogue import ERROR_DEFINITIONS, get_error_definition
from .serializers import ErrorCodeSerializer


class ErrorCodeListView(GenericAPIView):
    permission_classes = [IsSuperUser]
    serializer_class = ErrorCodeSerializer

    def get(self, request):
        keyword = str(request.query_params.get('keyword') or '').strip().casefold()
        category = str(request.query_params.get('category') or '').strip()
        definitions = ERROR_DEFINITIONS
        if keyword:
            definitions = tuple(
                definition for definition in definitions
                if keyword in f'{definition.code} {definition.default_message} {definition.description}'.casefold()
            )
        if category:
            definitions = tuple(definition for definition in definitions if definition.category == category)
        categories = sorted({definition.category for definition in ERROR_DEFINITIONS})
        page = self.paginate_queryset(definitions)
        if page is not None:
            response = self.get_paginated_response(self.get_serializer(page, many=True).data)
            response.data['categories'] = categories
            return response
        return Response({'results': self.get_serializer(definitions, many=True).data, 'categories': categories})


class ErrorCodeDetailView(GenericAPIView):
    permission_classes = [IsSuperUser]
    serializer_class = ErrorCodeSerializer

    def get(self, request, code: str):
        definition = get_error_definition(code)
        if definition is None:
            raise Http404
        return Response(self.get_serializer(definition).data)
