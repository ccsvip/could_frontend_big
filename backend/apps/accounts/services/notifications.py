from __future__ import annotations

from typing import Any

from apps.resources.services.feishu import notify_business_event, send_feishu_text

from ..models import AccountApplication


def notify_account_application_created(application: AccountApplication) -> bool:
    """发送账号申请创建通知到飞书。"""
    email = application.email or '未填写'
    text = (
        '📩 账号入驻申请通知\n'
        f'登录用户名：{application.login_username}\n'
        f'申请人姓名：{application.applicant_name}\n'
        f'手机号：{application.phone}\n'
        f'企业邮箱：{email}\n'
        f'申请说明：{application.reason}'
    )
    return send_feishu_text(text)


def notify_account_application_reviewed(application: AccountApplication, user: Any) -> bool:
    """发送账号申请审核结果通知到飞书。"""
    status_label = application.get_status_display()
    return notify_business_event(
        title='账号申请审核通知',
        action='review',
        user=user,
        target_label='登录用户名',
        target_name=application.login_username,
        extra_lines=[
            f'申请人姓名：{application.applicant_name}',
            f'手机号：{application.phone}',
            f'审核结果：{status_label}',
        ],
    )
