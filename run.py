import os
from dotenv import load_dotenv
from app import create_app

# 加载环境变量
load_dotenv()

# 创建应用
app = create_app()

if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

    print(f"""
╔══════════════════════════════════════════════════╗
║     Flask CKiko-Admin API Server                ║
║     Running on: http://{host}:{port}                ║
║     Environment: {os.getenv('FLASK_ENV', 'development')}                     ║
║     Debug: {debug}                                ║
╚══════════════════════════════════════════════════╝
    """)

    app.run(host=host, port=port, debug=debug)
