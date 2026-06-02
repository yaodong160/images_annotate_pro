import os
from flask import Blueprint, request, send_from_directory, current_app, g
from app.extensions import db
from app.models.annotation import AnnotatedImage, AnnotationProject
from app.utils.jwt_utils import login_required
from app.utils.response import success, error
from app.utils.file_utils import (
    allowed_file, save_upload_file, create_thumbnail,
    delete_upload_file, get_project_upload_dir
)

upload_bp = Blueprint('upload', __name__)


@upload_bp.route('/upload/image', methods=['POST'])
@login_required
def upload_image():
    """上传图片到项目（支持批量）
    表单字段:
        files: 图片文件（可多个）
        project_id: 项目ID（必填）
    """
    project_id = request.form.get('project_id', type=int)
    if not project_id:
        return error('请指定项目ID')

    project = AnnotationProject.query.get(project_id)
    if not project:
        return error('项目不存在', code=404)

    if 'files' not in request.files and 'file' not in request.files:
        return error('请选择要上传的图片')

    files = request.files.getlist('files') or request.files.getlist('file')
    if not files or all(f.filename == '' for f in files):
        return error('请选择要上传的图片')

    results = []

    for file in files:
        if not file or not file.filename:
            continue

        if not allowed_file(file.filename):
            results.append({
                'filename': file.filename,
                'status': 'failed',
                'message': '不支持的文件类型',
            })
            continue

        try:
            file_info = save_upload_file(file, project_id)
            thumbnail_url = create_thumbnail(file_info['file_path'], project_id)

            image = AnnotatedImage(
                filename=file_info['filename'],
                file_path=file_info['file_path'],
                file_url=file_info['file_url'],
                file_size=file_info['file_size'],
                mime_type=file_info['mime_type'],
                width=file_info['width'],
                height=file_info['height'],
                thumbnail_url=thumbnail_url,
                project_id=project_id,
                upload_by=g.current_user_id,
            )
            db.session.add(image)
            db.session.flush()

            results.append({
                'id': image.id,
                'filename': file_info['filename'],
                'originalFilename': file_info.get('original_filename', ''),
                'file_url': file_info['file_url'],
                'thumbnail_url': thumbnail_url,
                'width': file_info['width'],
                'height': file_info['height'],
                'file_size': file_info['file_size'],
                'status': 'success',
                'message': '上传成功',
            })
        except Exception as e:
            results.append({
                'filename': file.filename,
                'status': 'failed',
                'message': str(e),
            })

    db.session.commit()

    return success(data={
        'total': len(files),
        'success_count': sum(1 for r in results if r['status'] == 'success'),
        'failed_count': sum(1 for r in results if r['status'] == 'failed'),
        'results': results,
    }, message='上传完成')


@upload_bp.route('/upload/delete/<int:image_id>', methods=['DELETE'])
@login_required
def delete_image(image_id):
    """删除图片（同时删除文件 + 数据库记录 + 标注数据）"""
    image = AnnotatedImage.query.get(image_id)
    if not image:
        return error('图片不存在', code=404)

    if image.file_path:
        delete_upload_file(image.file_path)

    db.session.delete(image)
    db.session.commit()

    return success(message='图片已删除')


@upload_bp.route('/upload/batch-delete', methods=['POST'])
@login_required
def batch_delete_images():
    """批量删除图片"""
    data = request.get_json() or {}
    ids = data.get('ids', [])

    if not ids:
        return error('请选择要删除的图片')

    images = AnnotatedImage.query.filter(AnnotatedImage.id.in_(ids)).all()

    for image in images:
        if image.file_path:
            delete_upload_file(image.file_path)

    AnnotatedImage.query.filter(AnnotatedImage.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()

    return success(message=f'已删除 {len(ids)} 张图片')


# 静态文件服务：访问上传的文件
@upload_bp.route('/uploads/<path:filename>')
def serve_upload(filename):
    """提供上传文件的访问"""
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    return send_from_directory(upload_folder, filename)
