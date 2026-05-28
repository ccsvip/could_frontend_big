from apps.resources.models import Point  # pyright: ignore[reportImplicitRelativeImport]


class PointApiTest(Point):
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        proxy = True
        default_permissions = ()
        verbose_name = '指令任务接口测试'
        verbose_name_plural = '指令任务接口测试'


class ApiTester(Point):
    """通用 API 接口测试 proxy model（借 Point 表挂在 admin 上，不存数据）。"""

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        proxy = True
        default_permissions = ()
        verbose_name = '全部接口测试'
        verbose_name_plural = '全部接口测试'
