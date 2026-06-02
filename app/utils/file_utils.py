import os
from datetime import datetime
from flask import current_app
from PIL import Image as PILImage


# 允许上传的图片类型
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff', 'svg'}
ALLOWED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/gif',
    'image/bmp', 'image/webp', 'image/tiff', 'image/svg+xml'
}


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_project_upload_dir(project_id):
    """获取项目上传目录: uploads/{project_id}/"""
    upload_root = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    project_dir = os.path.join(upload_root, str(project_id))

    if not os.path.exists(project_dir):
        os.makedirs(project_dir)

    return project_dir


def generate_timestamp_filename(ext):
    """生成毫秒级时间戳文件名: YYYYMMDDHHmmSSfff.ext"""
    now = datetime.now()
    ts = now.strftime('%Y%m%d%H%M%S') + f'{now.microsecond // 1000:03d}'
    return f"{ts}.{ext.lower()}" if ext else ts


def save_upload_file(file, project_id):
    """保存上传文件到项目目录，返回文件信息字典"""
    original_filename = file.filename
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    unique_filename = generate_timestamp_filename(ext)
    upload_dir = get_project_upload_dir(project_id)

    file_path = os.path.join(upload_dir, unique_filename)
    file.save(file_path)

    # 获取图片尺寸，若竖长图（高/宽 > 1.3）则旋转90度
    width, height = None, None
    try:
        with PILImage.open(file_path) as img:
            width, height = img.size
            if width and height and height / width > 1.3:
                # EXIF 中可能已包含旋转信息，先按 EXIF 修正方向再判断
                # 直接旋转图片 90 度（逆时针），使宽 > 高
                rotated = img.rotate(90, expand=True)
                # 保留 EXIF（如果有的话），去掉方向标记避免二次旋转
                exif = img.info.get('exif')
                save_kwargs = {}
                if exif:
                    save_kwargs['exif'] = exif
                rotated.save(file_path, quality=95, **save_kwargs)
                width, height = rotated.size
    except Exception:
        pass

    file_size = os.path.getsize(file_path)

    # 构建访问URL
    file_url = f"/uploads/{project_id}/{unique_filename}"

    return {
        'filename': unique_filename,
        'original_filename': original_filename,
        'file_path': file_path,
        'file_url': file_url,
        'file_size': file_size,
        'mime_type': file.content_type,
        'width': width,
        'height': height,
        'ext': ext,
    }


def create_thumbnail(file_path, project_id):
    """生成缩略图，保存在同目录下"""
    try:
        upload_dir = get_project_upload_dir(project_id)
        base_name = os.path.basename(file_path)
        thumb_name = f"thumb_{base_name}"
        thumb_path = os.path.join(upload_dir, thumb_name)

        with PILImage.open(file_path) as img:
            img.thumbnail((200, 200), PILImage.Resampling.LANCZOS)
            img.save(thumb_path, quality=85)

        return f"/uploads/{project_id}/{thumb_name}"
    except Exception:
        return None


def delete_upload_file(file_path):
    """删除上传文件及缩略图"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        # 尝试删除缩略图
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        thumb_path = os.path.join(dir_name, f"thumb_{base_name}")
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        return True
    except Exception:
        return False
