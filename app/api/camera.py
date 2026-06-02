"""
摄像头 API：抓图、MJPEG 预览、云台控制、分辨率管理
"""
import os
import json
from flask import Blueprint, request, g, Response, current_app
from app.extensions import db
from app.models.annotation import AnnotationProject, AnnotatedImage
from app.services.hikvision import get_project_camera
from app.utils.response import success, error
from app.utils.jwt_utils import login_required
from app.utils.file_utils import get_project_upload_dir, generate_timestamp_filename, create_thumbnail

camera_bp = Blueprint('camera', __name__, url_prefix='/camera')


def _get_project(project_id):
    """获取项目并校验摄像头配置"""
    project = AnnotationProject.query.get(project_id)
    if not project:
        return None, error('项目不存在', code=404)
    return project, None


# ==================== 连通性检查 ====================

@camera_bp.route('/check/<int:project_id>', methods=['GET'])
@login_required
def check_connection(project_id):
    """检查摄像头连通性"""
    project, err = _get_project(project_id)
    if err:
        return err

    cam, cam_err = get_project_camera(project)
    if cam_err:
        return error(cam_err)

    ok = cam._check_connection()
    if ok:
        return success(data={'connected': True}, message='摄像头连接正常')
    else:
        return error('无法连接摄像头，请检查地址和网络', code=503)


# ==================== 截取单帧 ====================

@camera_bp.route('/capture/<int:project_id>', methods=['POST'])
@login_required
def capture_frame(project_id):
    """截取摄像头当前帧并保存到项目图片库"""
    project, err = _get_project(project_id)
    if err:
        return err

    cam, cam_err = get_project_camera(project)
    if cam_err:
        return error(cam_err)

    # 抓取图片
    img_bytes, cap_err = cam.capture()
    if img_bytes is None:
        return error(f'抓图失败: {cap_err}')

    # 保存文件
    upload_dir = get_project_upload_dir(project_id)
    filename = generate_timestamp_filename('jpeg')
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, 'wb') as f:
        f.write(img_bytes)

    file_size = os.path.getsize(file_path)
    file_url = f"/uploads/{project_id}/{filename}"

    # 生成缩略图
    thumbnail_url = create_thumbnail(file_path, project_id)

    # 尝试获取图片尺寸
    from PIL import Image as PILImage
    width, height = None, None
    try:
        with PILImage.open(file_path) as img:
            width, height = img.size
    except Exception:
        pass

    # 写入数据库
    image = AnnotatedImage(
        filename=filename,
        file_path=file_path,
        file_url=file_url,
        file_size=file_size,
        mime_type='image/jpeg',
        width=width,
        height=height,
        thumbnail_url=thumbnail_url,
        project_id=project_id,
        upload_by=g.current_user_id,
    )
    db.session.add(image)
    db.session.commit()

    return success(data={
        'id': image.id,
        'filename': filename,
        'file_url': file_url,
        'thumbnail_url': thumbnail_url,
        'width': width,
        'height': height,
        'file_size': file_size,
    }, message='截取成功')


# ==================== MJPEG 实时预览 ====================

@camera_bp.route('/preview/<int:project_id>', methods=['GET'])
@login_required
def preview_mjpeg(project_id):
    """MJPEG 实时预览流（multipart/x-mixed-replace）"""
    project, err = _get_project(project_id)
    if err:
        return err

    cam, cam_err = get_project_camera(project)
    if cam_err:
        return error(cam_err)

    def generate():
        """生成 MJPEG 流响应"""
        boundary = '--hikvision-mjpeg'
        yield f'--{boundary}\r\n'.encode()

        for frame_data, frame_boundary in cam.mjpeg_stream_generator():
            if frame_data is None:
                # 错误信息
                err_msg = frame_boundary or 'Unknown error'
                yield f'Content-Type: text/plain\r\n\r\n{err_msg}\r\n'.encode()
                yield f'--{boundary}--\r\n'.encode()
                return

            yield f'Content-Type: image/jpeg\r\nContent-Length: {len(frame_data)}\r\n\r\n'.encode()
            yield frame_data
            yield f'\r\n--{boundary}\r\n'.encode()

    return Response(
        generate(),
        mimetype=f'multipart/x-mixed-replace; boundary={boundary}',
        headers={
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Connection': 'close',
        }
    )


# ==================== 云台控制 ====================

@camera_bp.route('/ptz/<int:project_id>', methods=['POST'])
@login_required
def ptz_control(project_id):
    """云台控制
    请求体: { "action": "up|down|left|right|zoomIn|zoomOut", "speed": 5, "duration": 500 }
    """
    project, err = _get_project(project_id)
    if err:
        return err

    cam, cam_err = get_project_camera(project)
    if cam_err:
        return error(cam_err)

    data = request.get_json() or {}
    action = data.get('action', '')
    speed = data.get('speed', 5)
    duration = data.get('duration', 500)

    if not action:
        return error('缺少控制动作(action)')

    ok, msg = cam.ptz_action(action, speed=speed, duration=duration)
    if ok:
        return success(message='控制成功')
    return error(f'控制失败: {msg}')


# ==================== 分辨率管理 ====================

@camera_bp.route('/resolutions/<int:project_id>', methods=['GET'])
@login_required
def get_resolutions(project_id):
    """获取摄像头支持的可用分辨率列表"""
    project, err = _get_project(project_id)
    if err:
        return err

    cam, cam_err = get_project_camera(project)
    if cam_err:
        return error(cam_err)

    resolutions, res_err = cam.get_resolutions()
    if res_err:
        return error(res_err)

    return success(data=resolutions)


@camera_bp.route('/resolution/<int:project_id>', methods=['PUT'])
@login_required
def set_resolution(project_id):
    """设置摄像头分辨率
    请求体: { "width": 1920, "height": 1080 }
    """
    project, err = _get_project(project_id)
    if err:
        return err

    cam, cam_err = get_project_camera(project)
    if cam_err:
        return error(cam_err)

    data = request.get_json() or {}
    width = data.get('width')
    height = data.get('height')

    if not width or not height:
        return error('缺少分辨率参数')

    ok, msg = cam.set_resolution(width, height)
    if ok:
        return success(message='分辨率设置成功，可能需要重启预览')
    return error(f'设置失败: {msg}')
