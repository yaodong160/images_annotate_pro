from flask import Blueprint, request, g
from app.extensions import db
from app.models.user import User, Role, Menu, Permission
from app.utils.jwt_utils import login_required, admin_required
from app.utils.response import success, error

user_bp = Blueprint('user', __name__)


# ==================== 前端兼容的 System 用户管理接口 ====================

@user_bp.route('/system/user/list', methods=['GET'])
@login_required
def system_user_list():
    """获取用户列表（前端分页格式）
    Query 参数: current, size, userName, nickName, userEmail, status
    """
    current = request.args.get('current', 1, type=int)
    size = request.args.get('size', 10, type=int)
    user_name = request.args.get('userName', '')
    nick_name = request.args.get('nickName', '')
    user_email = request.args.get('userEmail', '')
    status = request.args.get('status', '')

    query = User.query

    if user_name:
        query = query.filter(User.username.like(f'%{user_name}%'))
    if nick_name:
        query = query.filter(User.nickname.like(f'%{nick_name}%'))
    if user_email:
        query = query.filter(User.email.like(f'%{user_email}%'))
    if status:
        query = query.filter_by(status=(status == '1'))

    query = query.order_by(User.id.desc())

    pagination = query.paginate(page=current, per_page=size, error_out=False)

    records = []
    for u in pagination.items:
        records.append({
            'id': u.id,
            'userName': u.username,
            'nickName': u.nickname,
            'userEmail': u.email or '',
            'userPhone': u.phone or '',
            'userGender': u.gender or None,
            'userRoles': [r.code for r in u.roles],
            'status': '1' if u.status else '2',
            'createBy': '',
            'createTime': u.created_at.strftime('%Y-%m-%d %H:%M:%S') if u.created_at else None,
            'updateBy': '',
            'updateTime': u.updated_at.strftime('%Y-%m-%d %H:%M:%S') if u.updated_at else None,
        })

    return success(data={
        'records': records,
        'current': pagination.page,
        'size': pagination.per_page,
        'total': pagination.total,
    })


@user_bp.route('/system/user/add', methods=['POST'])
@login_required
def system_user_add():
    """新增用户（前端格式）
    请求体: { userName, nickName, userEmail, userPhone, userGender, userRoles }
    """
    data = request.get_json() or {}
    username = data.get('userName', '').strip()
    password = data.get('password', '123456')
    nickname = data.get('nickName', '').strip()
    email = data.get('userEmail', '').strip()
    phone = data.get('userPhone', '').strip()
    gender = data.get('userGender', None)
    role_codes = data.get('userRoles', [])

    if not username or len(username) < 3:
        return error('用户名至少3个字符')
    if User.query.filter_by(username=username).first():
        return error('用户名已存在')
    if email and User.query.filter_by(email=email).first():
        return error('邮箱已被使用')

    # 查找角色（多角色）
    roles = []
    if role_codes:
        roles = Role.query.filter(Role.code.in_(role_codes), Role.status == True).all()

    user = User(
        username=username,
        nickname=nickname or username,
        email=email or None,
        phone=phone or None,
        gender=gender,
        status=True,
    )
    user.roles = roles
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return success(data={
        'id': user.id,
        'userName': user.username,
        'nickName': user.nickname,
        'userEmail': user.email or '',
        'userPhone': user.phone or '',
        'userGender': user.gender or None,
        'userRoles': [r.code for r in user.roles],
        'status': '1',
        'createBy': '',
        'createTime': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
        'updateBy': '',
        'updateTime': user.updated_at.strftime('%Y-%m-%d %H:%M:%S') if user.updated_at else None,
    }, message='用户创建成功')


@user_bp.route('/system/user/edit/<int:user_id>', methods=['PUT'])
@login_required
def system_user_edit(user_id):
    """编辑用户（前端格式）"""
    user = User.query.get(user_id)
    if not user:
        return error('用户不存在', code=404)

    data = request.get_json() or {}

    if 'userName' in data:
        username = data['userName'].strip()
        if username != user.username and User.query.filter_by(username=username).first():
            return error('用户名已存在')
        user.username = username
    if 'nickName' in data:
        user.nickname = data['nickName']
    if 'userEmail' in data:
        user.email = data['userEmail'] or None
    if 'userPhone' in data:
        user.phone = data['userPhone'] or None
    if 'userGender' in data:
        user.gender = data['userGender']
    if 'status' in data:
        user.status = (data['status'] == '1')
    if 'userRoles' in data:
        roles = Role.query.filter(Role.code.in_(data['userRoles']), Role.status == True).all()
        user.roles = roles
    if 'password' in data and data['password']:
        user.set_password(data['password'])

    db.session.commit()

    return success(data={
        'id': user.id,
        'userName': user.username,
        'nickName': user.nickname,
        'userEmail': user.email or '',
        'userPhone': user.phone or '',
        'userGender': user.gender or None,
        'userRoles': [r.code for r in user.roles],
        'status': '1' if user.status else '2',
        'createBy': '',
        'createTime': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
        'updateBy': '',
        'updateTime': user.updated_at.strftime('%Y-%m-%d %H:%M:%S') if user.updated_at else None,
    }, message='用户更新成功')


@user_bp.route('/system/user/delete/<int:user_id>', methods=['DELETE'])
@login_required
def system_user_delete(user_id):
    """删除用户（前端格式）"""
    user = User.query.get(user_id)
    if not user:
        return error('用户不存在', code=404)
    if user.id == g.current_user_id:
        return error('不能删除自己')

    user.status = False
    db.session.commit()
    return success(message='用户已禁用')


@user_bp.route('/system/user/batchDelete', methods=['DELETE'])
@login_required
def system_user_batch_delete():
    """批量删除用户（前端格式）"""
    data = request.get_json() or {}
    ids = data.get('ids', [])
    if not ids:
        return error('请选择要删除的用户')
    if g.current_user_id in ids:
        return error('不能删除自己')

    User.query.filter(User.id.in_(ids)).update(
        {User.status: False}, synchronize_session=False
    )
    db.session.commit()
    return success(message=f'已禁用 {len(ids)} 个用户')


@user_bp.route('/system/user/detail/<int:user_id>', methods=['GET'])
@login_required
def system_user_detail(user_id):
    """获取用户详情（前端格式）"""
    user = User.query.get(user_id)
    if not user:
        return error('用户不存在', code=404)

    role_codes = [r.code for r in user.roles]
    return success(data={
        'id': user.id,
        'userName': user.username,
        'nickName': user.nickname,
        'userEmail': user.email or '',
        'userPhone': user.phone or '',
        'userGender': user.gender or None,
        'userRoles': role_codes,
        'status': '1' if user.status else '2',
        'createBy': '',
        'createTime': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
        'updateBy': '',
        'updateTime': user.updated_at.strftime('%Y-%m-%d %H:%M:%S') if user.updated_at else None,
    })


# ==================== 前端兼容的 System 角色管理接口 ====================

@user_bp.route('/system/role/list', methods=['GET'])
@login_required
def system_role_list():
    """获取角色列表（前端分页格式）"""
    current = request.args.get('current', 1, type=int)
    size = request.args.get('size', 10, type=int)
    role_name = request.args.get('roleName', '')
    role_code = request.args.get('roleCode', '')
    status = request.args.get('status', '')

    query = Role.query

    if role_name:
        query = query.filter(Role.name.like(f'%{role_name}%'))
    if role_code:
        query = query.filter(Role.code.like(f'%{role_code}%'))
    if status:
        query = query.filter_by(status=(status == '1'))

    query = query.order_by(Role.id.desc())
    pagination = query.paginate(page=current, per_page=size, error_out=False)

    records = []
    for r in pagination.items:
        records.append({
            'id': r.id,
            'roleCode': r.code,
            'roleName': r.name,
            'roleDesc': r.description or '',
            'status': '1' if r.status else '2',
            'createBy': '',
            'createTime': r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else None,
            'updateBy': '',
            'updateTime': r.updated_at.strftime('%Y-%m-%d %H:%M:%S') if r.updated_at else None,
        })

    return success(data={
        'records': records,
        'current': pagination.page,
        'size': pagination.per_page,
        'total': pagination.total,
    })


@user_bp.route('/system/role/all', methods=['GET'])
@login_required
def system_role_all():
    """获取所有角色（下拉选择用）"""
    roles = Role.query.filter_by(status=True).all()
    return success(data=[{
        'id': r.id,
        'roleCode': r.code,
        'roleName': r.name,
    } for r in roles])


@user_bp.route('/system/role/add', methods=['POST'])
@login_required
def system_role_add():
    """新增角色"""
    data = request.get_json() or {}
    role_name = data.get('roleName', '').strip()
    role_code = data.get('roleCode', '').strip()
    role_desc = data.get('roleDesc', '').strip()

    if not role_name or not role_code:
        return error('角色名称和编码不能为空')
    if Role.query.filter_by(code=role_code).first():
        return error('角色编码已存在')

    role = Role(name=role_name, code=role_code, description=role_desc)
    db.session.add(role)
    db.session.commit()

    return success(data={
        'id': role.id,
        'roleCode': role.code,
        'roleName': role.name,
        'roleDesc': role.description or '',
        'status': '1',
        'createBy': '',
        'createTime': role.created_at.strftime('%Y-%m-%d %H:%M:%S') if role.created_at else None,
        'updateBy': '',
        'updateTime': role.updated_at.strftime('%Y-%m-%d %H:%M:%S') if role.updated_at else None,
    }, message='角色创建成功')


@user_bp.route('/system/role/edit/<int:role_id>', methods=['PUT'])
@login_required
def system_role_edit(role_id):
    """编辑角色"""
    role = Role.query.get(role_id)
    if not role:
        return error('角色不存在', code=404)

    data = request.get_json() or {}
    if 'roleName' in data:
        role.name = data['roleName']
    if 'roleCode' in data:
        if data['roleCode'] != role.code and Role.query.filter_by(code=data['roleCode']).first():
            return error('角色编码已存在')
        role.code = data['roleCode']
    if 'roleDesc' in data:
        role.description = data['roleDesc']
    if 'status' in data:
        role.status = (data['status'] == '1')

    db.session.commit()

    return success(data={
        'id': role.id,
        'roleCode': role.code,
        'roleName': role.name,
        'roleDesc': role.description or '',
        'status': '1' if role.status else '2',
        'createBy': '',
        'createTime': role.created_at.strftime('%Y-%m-%d %H:%M:%S') if role.created_at else None,
        'updateBy': '',
        'updateTime': role.updated_at.strftime('%Y-%m-%d %H:%M:%S') if role.updated_at else None,
    }, message='角色更新成功')


@user_bp.route('/system/role/delete/<int:role_id>', methods=['DELETE'])
@login_required
def system_role_delete(role_id):
    """删除角色"""
    role = Role.query.get(role_id)
    if not role:
        return error('角色不存在', code=404)

    # 检查是否有用户使用此角色
    if User.query.filter_by(role_id=role_id, status=True).first():
        return error('该角色下存在用户，请先转移用户')

    role.status = False
    db.session.commit()
    return success(message='角色已禁用')


# ==================== 原有兼容接口 ====================

@user_bp.route('/users', methods=['GET'])
@login_required
def get_user_list():
    """获取用户列表（分页 + 搜索）
    Query 参数:
        page: 页码（默认1）
        page_size: 每页条数（默认10）
        username: 用户名搜索
        status: 状态筛选
    """
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 10, type=int)
    username = request.args.get('username', '')
    status = request.args.get('status', type=int)

    query = User.query

    if username:
        query = query.filter(User.username.like(f'%{username}%'))
    if status is not None:
        query = query.filter_by(status=bool(status))

    query = query.order_by(User.id.desc())

    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return success(data={
        'list': [u.to_dict(include_role=True) for u in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'page_size': pagination.per_page,
        'pages': pagination.pages,
    })


@user_bp.route('/users/<int:user_id>', methods=['GET'])
@login_required
def get_user_detail(user_id):
    """获取用户详情"""
    user = User.query.get(user_id)
    if not user:
        return error('用户不存在', code=404)
    return success(data=user.to_dict(include_role=True))


@user_bp.route('/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    """新增用户
    请求体:
    {
        "username": "test",
        "password": "123456",
        "nickname": "测试用户",
        "email": "test@example.com",
        "phone": "13800138000",
        "role_id": 2
    }
    """
    data = request.get_json() or {}

    username = data.get('username', '').strip()
    password = data.get('password', '')
    nickname = data.get('nickname', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    role_id = data.get('role_id')

    # 参数校验
    if not username or len(username) < 3:
        return error('用户名至少3个字符')
    if not password or len(password) < 6:
        return error('密码至少6位')

    # 检查用户名是否已存在
    if User.query.filter_by(username=username).first():
        return error('用户名已存在')

    if email and User.query.filter_by(email=email).first():
        return error('邮箱已被使用')

    # 创建用户
    user = User(
        username=username,
        nickname=nickname or username,
        email=email or None,
        phone=phone or None,
        role_id=role_id,
        status=True,
    )
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    return success(data=user.to_dict(include_role=True), message='用户创建成功')


@user_bp.route('/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    """更新用户信息
    请求体:
    {
        "nickname": "新昵称",
        "email": "new@example.com",
        "phone": "13900139000",
        "status": true,
        "role_id": 2
    }
    """
    user = User.query.get(user_id)
    if not user:
        return error('用户不存在', code=404)

    data = request.get_json() or {}

    # 更新字段
    if 'nickname' in data:
        user.nickname = data['nickname']
    if 'email' in data:
        email = data['email'].strip()
        if email and email != user.email:
            if User.query.filter_by(email=email).first():
                return error('邮箱已被使用')
        user.email = email or None
    if 'phone' in data:
        user.phone = data['phone'] or None
    if 'status' in data:
        user.status = bool(data['status'])
    if 'role_id' in data:
        user.role_id = data['role_id']
    if 'password' in data and data['password']:
        if len(data['password']) < 6:
            return error('密码至少6位')
        user.set_password(data['password'])

    db.session.commit()

    return success(data=user.to_dict(include_role=True), message='用户更新成功')


@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """删除用户（软删除：禁用状态）"""
    user = User.query.get(user_id)
    if not user:
        return error('用户不存在', code=404)

    # 不能删除自己
    if user.id == g.current_user_id:
        return error('不能删除自己')

    # 软删除：设置为禁用
    user.status = False
    db.session.commit()

    return success(message='用户已禁用')


@user_bp.route('/users/batch-delete', methods=['POST'])
@login_required
@admin_required
def batch_delete_users():
    """批量删除用户
    请求体:
    {
        "ids": [1, 2, 3]
    }
    """
    data = request.get_json() or {}
    ids = data.get('ids', [])

    if not ids:
        return error('请选择要删除的用户')

    if g.current_user_id in ids:
        return error('不能删除自己')

    User.query.filter(
        User.id.in_(ids),
        User.id != g.current_user_id
    ).update(
        {User.status: False},
        synchronize_session=False
    )
    db.session.commit()

    return success(message=f'已禁用 {len(ids)} 个用户')


# ==================== 角色管理 ====================

@user_bp.route('/roles', methods=['GET'])
@login_required
def get_role_list():
    """获取所有角色"""
    roles = Role.query.filter_by(status=True).all()
    return success(data=[r.to_dict() for r in roles])


@user_bp.route('/roles', methods=['POST'])
@login_required
@admin_required
def create_role():
    """新增角色"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    code = data.get('code', '').strip()
    description = data.get('description', '').strip()

    if not name or not code:
        return error('角色名称和编码不能为空')

    if Role.query.filter_by(code=code).first():
        return error('角色编码已存在')

    role = Role(name=name, code=code, description=description)
    db.session.add(role)
    db.session.commit()

    return success(data=role.to_dict(), message='角色创建成功')


# ==================== 角色菜单权限接口 ====================

@user_bp.route('/system/role/menu/<int:role_id>', methods=['GET'])
@login_required
def get_role_menus(role_id):
    """获取角色的菜单权限
    返回: { allMenus: [...], checkedKeys: [...] }
    """
    role = Role.query.get(role_id)
    if not role:
        return error('角色不存在', code=404)

    # 获取所有菜单（树形结构）
    all_menus = _build_menu_tree()

    # 获取该角色已分配的菜单ID列表
    checked_ids = [m.id for m in role.menus]

    return success(data={
        'allMenus': all_menus,
        'checkedKeys': checked_ids,
    })


@user_bp.route('/system/role/menu/<int:role_id>', methods=['PUT'])
@login_required
def save_role_menus(role_id):
    """保存角色的菜单权限
    请求体: { menuIds: [1, 2, 3] }
    """
    role = Role.query.get(role_id)
    if not role:
        return error('角色不存在', code=404)

    data = request.get_json() or {}
    menu_ids = data.get('menuIds', [])

    # 更新角色的菜单
    menus = Menu.query.filter(Menu.id.in_(menu_ids), Menu.status == True).all()
    role.menus = menus
    db.session.commit()

    return success(message='菜单权限保存成功')


# ==================== 角色按钮权限接口 ====================

@user_bp.route('/system/role/permission/<int:role_id>', methods=['GET'])
@login_required
def get_role_permissions(role_id):
    """获取角色的按钮权限
    返回: { allPermissions: [...], checkedKeys: [...] }
    """
    role = Role.query.get(role_id)
    if not role:
        return error('角色不存在', code=404)

    # 获取所有按钮权限（按菜单分组）
    all_permissions = _build_permission_tree()

    # 获取该角色已分配的权限ID列表
    checked_ids = [p.id for p in role.permissions]

    return success(data={
        'allPermissions': all_permissions,
        'checkedKeys': checked_ids,
    })


@user_bp.route('/system/role/permission/<int:role_id>', methods=['PUT'])
@login_required
def save_role_permissions(role_id):
    """保存角色的按钮权限
    请求体: { permissionIds: [1, 2, 3] }
    """
    role = Role.query.get(role_id)
    if not role:
        return error('角色不存在', code=404)

    data = request.get_json() or {}
    perm_ids = data.get('permissionIds', [])

    # 更新角色的权限
    permissions = Permission.query.filter(Permission.id.in_(perm_ids), Permission.status == True).all()
    role.permissions = permissions
    db.session.commit()

    return success(message='按钮权限保存成功')


def _build_menu_tree():
    """构建菜单树（供前端使用）"""
    root_menus = Menu.query.filter(Menu.parent_id.is_(None), Menu.status == True).order_by(Menu.sort_order).all()

    def _build_node(menu):
        node = {
            'key': menu.id,
            'title': menu.name,
        }
        children = Menu.query.filter_by(parent_id=menu.id, status=True).order_by(Menu.sort_order).all()
        if children:
            node['children'] = [_build_node(c) for c in children]
        return node

    return [_build_node(m) for m in root_menus]


def _build_permission_tree():
    """构建权限树（按菜单分组，供前端使用）"""
    menus = Menu.query.filter_by(status=True).order_by(Menu.sort_order).all()
    result = []
    for menu in menus:
        perms = Permission.query.filter_by(menu_id=menu.id, status=True).order_by(Permission.sort_order).all()
        if perms:
            node = {
                'key': f'menu_{menu.id}',
                'title': menu.name,
                'children': [
                    {
                        'key': p.id,
                        'title': p.name,
                        'code': p.code,
                    }
                    for p in perms
                ],
            }
            result.append(node)
    return result
