from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask import has_request_context, g
from sqlalchemy import event

# 创建扩展实例（不绑定 app）
db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
cors = CORS()


def _auto_fill_audit_fields(_mapper, _connection, target):
    """INSERT 前自动填充 created_by, updated_by"""
    if has_request_context() and hasattr(g, 'current_user_id'):
        if hasattr(target, 'created_by') and target.created_by is None:
            target.created_by = g.current_user_id
        if hasattr(target, 'updated_by') and target.updated_by is None:
            target.updated_by = g.current_user_id


def _auto_update_audit_fields(_mapper, _connection, target):
    """UPDATE 前自动填充 updated_by"""
    if has_request_context() and hasattr(g, 'current_user_id'):
        if hasattr(target, 'updated_by'):
            target.updated_by = g.current_user_id


def init_extensions(app):
    """初始化所有 Flask 扩展"""
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    cors.init_app(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "x-request-id"],
            "expose_headers": ["Content-Disposition"],
        }
    })

    # 注册 SQLAlchemy 事件：自动填充创建人/更新人
    event.listen(db.Model, 'before_insert', _auto_fill_audit_fields)
    event.listen(db.Model, 'before_update', _auto_update_audit_fields)
