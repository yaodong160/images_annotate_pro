import json
from flask import Blueprint, request, g
from app.extensions import db
from app.models.annotation import AnnotationProject
from app.utils.response import success, error
from app.utils.jwt_utils import login_required

project_bp = Blueprint('project', __name__, url_prefix='/annotation/project')


@project_bp.route('/list', methods=['GET'])
@login_required
def project_list():
    """获取标注项目列表（分页）"""
    try:
        current = request.args.get('current', 1, type=int)
        size = request.args.get('size', 10, type=int)
        project_name = request.args.get('projectName', '')
        status_filter = request.args.get('status', '')
        member_id = request.args.get('memberId', '')

        query = AnnotationProject.query

        if project_name:
            query = query.filter(AnnotationProject.project_name.like(f'%{project_name}%'))
        if status_filter:
            query = query.filter(AnnotationProject.status == status_filter)
        if member_id:
            query = query.filter(AnnotationProject.member_ids.like(f'%{member_id}%'))

        query = query.order_by(AnnotationProject.created_at.desc())

        pagination = query.paginate(page=current, per_page=size, error_out=False)

        records = [p.to_dict() for p in pagination.items]

        return success(data={
            'records': records,
            'current': pagination.page,
            'size': pagination.per_page,
            'total': pagination.total,
        }, message='查询成功')
    except Exception as e:
        return error(message=f'查询失败: {str(e)}', code=500)


@project_bp.route('/add', methods=['POST'])
@login_required
def project_add():
    """新增标注项目"""
    try:
        data = request.get_json() or {}

        project_name = data.get('projectName', '').strip()
        if not project_name:
            return error(message='项目名称不能为空')

        project = AnnotationProject(
            project_name=project_name,
            description=data.get('description', ''),
            classes=json.dumps(data.get('classes', []), ensure_ascii=False),
            tags=json.dumps(data.get('tags', []), ensure_ascii=False),
            enable_comment=data.get('enableComment', False),
            tools=json.dumps(data.get('tools', []), ensure_ascii=False),
            member_ids=json.dumps(data.get('memberIds', []), ensure_ascii=False),
            camera_url=data.get('cameraUrl', '').strip() or None,
            camera_username=data.get('cameraUsername', '').strip() or None,
            camera_password=data.get('cameraPassword', '') or None,
            status=data.get('status', 'active'),
            created_by=g.current_user_id,
            updated_by=g.current_user_id,
        )

        db.session.add(project)
        db.session.commit()

        return success(data={
            'projectId': project.id,
        }, message='创建成功')
    except Exception as e:
        db.session.rollback()
        return error(message=f'创建失败: {str(e)}', code=500)


@project_bp.route('/edit/<int:project_id>', methods=['PUT'])
@login_required
def project_edit(project_id):
    """编辑标注项目"""
    try:
        project = AnnotationProject.query.get(project_id)
        if not project:
            return error(message='项目不存在', code=404)

        data = request.get_json() or {}

        if 'projectName' in data:
            name = data['projectName'].strip()
            if not name:
                return error(message='项目名称不能为空')
            project.project_name = name

        if 'description' in data:
            project.description = data['description']
        if 'classes' in data:
            project.classes = json.dumps(data['classes'], ensure_ascii=False)
        if 'tags' in data:
            project.tags = json.dumps(data['tags'], ensure_ascii=False)
        if 'enableComment' in data:
            project.enable_comment = data['enableComment']
        if 'tools' in data:
            project.tools = json.dumps(data['tools'], ensure_ascii=False)
        if 'memberIds' in data:
            project.member_ids = json.dumps(data['memberIds'], ensure_ascii=False)
        if 'status' in data:
            project.status = data['status']
        if 'cameraUrl' in data:
            project.camera_url = data['cameraUrl'].strip() or None
        if 'cameraUsername' in data:
            project.camera_username = data['cameraUsername'].strip() or None
        if 'cameraPassword' in data and data['cameraPassword']:
            project.camera_password = data['cameraPassword']

        project.updated_by = g.current_user_id

        db.session.commit()

        return success(data=project.to_dict(), message='更新成功')
    except Exception as e:
        db.session.rollback()
        return error(message=f'更新失败: {str(e)}', code=500)


@project_bp.route('/delete/<int:project_id>', methods=['DELETE'])
@login_required
def project_delete(project_id):
    """删除标注项目"""
    try:
        project = AnnotationProject.query.get(project_id)
        if not project:
            return error(message='项目不存在', code=404)

        db.session.delete(project)
        db.session.commit()

        return success(message='删除成功')
    except Exception as e:
        db.session.rollback()
        return error(message=f'删除失败: {str(e)}', code=500)


@project_bp.route('/detail/<int:project_id>', methods=['GET'])
@login_required
def project_detail(project_id):
    """获取标注项目详情"""
    try:
        project = AnnotationProject.query.get(project_id)
        if not project:
            return error(message='项目不存在', code=404)

        return success(data=project.to_dict(), message='查询成功')
    except Exception as e:
        return error(message=f'查询失败: {str(e)}', code=500)
