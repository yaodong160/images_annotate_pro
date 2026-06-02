from datetime import datetime
from app.extensions import db, bcrypt

# 用户-角色多对多关联表
user_roles = db.Table(
    'user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
)

# 角色-菜单多对多关联表
role_menus = db.Table(
    'role_menus',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('menu_id', db.Integer, db.ForeignKey('menus.id'), primary_key=True),
)

# 角色-按钮权限多对多关联表
role_permissions = db.Table(
    'role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True),
)


class Role(db.Model):
    """角色表"""
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), unique=True, nullable=False, comment='角色名称')
    code = db.Column(db.String(50), unique=True, nullable=False, comment='角色编码')
    description = db.Column(db.String(200), comment='角色描述')
    status = db.Column(db.Boolean, default=True, comment='状态: 1-启用, 0-禁用')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建人')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='更新人')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联用户（多对多）
    users = db.relationship('User', secondary=user_roles, back_populates='roles')
    # 关联菜单（多对多）
    menus = db.relationship('Menu', secondary=role_menus, back_populates='roles')
    # 关联按钮权限（多对多）
    permissions = db.relationship('Permission', secondary=role_permissions, back_populates='roles')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'status': self.status,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }


class Menu(db.Model):
    """菜单表（树形结构）"""
    __tablename__ = 'menus'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('menus.id'), nullable=True, comment='父菜单ID，NULL为根菜单')
    name = db.Column(db.String(50), nullable=False, comment='菜单名称')
    path = db.Column(db.String(200), comment='前端路由路径')
    component = db.Column(db.String(200), comment='前端组件路径')
    icon = db.Column(db.String(50), comment='图标')
    sort_order = db.Column(db.Integer, default=0, comment='排序号')
    hidden = db.Column(db.Boolean, default=False, comment='是否隐藏')
    status = db.Column(db.Boolean, default=True, comment='状态')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建人')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='更新人')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 自引用关系（子菜单）
    children = db.relationship('Menu', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    # 关联角色
    roles = db.relationship('Role', secondary=role_menus, back_populates='menus')

    def to_dict(self, include_children=False):
        data = {
            'id': self.id,
            'parent_id': self.parent_id,
            'name': self.name,
            'path': self.path or '',
            'component': self.component or '',
            'icon': self.icon or '',
            'sort_order': self.sort_order,
            'hidden': self.hidden,
            'status': self.status,
        }
        if include_children:
            data['children'] = [c.to_dict() for c in self.children.filter_by(status=True).order_by(Menu.sort_order).all()]
        return data


class Permission(db.Model):
    """按钮权限表"""
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menus.id'), nullable=False, comment='所属菜单ID')
    name = db.Column(db.String(50), nullable=False, comment='权限名称')
    code = db.Column(db.String(100), unique=True, nullable=False, comment='权限编码，如 system:user:add')
    description = db.Column(db.String(200), comment='权限描述')
    sort_order = db.Column(db.Integer, default=0, comment='排序号')
    status = db.Column(db.Boolean, default=True, comment='状态')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建人')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='更新人')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联菜单
    menu = db.relationship('Menu', backref='permissions')
    # 关联角色
    roles = db.relationship('Role', secondary=role_permissions, back_populates='permissions')

    def to_dict(self):
        return {
            'id': self.id,
            'menu_id': self.menu_id,
            'name': self.name,
            'code': self.code,
            'description': self.description or '',
            'sort_order': self.sort_order,
            'status': self.status,
        }


class User(db.Model):
    """用户表"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, comment='用户名')
    password_hash = db.Column(db.String(255), nullable=False, comment='密码哈希')
    nickname = db.Column(db.String(80), comment='昵称')
    email = db.Column(db.String(120), unique=True, comment='邮箱')
    phone = db.Column(db.String(20), comment='手机号')
    gender = db.Column(db.String(1), comment='性别: 1-男, 2-女')
    avatar = db.Column(db.String(500), comment='头像URL')
    status = db.Column(db.Boolean, default=True, comment='状态: 1-启用, 0-禁用')
    last_login = db.Column(db.DateTime, comment='最后登录时间')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建人')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='更新人')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联角色（多对多）
    roles = db.relationship('Role', secondary=user_roles, back_populates='users')

    def set_password(self, password):
        """设置密码"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        """校验密码"""
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self, include_roles=False):
        """序列化为字典"""
        data = {
            'id': self.id,
            'username': self.username,
            'nickname': self.nickname,
            'email': self.email,
            'phone': self.phone,
            'avatar': self.avatar,
            'status': self.status,
            'roles': [r.code for r in self.roles] if self.roles else [],
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M:%S') if self.last_login else None,
            'created_by': self.created_by,
            'updated_by': self.updated_by,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }
        if include_roles and self.roles:
            data['role_list'] = [r.to_dict() for r in self.roles]
        return data
