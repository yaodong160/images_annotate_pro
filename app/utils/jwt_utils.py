import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app, g
from app.models.user import User


def generate_token(user_id, role_code=None):
    """生成 JWT Token"""
    payload = {
        'user_id': user_id,
        'role_code': role_code,
        'iat': datetime.utcnow(),
        'exp': datetime.utcnow() + timedelta(
            hours=current_app.config['JWT_EXPIRATION_HOURS']
        ),
    }
    return jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )


def decode_token(token):
    """解码 JWT Token"""
    try:
        payload = jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # 从 Authorization header 获取 token
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if not token:
            return jsonify({
                'code': 401,
                'message': '请先登录',
                'data': None
            }), 401

        # 解码 token
        payload = decode_token(token)
        if not payload:
            return jsonify({
                'code': 401,
                'message': 'Token 已过期或无效，请重新登录',
                'data': None
            }), 401

        # 查询用户
        user = User.query.get(payload.get('user_id'))
        if not user or not user.status:
            return jsonify({
                'code': 403,
                'message': '用户不存在或已被禁用',
                'data': None
            }), 403

        # 将当前用户信息存入 g 对象
        g.current_user = user
        g.current_user_id = user.id
        g.current_role_code = payload.get('role_code')

        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """管理员权限验证装饰器（需配合 login_required 使用）"""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        role_codes = (g.current_role_code or '').split(',')
        if not any(rc in ('R_ADMIN', 'R_SUPER') for rc in role_codes):
            return jsonify({
                'code': 403,
                'message': '权限不足，需要管理员权限',
                'data': None
            }), 403
        return f(*args, **kwargs)
    return decorated
