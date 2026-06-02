import os
from flask import Blueprint, request, g
from app.extensions import db
from app.models.annotation import AnnotatedImage
from app.utils.jwt_utils import login_required
from app.utils.response import success, error
from app.utils.file_utils import delete_upload_file

image_bp = Blueprint('image', __name__)


# ==================== 前端标注图片接口 ====================

@image_bp.route('/annotation/image/list', methods=['GET'])
@login_required
def get_annotation_image_list():
    """获取项目图片列表（分页）
    Query: projectId, annotateStatus, current, size
    """
    current_page = request.args.get('current', 1, type=int)
    size = request.args.get('size', 10, type=int)
    project_id = request.args.get('projectId', type=int)
    annotate_status = request.args.get('annotateStatus', '')

    query = AnnotatedImage.query.filter_by(status=True)

    if project_id:
        query = query.filter_by(project_id=project_id)
    if annotate_status:
        if annotate_status == 'pending':
            query = query.filter_by(is_annotated=False)
        elif annotate_status == 'annotated':
            query = query.filter_by(is_annotated=True)

    query = query.order_by(AnnotatedImage.upload_at.desc())

    pagination = query.paginate(page=current_page, per_page=size, error_out=False)

    records = []
    for img in pagination.items:
        status_map = {False: 'pending', True: 'annotated'}
        records.append({
            'id': img.id,
            'projectId': img.project_id,
            'imageUrl': img.file_url,
            'imageName': img.filename,
            'annotateStatus': status_map.get(img.is_annotated, 'pending'),
            'annotator': '',
            'annotateTime': img.updated_at.strftime('%Y-%m-%d %H:%M:%S') if img.updated_at else None,
            'createTime': img.upload_at.strftime('%Y-%m-%d %H:%M:%S') if img.upload_at else None,
        })

    return success(data={
        'records': records,
        'current': pagination.page,
        'size': pagination.per_page,
        'total': pagination.total,
    })


@image_bp.route('/annotation/image/delete/<int:image_id>', methods=['DELETE'])
@login_required
def delete_annotation_image(image_id):
    """删除标注图片"""
    image = AnnotatedImage.query.get(image_id)
    if not image:
        return error('图片不存在', code=404)

    if image.file_path and os.path.exists(image.file_path):
        delete_upload_file(image.file_path)

    db.session.delete(image)
    db.session.commit()
    return success(message='删除成功')


# ==================== 图片管理 ====================

@image_bp.route('/images', methods=['GET'])
@login_required
def get_image_list():
    """获取图片列表（分页 + 筛选）
    Query: page, page_size, project_id, is_annotated, keyword
    """
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 12, type=int)
    project_id = request.args.get('project_id', type=int)
    is_annotated = request.args.get('is_annotated', type=int)
    keyword = request.args.get('keyword', '')

    query = AnnotatedImage.query.filter_by(status=True)

    if project_id is not None:
        query = query.filter_by(project_id=project_id)
    if is_annotated is not None:
        query = query.filter_by(is_annotated=bool(is_annotated))
    if keyword:
        query = query.filter(AnnotatedImage.filename.like(f'%{keyword}%'))

    query = query.order_by(AnnotatedImage.upload_at.desc())

    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return success(data={
        'list': [img.to_dict() for img in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'page_size': pagination.per_page,
        'pages': pagination.pages,
    })


@image_bp.route('/images/<int:image_id>', methods=['GET'])
@login_required
def get_image_detail(image_id):
    """获取图片详情（包含所有标注数据）"""
    image = AnnotatedImage.query.get(image_id)
    if not image:
        return error('图片不存在', code=404)

    from app.models.annotation import Annotation
    annotations = Annotation.query.filter_by(
        image_id=image_id,
        status=True
    ).order_by(Annotation.created_at.desc()).all()

    return success(data={
        'image': image.to_dict(),
        'annotations': [ann.to_dict(include_category=True) for ann in annotations],
    })


@image_bp.route('/images/<int:image_id>', methods=['PUT'])
@login_required
def update_image(image_id):
    """更新图片信息"""
    image = AnnotatedImage.query.get(image_id)
    if not image:
        return error('图片不存在', code=404)

    data = request.get_json() or {}

    if 'status' in data:
        image.status = bool(data['status'])

    db.session.commit()
    return success(data=image.to_dict(), message='更新成功')


@image_bp.route('/images/move', methods=['POST'])
@login_required
def move_images():
    """批量移动图片到指定项目
    请求体: {"image_ids": [1, 2, 3], "project_id": 5}
    """
    data = request.get_json() or {}
    image_ids = data.get('image_ids', [])
    project_id = data.get('project_id')

    if not image_ids:
        return error('请选择要移动的图片')
    if not project_id:
        return error('请指定目标项目')

    AnnotatedImage.query.filter(
        AnnotatedImage.id.in_(image_ids)
    ).update(
        {AnnotatedImage.project_id: project_id},
        synchronize_session=False
    )
    db.session.commit()

    return success(message=f'已移动 {len(image_ids)} 张图片')
