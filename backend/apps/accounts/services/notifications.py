from __future__ import annotations

from typing import Any

from apps.resources.services.feishu import notify_business_event_card

from ..models import AccountApplication


def notify_account_application_created(application: AccountApplication) -> bool:
    """发送账号申请创建通知到飞书卡片。"""
    return notify_business_event_card(
        title='账号入驻申请通知',
        action='submit',
        user=None,
        target_label='登录用户名',
        target_name=application.login_username,
        extra_lines=[
            f'**申请人姓名**\n{application.applicant_name}',
            f'**企业名称**\n{application.enterprise_name}',
            f'**手机号**\n{application.phone}',
            f'**申请说明**\n{application.reason}',
        ],
    )


def notify_account_application_reviewed(application: AccountApplication, user: Any) -> bool:
    """发送账号申请审核结果通知到飞书卡片。"""
    status_label = application.get_status_display()
    return notify_business_event_card(
        title='账号申请审核通知',
        action='review',
        user=user,
        target_label='登录用户名',
        target_name=application.login_username,
        extra_lines=[
            f'**申请人姓名**\n{application.applicant_name}',
            f'**手机号**\n{application.phone}',
            f'**审核结果**\n{status_label}',
        ],
        company_name=application.enterprise_name,
    )
