from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    """
    统一异常处理器，返回格式：
    {
        "status": "error",
        "message": "错误信息",
        "code": 400
    }
    """
    # 先调用 DRF 默认的异常处理器
    response = drf_exception_handler(exc, context)

    if response is not None:
        # DRF 已处理的异常
        custom_response = {
            'status': 'error',
            'message': '',
            'code': response.status_code,
        }
        response_data = getattr(exc, 'response_data', None)
        if response_data is not None:
            custom_response['data'] = response_data

        # 提取错误信息
        if isinstance(response.data, dict):
            if 'detail' in response.data:
                custom_response['message'] = response.data['detail']
            else:
                # 处理字段验证错误
                errors = []
                for field, messages in response.data.items():
                    if isinstance(messages, list):
                        for msg in messages:
                            msg_str = str(msg)
                            # 特殊处理手机号唯一约束错误
                            if '手机号' in msg_str and '已存在' in msg_str:
                                errors.append('该手机号已提交过申请，请勿重复提交')
                            else:
                                errors.append(msg_str)
                    else:
                        msg_str = str(messages)
                        # 特殊处理手机号唯一约束错误
                        if '手机号' in msg_str and '已存在' in msg_str:
                            errors.append('该手机号已提交过申请，请勿重复提交')
                        else:
                            errors.append(msg_str)
                custom_response['message'] = '；'.join(errors) if errors else '请求参数错误'
        elif isinstance(response.data, list):
            custom_response['message'] = '；'.join(str(msg) for msg in response.data)
        else:
            custom_response['message'] = str(response.data)

        response.data = custom_response
        return response

    # 处理数据库完整性错误（如唯一约束）
    if isinstance(exc, IntegrityError):
        error_message = str(exc)
        if 'phone' in error_message and '已经存在' in error_message:
            message = '该手机号已提交过申请，请勿重复提交'
        elif 'unique constraint' in error_message.lower() or 'already exists' in error_message.lower():
            message = '数据重复，该记录已存在'
        else:
            message = '数据保存失败，请检查输入信息'

        return Response(
            {
                'status': 'error',
                'message': message,
                'code': status.HTTP_400_BAD_REQUEST,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 处理 Django 验证错误
    if isinstance(exc, DjangoValidationError):
        return Response(
            {
                'status': 'error',
                'message': '；'.join(exc.messages) if hasattr(exc, 'messages') else str(exc),
                'code': status.HTTP_400_BAD_REQUEST,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 未处理的异常
    return Response(
        {
            'status': 'error',
            'message': '服务器内部错误，请稍后重试',
            'code': status.HTTP_500_INTERNAL_SERVER_ERROR,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
