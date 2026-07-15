from django.contrib.auth import authenticate
from kombu.exceptions import OperationalError
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import OpenApiResponse, extend_schema

from .models import AccountApplication
from .permissions import CanReviewAccountApplications, CanViewAccountApplications
from .serializers import (
    AccountApplicationCreateSerializer,
    AccountApplicationResponseSerializer,
    AccountApplicationStatusSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    UserSerializer,
)
from .services.notifications import notify_account_application_created, notify_account_application_reviewed
from .tasks import notify_account_application
from apps.tenants.services import get_user_tenant


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=LoginSerializer,
        responses={200: OpenApiResponse(description='登录成功')},
        tags=['Auth'],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )
        if not user:
            return Response(
                {
                    'status': 'error',
                    'message': '账号或密码错误',
                    'code': status.HTTP_400_BAD_REQUEST,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # tenant_id 写入 JWT claim 仅作辅助；权威租户上下文始终以 DB 的 Membership 为准
        # （避免 superuser 重新归属数据后旧 token 串租户）。
        tenant = get_user_tenant(user)
        if tenant is not None and not tenant.is_active:
            return Response(
                {
                    'status': 'error',
                    'message': '公司已停用，请联系管理员',
                    'code': status.HTTP_403_FORBIDDEN,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        refresh = RefreshToken.for_user(user)
        if tenant is not None:
            refresh['tenant_id'] = tenant.id
        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
                'message': '登录成功',
            }
        )


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=UserSerializer, tags=['Auth'])
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={200: OpenApiResponse(description='密码修改成功')},
        tags=['Auth'],
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data['newPassword'])
        request.user.save(update_fields=['password'])
        # 清除首登强制改密标志（员工自行改密后即解除拦截）。
        from apps.tenants.models import Membership
        Membership.objects.filter(user=request.user, must_change_password=True).update(must_change_password=False)
        return Response(
            {
                'status': 'success',
                'message': '密码修改成功，请重新登录',
            }
        )


class AccountApplicationCreateView(generics.CreateAPIView):
    authentication_classes = []
    queryset = AccountApplication.objects.all()
    serializer_class = AccountApplicationCreateSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=AccountApplicationCreateSerializer,
        responses={201: AccountApplicationResponseSerializer},
        tags=['Accounts'],
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        try:
            notify_account_application.delay(application.id)
        except OperationalError:
            # Celery 暂不可用时同步兜底，避免申请通知直接丢失。
            notify_account_application_created(application)
        response_data = AccountApplicationResponseSerializer(application).data
        return Response(
            {
                'status': 'success',
                'message': '账号申请已提交，管理员会尽快审核',
                'data': response_data,
            },
            status=status.HTTP_201_CREATED,
        )


class AccountApplicationListView(generics.ListAPIView):
    queryset = AccountApplication.objects.all()
    serializer_class = AccountApplicationResponseSerializer
    permission_classes = [CanViewAccountApplications]


class AccountApplicationDetailView(generics.RetrieveUpdateAPIView):
    queryset = AccountApplication.objects.all()

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            permission_classes = [CanViewAccountApplications]
        else:
            permission_classes = [CanReviewAccountApplications]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return AccountApplicationStatusSerializer
        return AccountApplicationResponseSerializer

    @extend_schema(
        request=AccountApplicationStatusSerializer,
        responses={200: AccountApplicationResponseSerializer},
        tags=['Accounts'],
    )
    def patch(self, request, *args, **kwargs):
        application = self.get_object()
        serializer = self.get_serializer(application, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        notify_account_application_reviewed(application, request.user)

        response_data = AccountApplicationResponseSerializer(application).data
        status_text = '已通过' if application.status == AccountApplication.STATUS_APPROVED else '已拒绝'
        return Response(
            {
                'status': 'success',
                'message': f'审核操作成功，状态已更新为{status_text}',
                'data': response_data,
            }
        )
