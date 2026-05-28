from django.db.models import Prefetch
from rest_framework import status

from .models import TaskCommand, TaskCommandStep
from .serializers import build_task_command_list, build_task_step_runtime_data


def build_point_runtime_lookup_response(request, command: str):
    """运行时按 command 查询字符串直接返回同名任务指令的编排列表。"""
    task_command = TaskCommand.objects.filter(command_code=command, is_active=True, group__is_active=True).first()
    if task_command is None:
        return (
            {'status': 'error', 'message': '指令不存在', 'code': 40401, 'data': None},
            status.HTTP_404_NOT_FOUND,
        )

    inner_step_queryset = TaskCommandStep.objects.select_related('control_command', 'point', 'resource').order_by('order', 'id')
    steps = list(
        TaskCommandStep.objects.filter(task_command=task_command, parent__isnull=True)
        .select_related('control_command', 'point', 'resource')
        .prefetch_related(Prefetch('inner_tasks', queryset=inner_step_queryset))
        .order_by('order', 'id')
    )
    return (
        {
            'status': 'success',
            'message': 'success',
            'code': 200,
            'data': {
                'commandType': 'task',
                'name': task_command.name,
                'command': task_command.command_code,
                'tasks': [build_task_step_runtime_data(request, step) for step in steps],
                'command_list': build_task_command_list(steps),
            },
        },
        status.HTTP_200_OK,
    )
