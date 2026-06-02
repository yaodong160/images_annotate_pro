"""Flask CLI 命令：初始化数据库和数据"""
import click
from flask import current_app
from app.extensions import db
from app.models.user import User, Role, Menu, Permission
from app.models.annotation import AnnotationCategory, AnnotationProject


def register_commands(app):
    """注册 CLI 命令"""

    @app.cli.command('init-db')
    def init_db():
        """创建所有数据库表"""
        db.create_all()
        click.echo('[OK] 数据库表创建成功！')

    @app.cli.command('drop-db')
    def drop_db():
        """删除所有数据库表"""
        if click.confirm('[WARN]  确定要删除所有数据库表吗？数据将不可恢复！'):
            db.drop_all()
            click.echo('[OK] 数据库表已删除！')

    @app.cli.command('fix-image-filenames')
    def fix_image_filenames():
        """修复 AnnotatedImage 的 filename 字段：从 file_path 提取实际文件名"""
        from app.models.annotation import AnnotatedImage
        import os

        images = AnnotatedImage.query.all()
        fixed = 0
        for img in images:
            if img.file_path:
                actual_name = os.path.basename(img.file_path)
                if img.filename != actual_name:
                    click.echo(f'  {img.id}: "{img.filename}" -> "{actual_name}"')
                    img.filename = actual_name
                    fixed += 1
        db.session.commit()
        click.echo(f'[OK] 共修复 {fixed} 条记录')

    @app.cli.command('seed-db')
    def seed_db():
        """初始化种子数据（角色、账号、标注分类）"""
        # 创建超级管理员角色 (R_SUPER)
        super_role = Role.query.filter_by(code='R_SUPER').first()
        if not super_role:
            super_role = Role(
                name='超级管理员',
                code='R_SUPER',
                description='超级管理员，拥有所有权限',
            )
            db.session.add(super_role)
            click.echo('[OK] 超级管理员角色创建成功 (R_SUPER)')

        # 创建管理员角色 (R_ADMIN)
        admin_role = Role.query.filter_by(code='R_ADMIN').first()
        if not admin_role:
            admin_role = Role(
                name='管理员',
                code='R_ADMIN',
                description='管理员，拥有管理权限',
            )
            db.session.add(admin_role)
            click.echo('[OK] 管理员角色创建成功 (R_ADMIN)')

        # 创建普通用户角色 (R_USER)
        user_role = Role.query.filter_by(code='R_USER').first()
        if not user_role:
            user_role = Role(
                name='普通用户',
                code='R_USER',
                description='普通用户，基础权限',
            )
            db.session.add(user_role)
            click.echo('[OK] 普通用户角色创建成功 (R_USER)')

        # 创建标注员角色
        annotator_role = Role.query.filter_by(code='annotator').first()
        if not annotator_role:
            annotator_role = Role(
                name='标注员',
                code='annotator',
                description='图片标注人员，可上传和标注图片',
            )
            db.session.add(annotator_role)
            click.echo('[OK] 标注员角色创建成功')

        db.session.commit()

        # 创建菜单种子数据
        _seed_menus()
        # 创建按钮权限种子数据
        _seed_permissions()

        # 获取角色引用（用于后续授权）
        super_role = Role.query.filter_by(code='R_SUPER').first()
        admin_role = Role.query.filter_by(code='R_ADMIN').first()
        user_role = Role.query.filter_by(code='R_USER').first()

        # 创建管理员账号（多角色：R_SUPER + R_ADMIN）
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                nickname='超级管理员',
                email='admin@example.com',
                status=True,
            )
            admin_user.set_password('admin123')
            admin_user.roles = [super_role, admin_role]
            db.session.add(admin_user)
            click.echo('[OK] 管理员账号创建成功 (admin / admin123) [R_SUPER, R_ADMIN]')

        # 创建测试用户（普通角色）
        test_user = User.query.filter_by(username='test').first()
        if not test_user:
            test_user = User(
                username='test',
                nickname='测试用户',
                email='test@example.com',
                status=True,
            )
            test_user.set_password('test123')
            test_user.roles = [user_role]
            db.session.add(test_user)
            click.echo('[OK] 测试账号创建成功 (test / test123) [R_USER]')

        db.session.commit()

        # 为 R_SUPER 角色授予所有菜单和按钮权限
        _assign_full_permissions_to_super()

        # 为 R_ADMIN 角色授予部分权限
        _assign_admin_permissions()

        # 为 R_USER 角色授予基础权限
        _assign_user_permissions()

        # 创建标注分类种子数据
        _seed_annotation_categories()
        # 创建标注项目种子数据
        _seed_annotation_projects()
        click.echo('\n[DONE] 种子数据初始化完成！')


def _seed_annotation_categories():
    """初始化标注分类种子数据"""
    categories = [
        {'name': '人物', 'code': 'person', 'color': '#1890ff', 'sort_order': 1,
         'description': '人、行人、骑行者等'},
        {'name': '车辆', 'code': 'vehicle', 'color': '#52c41a', 'sort_order': 2,
         'description': '汽车、卡车、公交车等', 'children': [
            {'name': '小汽车', 'code': 'car', 'color': '#73d13d', 'sort_order': 1},
            {'name': '卡车', 'code': 'truck', 'color': '#95de64', 'sort_order': 2},
            {'name': '公交车', 'code': 'bus', 'color': '#b7eb8f', 'sort_order': 3},
            {'name': '摩托车', 'code': 'motorcycle', 'color': '#d9f7be', 'sort_order': 4},
            {'name': '自行车', 'code': 'bicycle', 'color': '#f6ffed', 'sort_order': 5},
        ]},
        {'name': '动物', 'code': 'animal', 'color': '#fa8c16', 'sort_order': 3,
         'description': '猫、狗、鸟等'},
        {'name': '交通标志', 'code': 'traffic_sign', 'color': '#ff4d4f', 'sort_order': 4,
         'description': '红绿灯、限速牌、指示牌等'},
        {'name': '建筑', 'code': 'building', 'color': '#722ed1', 'sort_order': 5,
         'description': '楼房、房屋等'},
        {'name': '障碍物', 'code': 'obstacle', 'color': '#faad14', 'sort_order': 6,
         'description': '路障、锥桶、施工区域等'},
        {'name': '其他', 'code': 'other', 'color': '#8c8c8c', 'sort_order': 99,
         'description': '其他未分类对象'},
    ]

    for cat_data in categories:
        existing = AnnotationCategory.query.filter_by(code=cat_data['code']).first()
        if not existing:
            children = cat_data.pop('children', [])
            category = AnnotationCategory(**cat_data)
            db.session.add(category)
            db.session.flush()  # 获取 category.id

            for child_data in children:
                child_existing = AnnotationCategory.query.filter_by(code=child_data['code']).first()
                if not child_existing:
                    child = AnnotationCategory(
                        parent_id=category.id,
                        **child_data
                    )
                    db.session.add(child)

    db.session.commit()
    click.echo('[OK] 标注分类种子数据创建成功')


def _seed_annotation_projects():
    """初始化标注项目种子数据"""
    import json
    projects = [
        {
            'project_name': '道路标识标注',
            'description': '用于标注城市道路上的各类交通标识和设施',
            'classes': [{'name': '人物'}, {'name': '车辆'}, {'name': '交通标志'}, {'name': '障碍物'}],
            'tags': ['城市道路', '白天', '高优先级'],
            'enable_comment': True,
            'tools': ['create-box', 'create-polygon', 'create-point'],
            'member_ids': ['admin', 'test'],
            'status': 'active',
        },
        {
            'project_name': '人脸关键点标注',
            'description': '人脸图片的关键点标注项目，用于训练人脸识别模型',
            'classes': [{'name': '人物'}],
            'tags': ['人脸', '关键点', 'AI训练'],
            'enable_comment': False,
            'tools': ['create-point'],
            'member_ids': ['admin'],
            'status': 'active',
        },
    ]

    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        click.echo('[WARN] 管理员账号不存在，跳过项目种子数据')
        return

    for proj_data in projects:
        existing = AnnotationProject.query.filter_by(project_name=proj_data['project_name']).first()
        if not existing:
            project = AnnotationProject(
                project_name=proj_data['project_name'],
                description=proj_data['description'],
                classes=json.dumps(proj_data['classes'], ensure_ascii=False),
                tags=json.dumps(proj_data['tags'], ensure_ascii=False),
                enable_comment=proj_data['enable_comment'],
                tools=json.dumps(proj_data['tools'], ensure_ascii=False),
                member_ids=json.dumps(proj_data['member_ids'], ensure_ascii=False),
                status=proj_data['status'],
                created_by=admin_user.id,
                updated_by=admin_user.id,
            )
            db.session.add(project)

    db.session.commit()
    click.echo('[OK] 标注项目种子数据创建成功')


def _seed_menus():
    """初始化菜单种子数据（树形结构）"""
    menus_data = [
        {
            'name': 'Dashboard',
            'path': '/dashboard',
            'component': 'dashboard',
            'icon': 'dashboard',
            'sort_order': 1,
            'children': [],
        },
        {
            'name': '系统管理',
            'path': '/system',
            'component': '',
            'icon': 'setting',
            'sort_order': 2,
            'children': [
                {'name': '用户管理', 'path': '/system/user', 'component': 'system/user', 'icon': 'user', 'sort_order': 1},
                {'name': '角色管理', 'path': '/system/role', 'component': 'system/role', 'icon': 'role', 'sort_order': 2},
            ],
        },
        {
            'name': '标注管理',
            'path': '/annotation',
            'component': '',
            'icon': 'edit',
            'sort_order': 3,
            'children': [
                {'name': '项目管理', 'path': '/annotation/project', 'component': 'annotation/project', 'icon': 'project', 'sort_order': 1},
                {'name': '图片标注', 'path': '/annotation/image', 'component': 'annotation/image', 'icon': 'picture', 'sort_order': 2},
            ],
        },
    ]

    def _create_menu(parent_id, menu_data):
        existing = Menu.query.filter_by(path=menu_data['path']).first()
        if existing:
            return existing
        children = menu_data.pop('children', [])
        menu = Menu(parent_id=parent_id, **menu_data)
        db.session.add(menu)
        db.session.flush()
        for child_data in children:
            _create_menu(menu.id, child_data)
        return menu

    for m in menus_data:
        _create_menu(None, m)

    db.session.commit()
    click.echo('[OK] 菜单种子数据创建成功')


def _seed_permissions():
    """初始化按钮权限种子数据"""
    # 获取菜单
    user_menu = Menu.query.filter_by(path='/system/user').first()
    role_menu = Menu.query.filter_by(path='/system/role').first()

    permissions_data = [
        # 用户管理按钮权限
        {'menu_id': user_menu.id if user_menu else 1, 'name': '新增用户', 'code': 'system:user:add', 'sort_order': 1},
        {'menu_id': user_menu.id if user_menu else 1, 'name': '编辑用户', 'code': 'system:user:edit', 'sort_order': 2},
        {'menu_id': user_menu.id if user_menu else 1, 'name': '删除用户', 'code': 'system:user:delete', 'sort_order': 3},
        {'menu_id': user_menu.id if user_menu else 1, 'name': '查看用户', 'code': 'system:user:list', 'sort_order': 4},
        # 角色管理按钮权限
        {'menu_id': role_menu.id if role_menu else 2, 'name': '新增角色', 'code': 'system:role:add', 'sort_order': 1},
        {'menu_id': role_menu.id if role_menu else 2, 'name': '编辑角色', 'code': 'system:role:edit', 'sort_order': 2},
        {'menu_id': role_menu.id if role_menu else 2, 'name': '删除角色', 'code': 'system:role:delete', 'sort_order': 3},
        {'menu_id': role_menu.id if role_menu else 2, 'name': '查看角色', 'code': 'system:role:list', 'sort_order': 4},
    ]

    for p_data in permissions_data:
        existing = Permission.query.filter_by(code=p_data['code']).first()
        if not existing:
            perm = Permission(**p_data)
            db.session.add(perm)

    db.session.commit()
    click.echo('[OK] 按钮权限种子数据创建成功')


def _assign_full_permissions_to_super():
    """为 R_SUPER 角色授予所有菜单和按钮权限"""
    super_role = Role.query.filter_by(code='R_SUPER').first()
    if not super_role:
        return

    all_menus = Menu.query.filter_by(status=True).all()
    all_perms = Permission.query.filter_by(status=True).all()

    super_role.menus = all_menus
    super_role.permissions = all_perms
    db.session.commit()
    click.echo('[OK] R_SUPER 角色已授予所有菜单和按钮权限')


def _assign_admin_permissions():
    """为 R_ADMIN 角色授予管理相关权限"""
    admin_role = Role.query.filter_by(code='R_ADMIN').first()
    if not admin_role:
        return

    # 管理员有全部菜单和权限（略少于超管，此处简化）
    all_menus = Menu.query.filter_by(status=True).all()
    all_perms = Permission.query.filter_by(status=True).all()

    admin_role.menus = all_menus
    admin_role.permissions = all_perms
    db.session.commit()
    click.echo('[OK] R_ADMIN 角色已授予管理权限')


def _assign_user_permissions():
    """为 R_USER 角色授予基础权限（只看 Dashboard）"""
    user_role = Role.query.filter_by(code='R_USER').first()
    if not user_role:
        return

    dashboard_menu = Menu.query.filter_by(path='/dashboard').first()
    if dashboard_menu:
        user_role.menus = [dashboard_menu]
    user_role.permissions = []
    db.session.commit()
    click.echo('[OK] R_USER 角色已授予基础权限')





