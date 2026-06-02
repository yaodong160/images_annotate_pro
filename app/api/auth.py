from datetime import datetime
from flask import Blueprint, request, g
from app.extensions import db
from app.models.user import User, Menu
from app.utils.jwt_utils import generate_token, login_required
from app.utils.response import success, error

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/auth/login', methods=['POST'])
def login():
    """用户登录
    请求体: { "userName": "admin", "password": "123456" }
    响应: { code: 200, data: { token, refreshToken } }
    """
    data = request.get_json() or {}

    username = data.get('userName', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return error('用户名和密码不能为空')

    # 查询用户
    user = User.query.filter_by(username=username).first()
    if not user:
        return error('用户名或密码错误')

    if not user.status:
        return error('账号已被禁用，请联系管理员')

    if not user.check_password(password):
        return error('用户名或密码错误')

    # 更新最后登录时间
    user.last_login = datetime.now()
    db.session.commit()

    # 生成 token（取第一个角色编码，多角色用逗号拼接）
    role_codes = [r.code for r in user.roles]
    role_str = ','.join(role_codes) if role_codes else None
    token = generate_token(user.id, role_str)
    refresh_token = generate_token(user.id, role_str)  # refreshToken

    return success(
        data={
            'token': token,
            'refreshToken': refresh_token,
        },
        message='登录成功'
    )


@auth_bp.route('/auth/getUserInfo', methods=['GET'])
@login_required
def get_userinfo():
    """获取当前用户信息
    响应: { code: 200, data: { userId, userName, roles, buttons, menus } }
    """
    user = g.current_user
    role_codes = [r.code for r in user.roles]

    # 收集用户所有角色的菜单和按钮权限（去重）
    menu_set = set()
    perm_codes = set()
    for role in user.roles:
        if role.status:
            for menu in role.menus:
                if menu.status:
                    menu_set.add(menu.id)
            for perm in role.permissions:
                if perm.status:
                    perm_codes.add(perm.code)

    # 构建按钮权限列表
    buttons = [{'code': code} for code in sorted(perm_codes)]

    # 构建菜单列表（只返回用户有权访问的菜单，树形结构）
    menus = _build_user_menu_tree(menu_set)

    return success(data={
        'userId': str(user.id),
        'userName': user.username,
        'roles': role_codes,
        'buttons': buttons,
        'menus': menus,
    })


@auth_bp.route('/auth/refreshToken', methods=['POST'])
@login_required
def refresh_token():
    """刷新 Token
    请求体: { "refreshToken": "xxx" }
    响应: { code: 200, data: { token, refreshToken } }
    """
    user = g.current_user
    role_codes = [r.code for r in user.roles]
    role_str = ','.join(role_codes) if role_codes else None
    new_token = generate_token(user.id, role_str)
    new_refresh_token = generate_token(user.id, role_str)

    return success(data={
        'token': new_token,
        'refreshToken': new_refresh_token,
    }, message='刷新令牌成功')


# ==================== 以下为原有兼容端点 ====================

@auth_bp.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    """用户登出"""
    return success(message='登出成功')


@auth_bp.route('/auth/userinfo', methods=['GET'])
@login_required
def get_userinfo_legacy():
    """获取用户信息（旧版兼容）"""
    user = g.current_user
    user_info = user.to_dict(include_roles=True)
    role_codes = [r.code for r in user.roles]

    # 收集所有权限码
    perm_codes = set()
    menu_ids = set()
    for role in user.roles:
        if role.status:
            for perm in role.permissions:
                if perm.status:
                    perm_codes.add(perm.code)
            for menu in role.menus:
                if menu.status:
                    menu_ids.add(menu.id)

    return success(data={
        'user_info': user_info,
        'permissions': list(perm_codes),
        'menus': _build_user_menu_tree(menu_ids),
    })


@auth_bp.route('/auth/update-password', methods=['PUT'])
@login_required
def update_password():
    """修改密码
    请求体:
    {
        "old_password": "xxx",
        "new_password": "xxx"
    }
    """
    data = request.get_json() or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')

    if not old_password or not new_password:
        return error('旧密码和新密码不能为空')

    if len(new_password) < 6:
        return error('新密码长度不能少于6位')

    user = g.current_user
    if not user.check_password(old_password):
        return error('旧密码错误')

    user.set_password(new_password)
    db.session.commit()

    return success(message='密码修改成功')


def _build_user_menu_tree(allowed_menu_ids):
    """根据用户允许的菜单ID集合，构建菜单树"""
    if not allowed_menu_ids:
        return []

    # 获取所有允许的菜单
    allowed_menus = Menu.query.filter(
        Menu.id.in_(allowed_menu_ids),
        Menu.status == True
    ).order_by(Menu.sort_order).all()

    allowed_id_set = set(allowed_menu_ids)

    def _build_node(menu):
        node = {
            'id': menu.id,
            'parent_id': menu.parent_id,
            'name': menu.name,
            'path': menu.path or '',
            'component': menu.component or '',
            'icon': menu.icon or '',
            'hidden': menu.hidden,
        }
        children = Menu.query.filter_by(parent_id=menu.id, status=True).order_by(Menu.sort_order).all()
        # 只保留用户有权访问的子菜单
        filtered_children = [c for c in children if c.id in allowed_id_set]
        if filtered_children:
            node['children'] = [_build_node(c) for c in filtered_children]
        else:
            node['children'] = []
        return node

    # 只返回根菜单（parent_id 为 NULL）且用户有权访问的
    return [_build_node(m) for m in allowed_menus if m.parent_id is None]
