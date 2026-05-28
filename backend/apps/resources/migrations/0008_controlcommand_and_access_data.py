from django.db import migrations, models


DEFAULT_CONTROL_COMMANDS = """
UDP 协议 IP 192.168.29.3 端口 13553
开启全厅 BenControlAOpenAll
关闭全厅 BenControlACloseAll
开启全厅灯光 BenControlAOpenLights
关闭全厅灯光 BenControlACloseLights
开启全厅设备 BenControlAOpenEquipments
关闭全厅设备 BenControlACloseEquipments
开启创业故事触控机 BenControlAOpenComputer1
关闭创业故事触控机 BenControlACloseComputer1
开启逐梦远航触控机 BenControlAOpenComputer2
关闭逐梦远航触控机 BenControlACloseComputer2
开启团队决策触控机 BenControlAOpenComputer3
关闭团队决策触控机 BenControlACloseComputer3
开启拼接屏主机 BenControlAOpenComputer4
关闭拼接屏主机 BenControlACloseComputer4
开启投影幕主机 BenControlAOpenComputer5
关闭投影幕主机 BenControlACloseComputer5
开启党建引领触控机 BenControlAOpenComputer6
关闭党建引领触控机 BenControlACloseComputer6
开启党建惠企触控机 BenControlAOpenComputer7
关闭党建惠企触控机 BenControlACloseComputer7
开启投影1 BenControlAOpenProjector1
关闭投影1 BenControlACloseProjector1
开启投影2 BenControlAOpenProjector2
关闭投影2 BenControlACloseProjector2
开启照明筒灯 BenControlAOpenLight1
关闭照明筒灯 BenControlACloseLight1
开启门口形象墙灯条 BenControlAOpenLight2
关闭门口形象墙灯条 BenControlACloseLight2
开启门口形象墙灯带 BenControlAOpenLight3
关闭门口形象墙灯带 BenControlACloseLight3
开启扬帆起航区弧顶灯带 BenControlAOpenLight4
关闭扬帆起航区弧顶灯带 BenControlACloseLight4
开启扬帆起航区射灯 BenControlAOpenLight5
关闭扬帆起航区射灯 BenControlACloseLight5
开启智慧护航区灯带 BenControlAOpenLight6
关闭智慧护航区灯带 BenControlACloseLight6
开启党建引领区灯带 BenControlAOpenLight7
关闭党建引领区灯带 BenControlACloseLight7
开启模拟航驶区灯带 BenControlAOpenLight8
关闭模拟航驶区灯带 BenControlACloseLight8
开启党建惠企区灯带 BenControlAOpenLight9
关闭党建惠企区灯带 BenControlACloseLight9
开启企业展厅门禁 BenControlAOpenDoor1
关闭企业展厅门禁 BenControlACloseDoor1
开启党建展厅门禁 BenControlAOpenDoor2
关闭党建展厅门禁 BenControlACloseDoor2
创业故事-动态屏保 BenControlBPlayProtect1
创业故事-静态屏保 BenControlBPlayProtect2
创业故事-播放视频1 BenControlBPlayVideo1
创业故事-暂停视频 BenControlBStopVideo
创业故事-恢复播放 BenControlBPlayVideo
拼接屏-播放桌面 BenControlCPlayDesktop
拼接屏-播放平台一 BenControlCPlayNet1
拼接屏-播放平台二 BenControlCPlayNet2
拼接屏-播放平台三 BenControlCPlayNet3
拼接屏-播放平台四 BenControlCPlayNet4
拼接屏-播放平台五 BenControlCPlayNet5
拼接屏-网页往下滚动 BenControlCPlayNetDown
拼接屏-网页往上滚动 BenControlCPlayNetUp
拼接屏-播放播放器 BenControlCPlayPlayer
拼接屏-播放屏保 BenControlCPlayProtect
拼接屏-播放PPT BenControlCPlayImg
拼接屏-播放PPT下一页 BenControlCPlayImgNext
拼接屏-播放PPT上一页 BenControlCPlayImgPrev
拼接屏-播放莹石云（船舶CCTV） BenControlCYSY
拼接幕-播放视频一 BenControlCPlayVideo1
拼接幕-播放视频二 BenControlCPlayVideo2
拼接幕-播放视频三 BenControlCPlayVideo3
拼接幕-播放视频四 BenControlCPlayVideo4
拼接幕-播放视频五 BenControlCPlayVideo5
拼接幕-暂停视频 BenControlCStopVideo
拼接幕-恢复播放 BenControlCPlayVideo
投影幕-播放屏保 BenControlDPlayProtect
投影幕-播放视频一 BenControlDPlayVideo1
投影幕-播放视频二 BenControlDPlayVideo2
投影幕-播放视频三 BenControlDPlayVideo3
投影幕-播放视频四 BenControlDPlayVideo4
投影幕-播放视频五 BenControlDPlayVideo5
投影幕-播放视频六 BenControlDPlayVideo6
投影幕-播放视频七 BenControlDPlayVideo7
投影幕-播放视频八 BenControlDPlayVideo8
投影幕-播放视频九 BenControlDPlayVideo9
投影幕-播放视频十 BenControlDPlayVideo10
投影幕-暂停视频 BenControlDStopVideo
投影幕-恢复播放 BenControlDPlayVideo
逐梦远航-播放桌面 BenControlEPlayDesktop
逐梦远航-播放播放器 BenControlEPlayPlayer
逐梦远航-播放屏保 BenControlEPlayProtect
逐梦远航-播放目录页 BenControlEPlayMain
逐梦远航-下一页 BenControlEPlayImgNext
逐梦远航-上一页 BenControlEPlayImgPrev
团队决策-播放屏保 BenControlFPlayProtect
团队决策-播放目录页 BenControlFPlayMain
团队决策-下一页 BenControlFPlayImgNext
团队决策-上一页 BenControlFPlayImgPrev
党建引领-播放屏保 BenControlGPlayProtect
党建引领-播放目录页 BenControlGPlayMain
党建引领-下一页 BenControlGPlayImgNext
党建引领-上一页 BenControlGPlayImgPrev
党建惠企-播放屏保 BenControlHPlayProtect
党建引领-播放首页 BenControlHPlayMain
党建惠企-下一页 BenControlHPlayImgNext
党建惠企-上一页 BenControlHPlayImgPrev
模拟海航-默认模式 BenControlJPlayDefault
模拟海航-风和日丽白天 BenControlJPlaySunnyDay
模拟海航-风和日丽夜晚 BenControlJPlaySunnyNight
模拟海航-极端天气白天 BenControlJPlayStormDay
模拟海航-极端天气夜晚 BenControlJPlayStormNight
""".strip()


CATEGORY_RULES = (
    ('全厅', ('全厅',)),
    ('设备控制', ('触控机', '主机', '投影', '照明', '灯', '门禁')),
    ('创业故事', ('创业故事',)),
    ('拼接屏', ('拼接屏', '拼接幕')),
    ('投影幕', ('投影幕',)),
    ('逐梦远航', ('逐梦远航',)),
    ('团队决策', ('团队决策',)),
    ('党建引领', ('党建引领',)),
    ('党建惠企', ('党建惠企',)),
    ('模拟海航', ('模拟海航',)),
)


def normalize_line(line):
    return ' '.join(str(line or '').strip().split())


def infer_category(name):
    for category, keywords in CATEGORY_RULES:
        if any(keyword in name for keyword in keywords):
            return category
    return '未分类'


def infer_target(name):
    if '-' in name:
        return name.split('-', 1)[0].strip()
    if name.startswith('开启') or name.startswith('关闭'):
        return name[2:].strip()
    return name.strip()


def build_default_command_items():
    lines = [normalize_line(line) for line in DEFAULT_CONTROL_COMMANDS.splitlines() if normalize_line(line)]
    header = lines[0]
    parts = header.split()
    protocol = parts[0]
    host = parts[3]
    port = int(parts[5])

    items = []
    for index, line in enumerate(lines[1:], start=1):
        name, command_code = line.rsplit(' ', 1)
        items.append(
            {
                'name': name,
                'command_code': command_code,
                'category': infer_category(name),
                'target': infer_target(name),
                'protocol': protocol,
                'host': host,
                'port': port,
                'payload_json': {},
                'description': '',
                'sort': index,
                'is_active': True,
                'is_visible': True,
            }
        )
    return items


def seed_control_command_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    Role = apps.get_model('accounts', 'Role')
    ControlCommand = apps.get_model('resources', 'ControlCommand')

    command_parent, _ = Menu.objects.update_or_create(
        key='/commands',
        defaults={
            'name': '指令管理',
            'path': '/commands',
            'icon': 'ThunderboltOutlined',
            'sort_order': 40,
            'is_active': True,
            'parent_id': None,
        },
    )

    command_menu, _ = Menu.objects.update_or_create(
        key='/commands/control',
        defaults={
            'name': '控制指令',
            'path': '/commands/control',
            'icon': 'ThunderboltOutlined',
            'sort_order': 41,
            'is_active': True,
            'parent_id': command_parent.id,
        },
    )

    permission_points = []
    for name, code, description in [
        ('查看控制指令', 'commands.control.view', '允许查看控制指令列表与详情'),
        ('创建控制指令', 'commands.control.create', '允许新增控制指令'),
        ('编辑控制指令', 'commands.control.update', '允许编辑控制指令'),
        ('删除控制指令', 'commands.control.delete', '允许删除控制指令'),
        ('导入控制指令', 'commands.control.import', '允许导入控制指令 JSON'),
        ('导出控制指令', 'commands.control.export', '允许导出控制指令 JSON'),
    ]:
        permission_point, _ = PermissionPoint.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'module': 'commands_control',
                'description': description,
                'is_active': True,
            },
        )
        permission_points.append(permission_point)

    readonly_codes = {'commands.control.view', 'commands.control.export'}
    readonly_permission_points = [item for item in permission_points if item.code in readonly_codes]

    for role in Role.objects.all():
        role.menus.add(command_menu)
        if role.code == 'admin':
            role.permission_points.add(*permission_points)
        else:
            role.permission_points.add(*readonly_permission_points)

    for item in build_default_command_items():
        ControlCommand.objects.update_or_create(
            command_code=item['command_code'],
            defaults=item,
        )


def unseed_control_command_access_data(apps, schema_editor):
    Menu = apps.get_model('accounts', 'Menu')
    PermissionPoint = apps.get_model('accounts', 'PermissionPoint')
    ControlCommand = apps.get_model('resources', 'ControlCommand')

    ControlCommand.objects.filter(command_code__startswith='BenControl').delete()
    PermissionPoint.objects.filter(code__startswith='commands.control.').delete()
    Menu.objects.filter(key='/commands/control').delete()
    Menu.objects.filter(key='/commands').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0004_menu_parent'),
        ('resources', '0007_update_admin_labels'),
    ]

    operations = [
        migrations.CreateModel(
            name='ControlCommand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='指令名称')),
                ('command_code', models.CharField(max_length=128, unique=True, verbose_name='指令标识')),
                ('category', models.CharField(max_length=64, verbose_name='分类')),
                ('target', models.CharField(blank=True, default='', max_length=128, verbose_name='目标对象')),
                ('protocol', models.CharField(choices=[('UDP', 'UDP'), ('TCP', 'TCP'), ('HTTP', 'HTTP')], default='UDP', max_length=16, verbose_name='协议')),
                ('host', models.GenericIPAddressField(verbose_name='主机地址')),
                ('port', models.PositiveIntegerField(verbose_name='端口')),
                ('payload_json', models.JSONField(blank=True, default=dict, verbose_name='指令内容')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='说明')),
                ('sort', models.PositiveIntegerField(default=0, verbose_name='排序')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('is_visible', models.BooleanField(default=True, verbose_name='前端可见')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '控制指令',
                'verbose_name_plural': '控制指令',
                'ordering': ['category', 'sort', 'id'],
            },
        ),
        migrations.RunPython(seed_control_command_access_data, unseed_control_command_access_data),
    ]
