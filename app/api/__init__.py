from flask import Blueprint

# 创建 API 蓝图（所有 API 统一前缀 /api）
api_bp = Blueprint('api', __name__, url_prefix='/api')


def register_blueprints(app):
    """注册所有蓝图"""
    from app.api.auth import auth_bp
    from app.api.user import user_bp
    from app.api.upload import upload_bp
    from app.api.image import image_bp
    from app.api.annotation import annotation_bp
    from app.api.project import project_bp
    from app.api.camera import camera_bp

    api_bp.register_blueprint(auth_bp)
    api_bp.register_blueprint(user_bp)
    api_bp.register_blueprint(upload_bp)
    api_bp.register_blueprint(image_bp)
    api_bp.register_blueprint(annotation_bp)
    api_bp.register_blueprint(project_bp)
    api_bp.register_blueprint(camera_bp)

    app.register_blueprint(api_bp)
