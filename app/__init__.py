import os
from flask import Flask, send_from_directory
from app.config import get_config
from app.extensions import init_extensions
from app.api import register_blueprints


def create_app(config_name=None):
    """应用工厂：创建并配置 Flask 应用"""
    app = Flask(__name__)

    # 加载配置
    if config_name is None:
        config = get_config()
    else:
        from app.config import config_map
        config = config_map.get(config_name, config_map['default'])

    app.config.from_object(config)

    # 确保上传目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # 初始化扩展
    init_extensions(app)

    # 注册蓝图
    register_blueprints(app)

    # 注册 CLI 命令
    from app.commands import register_commands
    register_commands(app)

    # 注册全局错误处理
    register_error_handlers(app)

    # 健康检查接口
    @app.route('/')
    def index():
        return {
            'code': 200,
            'message': 'Flask CKiko-Admin API Server is running',
            'version': '1.0.0',
        }

    @app.route('/health')
    def health():
        return {'status': 'ok'}

    # 静态文件服务（全局兜底，不依赖蓝图）
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    return app


def register_error_handlers(app):
    """注册全局错误处理"""

    @app.errorhandler(400)
    def bad_request(e):
        return {
            'code': 400,
            'message': '请求参数错误',
            'data': None,
        }, 400

    @app.errorhandler(404)
    def not_found(e):
        return {
            'code': 404,
            'message': '请求的资源不存在',
            'data': None,
        }, 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return {
            'code': 405,
            'message': '请求方法不允许',
            'data': None,
        }, 405

    @app.errorhandler(500)
    def internal_error(e):
        return {
            'code': 500,
            'message': '服务器内部错误',
            'data': None,
        }, 500
