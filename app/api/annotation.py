import json
from flask import Blueprint, request, g
from app.extensions import db
from app.models.annotation import Annotation, AnnotationCategory, AnnotatedImage, AnnotationProject
from app.utils.jwt_utils import login_required
from app.utils.response import success, error

annotation_bp = Blueprint('annotation', __name__)


# ==================== 标注数据 CRUD ====================

@annotation_bp.route('/annotations', methods=['GET'])
@login_required
def get_annotations():
    """获取某张图片的所有标注
    Query: image_id (必填)
    """
    image_id = request.args.get('image_id', type=int)
    if not image_id:
        return error('请指定图片ID')

    image = AnnotatedImage.query.get(image_id)
    if not image:
        return error('图片不存在', code=404)

    annotations = Annotation.query.filter_by(
        image_id=image_id, status=True
    ).order_by(Annotation.created_at.desc()).all()

    return success(data=[ann.to_dict(include_category=True) for ann in annotations])


@annotation_bp.route('/annotations', methods=['POST'])
@login_required
def create_annotation():
    """创建标注
    请求体:
    {
        "image_id": 1,
        "category_id": 2,
        "shape_type": "rect",
        "coordinates": {"x": 100, "y": 100, "width": 200, "height": 150},
        "label": "人物",
        "color": "#ff0000",
        "description": "备注",
        "attributes": {"occluded": false, "truncated": false}
    }
    """
    data = request.get_json() or {}

    image_id = data.get('image_id')
    category_id = data.get('category_id')
    shape_type = data.get('shape_type', 'rect')
    coordinates = data.get('coordinates')

    if not image_id:
        return error('请指定图片ID')
    if not coordinates:
        return error('请提供标注坐标')

    # 验证形状类型
    valid_shapes = ['rect', 'polygon', 'point', 'line', 'circle']
    if shape_type not in valid_shapes:
        return error(f'不支持的形状类型，支持: {", ".join(valid_shapes)}')

    # 检查图片是否存在
    image = AnnotatedImage.query.get(image_id)
    if not image:
        return error('图片不存在', code=404)

    # 创建标注
    annotation = Annotation(
        image_id=image_id,
        category_id=category_id,
        shape_type=shape_type,
        coordinates=json.dumps(coordinates, ensure_ascii=False) if not isinstance(coordinates, str) else coordinates,
        label=data.get('label', ''),
        description=data.get('description', ''),
        color=data.get('color', ''),
        attributes=json.dumps(data.get('attributes'), ensure_ascii=False) if data.get('attributes') and not isinstance(data.get('attributes'), str) else data.get('attributes'),
        created_by=g.current_user_id,
    )
    db.session.add(annotation)

    # 更新图片的标注状态
    image.is_annotated = True
    image.annotation_count = Annotation.query.filter_by(
        image_id=image_id, status=True
    ).count() + 1

    db.session.commit()

    return success(data=annotation.to_dict(include_category=True), message='标注创建成功')


@annotation_bp.route('/annotations/<int:annotation_id>', methods=['PUT'])
@login_required
def update_annotation(annotation_id):
    """更新标注
    请求体: 同创建接口（部分字段可省略）
    """
    annotation = Annotation.query.get(annotation_id)
    if not annotation:
        return error('标注不存在', code=404)

    data = request.get_json() or {}

    if 'coordinates' in data:
        annotation.coordinates = json.dumps(data['coordinates'], ensure_ascii=False) if not isinstance(data['coordinates'], str) else data['coordinates']
    if 'shape_type' in data:
        valid_shapes = ['rect', 'polygon', 'point', 'line', 'circle']
        if data['shape_type'] not in valid_shapes:
            return error(f'不支持的形状类型')
        annotation.shape_type = data['shape_type']
    if 'category_id' in data:
        annotation.category_id = data['category_id']
    if 'label' in data:
        annotation.label = data['label']
    if 'description' in data:
        annotation.description = data['description']
    if 'color' in data:
        annotation.color = data['color']
    if 'attributes' in data:
        annotation.attributes = json.dumps(data['attributes'], ensure_ascii=False) if not isinstance(data['attributes'], str) else data['attributes']

    db.session.commit()

    return success(data=annotation.to_dict(include_category=True), message='标注更新成功')


@annotation_bp.route('/annotations/<int:annotation_id>', methods=['DELETE'])
@login_required
def delete_annotation(annotation_id):
    """删除标注（软删除）"""
    annotation = Annotation.query.get(annotation_id)
    if not annotation:
        return error('标注不存在', code=404)

    image_id = annotation.image_id
    annotation.status = False
    db.session.commit()

    # 更新图片标注计数
    image = AnnotatedImage.query.get(image_id)
    if image:
        count = Annotation.query.filter_by(image_id=image_id, status=True).count()
        image.annotation_count = count
        image.is_annotated = count > 0
        db.session.commit()

    return success(message='标注已删除')


@annotation_bp.route('/annotations/batch', methods=['POST'])
@login_required
def batch_save_annotations():
    """批量保存标注（前端标注完一次性提交）
    请求体:
    {
        "image_id": 1,
        "annotations": [
            {
                "id": null,
                "category_id": 1,
                "shape_type": "rect",
                "coordinates": {...},
                "label": "标签",
                ...
            },
            ...
        ]
    }
    """
    data = request.get_json() or {}
    image_id = data.get('image_id')
    annotations_data = data.get('annotations', [])

    if not image_id:
        return error('请指定图片ID')

    image = AnnotatedImage.query.get(image_id)
    if not image:
        return error('图片不存在', code=404)

    # 先软删除该图片的所有旧标注
    Annotation.query.filter_by(image_id=image_id).update(
        {Annotation.status: False},
        synchronize_session=False
    )

    created = []
    for ann_data in annotations_data:
        coordinates = ann_data.get('coordinates')
        if not coordinates:
            continue

        shape_type = ann_data.get('shape_type', 'rect')
        valid_shapes = ['rect', 'polygon', 'point', 'line', 'circle']
        if shape_type not in valid_shapes:
            shape_type = 'rect'

        annotation = Annotation(
            image_id=image_id,
            category_id=ann_data.get('category_id'),
            shape_type=shape_type,
            coordinates=json.dumps(coordinates, ensure_ascii=False) if not isinstance(coordinates, str) else coordinates,
            label=ann_data.get('label', ''),
            description=ann_data.get('description', ''),
            color=ann_data.get('color', ''),
            attributes=json.dumps(ann_data.get('attributes'), ensure_ascii=False) if ann_data.get('attributes') and not isinstance(ann_data.get('attributes'), str) else ann_data.get('attributes'),
            created_by=g.current_user_id,
        )
        db.session.add(annotation)
        created.append(annotation)

    # 更新图片标注状态
    image.is_annotated = len(created) > 0
    image.annotation_count = len(created)

    db.session.commit()

    return success(data={
        'image_id': image_id,
        'count': len(created),
        'annotations': [ann.to_dict(include_category=True) for ann in created],
    }, message=f'批量保存成功，共 {len(created)} 个标注')


@annotation_bp.route('/annotations/batch-delete', methods=['POST'])
@login_required
def batch_delete_annotations():
    """批量删除标注
    请求体: {"ids": [1, 2, 3]}
    """
    data = request.get_json() or {}
    ids = data.get('ids', [])

    if not ids:
        return error('请选择要删除的标注')

    Annotation.query.filter(
        Annotation.id.in_(ids)
    ).update(
        {Annotation.status: False},
        synchronize_session=False
    )
    db.session.commit()

    return success(message=f'已删除 {len(ids)} 个标注')


@annotation_bp.route('/annotations/copy', methods=['POST'])
@login_required
def copy_annotations():
    """将一张图片的标注复制到另一张图片
    请求体:
    {
        "from_image_id": 1,
        "to_image_id": 2
    }
    """
    data = request.get_json() or {}
    from_image_id = data.get('from_image_id')
    to_image_id = data.get('to_image_id')

    if not from_image_id or not to_image_id:
        return error('请指定源图片和目标图片ID')

    from_image = AnnotatedImage.query.get(from_image_id)
    to_image = AnnotatedImage.query.get(to_image_id)

    if not from_image or not to_image:
        return error('图片不存在', code=404)

    # 复制标注
    source_annotations = Annotation.query.filter_by(
        image_id=from_image_id, status=True
    ).all()

    count = 0
    for ann in source_annotations:
        new_ann = Annotation(
            image_id=to_image_id,
            category_id=ann.category_id,
            shape_type=ann.shape_type,
            coordinates=ann.coordinates,
            label=ann.label,
            description=ann.description,
            color=ann.color,
            attributes=ann.attributes,
            created_by=g.current_user_id,
        )
        db.session.add(new_ann)
        count += 1

    # 更新目标图片状态
    to_image.is_annotated = count > 0
    to_image.annotation_count = Annotation.query.filter_by(
        image_id=to_image_id, status=True
    ).count() + count

    db.session.commit()

    return success(data={'count': count}, message=f'已复制 {count} 个标注')


# ==================== 标注分类管理 ====================

@annotation_bp.route('/categories', methods=['GET'])
@login_required
def get_categories():
    """获取标注分类树"""
    parent_id = request.args.get('parent_id', type=int)
    query = AnnotationCategory.query.filter_by(status=True)

    if parent_id is not None:
        query = query.filter_by(parent_id=parent_id)
    else:
        query = query.filter_by(parent_id=None)

    categories = query.order_by(AnnotationCategory.sort_order).all()

    result = []
    for cat in categories:
        cat_dict = cat.to_dict()
        cat_dict['children'] = _get_category_children(cat.id)
        cat_dict['annotation_count'] = Annotation.query.filter_by(
            category_id=cat.id, status=True
        ).count()
        result.append(cat_dict)

    return success(data=result)


def _get_category_children(parent_id):
    children = AnnotationCategory.query.filter_by(
        parent_id=parent_id, status=True
    ).order_by(AnnotationCategory.sort_order).all()
    result = []
    for child in children:
        child_dict = child.to_dict()
        child_dict['children'] = _get_category_children(child.id)
        child_dict['annotation_count'] = Annotation.query.filter_by(
            category_id=child.id, status=True
        ).count()
        result.append(child_dict)
    return result


@annotation_bp.route('/categories', methods=['POST'])
@login_required
def create_category():
    """创建标注分类"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    code = data.get('code', '').strip()

    if not name or not code:
        return error('分类名称和编码不能为空')

    if AnnotationCategory.query.filter_by(code=code).first():
        return error('分类编码已存在')

    category = AnnotationCategory(
        name=name,
        code=code,
        color=data.get('color', '#1890ff'),
        parent_id=data.get('parent_id'),
        sort_order=data.get('sort_order', 0),
        description=data.get('description', ''),
        created_by=g.current_user_id,
    )
    db.session.add(category)
    db.session.commit()

    return success(data=category.to_dict(), message='分类创建成功')


@annotation_bp.route('/categories/<int:category_id>', methods=['PUT'])
@login_required
def update_category(category_id):
    """更新标注分类"""
    category = AnnotationCategory.query.get(category_id)
    if not category:
        return error('分类不存在', code=404)

    data = request.get_json() or {}
    if 'name' in data:
        category.name = data['name'].strip()
    if 'code' in data:
        code = data['code'].strip()
        existing = AnnotationCategory.query.filter_by(code=code).first()
        if existing and existing.id != category_id:
            return error('分类编码已存在')
        category.code = code
    if 'color' in data:
        category.color = data['color']
    if 'parent_id' in data:
        category.parent_id = data['parent_id'] if data['parent_id'] else None
    if 'sort_order' in data:
        category.sort_order = data['sort_order']
    if 'description' in data:
        category.description = data['description']
    if 'status' in data:
        category.status = bool(data['status'])

    db.session.commit()
    return success(data=category.to_dict(), message='分类更新成功')


@annotation_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@login_required
def delete_category(category_id):
    """删除标注分类"""
    category = AnnotationCategory.query.get(category_id)
    if not category:
        return error('分类不存在', code=404)

    # 检查是否有子分类
    has_children = AnnotationCategory.query.filter_by(
        parent_id=category_id, status=True
    ).first()
    if has_children:
        return error('请先删除子分类')

    # 检查是否有关联的标注
    has_annotations = Annotation.query.filter_by(
        category_id=category_id, status=True
    ).first()
    if has_annotations:
        return error('该分类下存在标注数据，请先处理')

    category.status = False
    db.session.commit()

    return success(message='分类已删除')


# ==================== 前端兼容的标注结果接口 ====================

@annotation_bp.route('/annotation/result/image/<int:image_id>', methods=['GET'])
@login_required
def get_image_results(image_id):
    """获取某张图片的标注结果（前端 RegionData 格式）"""
    image = AnnotatedImage.query.get(image_id)
    if not image:
        return error('图片不存在', code=404)

    annotations = Annotation.query.filter_by(
        image_id=image_id, status=True
    ).order_by(Annotation.created_at.desc()).all()

    regions = []
    for ann in annotations:
        coords = json.loads(ann.coordinates) if isinstance(ann.coordinates, str) else ann.coordinates
        # 转换坐标格式：将后端的坐标格式转为前端需要的 points 格式
        points = _convert_coords_to_points(coords, ann.shape_type)
        # 从 attributes 读取标签信息
        tags = json.loads(ann.attributes) if isinstance(ann.attributes, str) else ann.attributes
        if not isinstance(tags, list):
            tags = [] if tags is None else [tags]

        regions.append({
            'id': ann.id,
            'type': _map_shape_type(ann.shape_type),
            'cls': ann.category.name if ann.category else '',
            'tags': tags,
            'comment': ann.description or '',
            'points': points,
        })

    return success(data=regions)


@annotation_bp.route('/annotation/result/save', methods=['POST'])
@login_required
def save_image_results():
    """保存标注结果（单张图片的全部 regions，覆盖式）
    请求体: { projectId, imageId, regions: [{ type, cls, tags, comment, points }] }
    每次保存前先删除该图片原有标注，再全量插入。
    """
    data = request.get_json() or {}
    image_id = data.get('imageId')
    regions = data.get('regions', [])

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f'[save] imageId={image_id}, regions count={len(regions)}, raw keys={list(data.keys())}')

    if not image_id:
        return error('缺少图片ID')

    image = AnnotatedImage.query.get(image_id)
    if not image:
        return error('图片不存在', code=404)

    # 先校验所有 region 数据合法性，避免删了旧数据后新数据又不合法
    for i, region in enumerate(regions):
        shape_type = _reverse_shape_type(region.get('type', 'create-box'))
        points = region.get('points', [])
        coords = _convert_points_to_coords(points, shape_type)
        if not coords:
            return error(f'第 {i+1} 个标注区域坐标为空或格式不正确')
        if shape_type == 'rect' and (coords.get('width', 0) <= 0 or coords.get('height', 0) <= 0):
            return error(f'第 {i+1} 个矩形标注宽或高为 0，请确保已正确绘制标注区域')

    # 物理删除该图片的所有旧标注
    Annotation.query.filter_by(image_id=image_id).delete()

    saved_count = 0
    for i, region in enumerate(regions):
        shape_type = _reverse_shape_type(region.get('type', 'create-box'))
        cls_name = region.get('cls', '')
        # 兼容前端传 tags 或 attributes 两种字段名
        tags = region.get('tags') or region.get('attributes') or []
        comment = region.get('comment', '')
        points = region.get('points', [])

        logger.info(f'[save] region[{i}] type={region.get("type")} shape={shape_type} cls={cls_name} tags={tags} points={points}')

        coords = _convert_points_to_coords(points, shape_type)

        category = None
        if cls_name:
            category = AnnotationCategory.query.filter_by(name=cls_name, status=True).first()

        annotation = Annotation(
            image_id=image_id,
            category_id=category.id if category else None,
            shape_type=shape_type,
            coordinates=json.dumps(coords, ensure_ascii=False),
            label=cls_name or None,
            description=comment,
            attributes=json.dumps(tags, ensure_ascii=False),
            color=category.color if category else None,
            created_by=g.current_user_id,
        )
        db.session.add(annotation)
        saved_count += 1

    # 更新图片标注状态
    image.is_annotated = saved_count > 0
    image.annotation_count = saved_count

    db.session.commit()
    return success(data={'count': saved_count}, message=f'保存成功，共 {saved_count} 个标注')


@annotation_bp.route('/annotation/result/project/<int:project_id>', methods=['GET'])
@login_required
def get_project_results(project_id):
    """获取项目所有图片的标注结果"""
    project = AnnotationProject.query.get(project_id)
    if not project:
        return error('项目不存在', code=404)

    images = AnnotatedImage.query.filter_by(
        project_id=project_id, status=True
    ).all()

    result = []
    for image in images:
        annotations = Annotation.query.filter_by(
            image_id=image.id, status=True
        ).order_by(Annotation.created_at.desc()).all()

        regions = []
        for ann in annotations:
            coords = json.loads(ann.coordinates) if isinstance(ann.coordinates, str) else ann.coordinates
            points = _convert_coords_to_points(coords, ann.shape_type)
            tags = json.loads(ann.attributes) if isinstance(ann.attributes, str) else ann.attributes
            if not isinstance(tags, list):
                tags = [] if tags is None else [tags]

            regions.append({
                'type': _map_shape_type(ann.shape_type),
                'cls': ann.category.name if ann.category else '',
                'tags': tags,
                'comment': ann.description or '',
                'points': points,
            })

        result.append({
            'imageId': image.id,
            'projectId': project_id,
            'regions': regions,
            'updateTime': image.updated_at.strftime('%Y-%m-%d %H:%M:%S') if image.updated_at else None,
        })

    return success(data=result)


# ==================== 坐标格式转换工具 ====================

def _map_shape_type(shape_type):
    """后端 shape_type -> 前端库原生 Region type（react-image-annotate 使用 'box'/'polygon'/'point'）"""
    mapping = {
        'rect': 'box',
        'polygon': 'polygon',
        'point': 'point',
        'line': 'polygon',
        'circle': 'box',
    }
    return mapping.get(shape_type, 'box')


def _reverse_shape_type(tool_type):
    """前端 type -> 后端 shape_type，兼容库原生名和 create- 前缀名"""
    mapping = {
        'box': 'rect',
        'create-box': 'rect',
        'polygon': 'polygon',
        'create-polygon': 'polygon',
        'point': 'point',
        'create-point': 'point',
    }
    return mapping.get(tool_type, 'rect')


def _convert_coords_to_points(coords, shape_type):
    """将后端坐标转为前端 points 数组格式"""
    if shape_type == 'rect':
        x, y, w, h = coords.get('x', 0), coords.get('y', 0), coords.get('width', 0), coords.get('height', 0)
        return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
    elif shape_type == 'polygon':
        if isinstance(coords, list):
            return [[p.get('x', 0), p.get('y', 0)] for p in coords]
        return []
    elif shape_type == 'point':
        return [[coords.get('x', 0), coords.get('y', 0)]]
    elif shape_type == 'line':
        if isinstance(coords, list):
            return [[p.get('x', 0), p.get('y', 0)] for p in coords]
        return []
    elif shape_type == 'circle':
        cx, cy, r = coords.get('cx', 0), coords.get('cy', 0), coords.get('r', 0)
        return [[cx - r, cy - r], [cx + r, cy - r], [cx + r, cy + r], [cx - r, cy + r]]
    return []


def _clamp(v):
    """将坐标值裁剪到 [0, 1] 范围内"""
    return max(0.0, min(1.0, v))


def _round_coord(v, precision=4):
    """将坐标值四舍五入，消除浮点尾数"""
    factor = 10 ** precision
    return round(v * factor) / factor


def _convert_points_to_coords(points, shape_type):
    """将前端 points 数组转为后端坐标格式，自动裁剪到 [0,1] 范围并消除浮点尾数"""
    if not points:
        return {}
    if shape_type == 'rect':
        # 矩形有4个点（左上、右上、右下、左下），取边界盒
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x, y = _round_coord(_clamp(min(xs))), _round_coord(_clamp(min(ys)))
        w = _round_coord(_clamp(max(xs)) - x)
        h = _round_coord(_clamp(max(ys)) - y)
        return {'x': x, 'y': y, 'width': w, 'height': h}
    elif shape_type == 'polygon':
        return [{'x': _round_coord(_clamp(p[0])), 'y': _round_coord(_clamp(p[1]))} for p in points]
    elif shape_type == 'point':
        return {'x': _round_coord(_clamp(points[0][0])), 'y': _round_coord(_clamp(points[0][1]))}
    elif shape_type == 'line':
        return [{'x': _round_coord(_clamp(p[0])), 'y': _round_coord(_clamp(p[1]))} for p in points]
    elif shape_type == 'circle':
        if len(points) >= 2:
            cx = _round_coord(_clamp((points[0][0] + points[1][0]) / 2))
            cy = _round_coord(_clamp((points[0][1] + points[1][1]) / 2))
            r = _round_coord(((points[1][0] - points[0][0]) ** 2 + (points[1][1] - points[0][1]) ** 2) ** 0.5 / 2)
            return {'cx': cx, 'cy': cy, 'r': r}
    return {}
