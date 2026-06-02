from datetime import datetime
import json
from app.extensions import db


class AnnotationProject(db.Model):
    """标注项目表"""
    __tablename__ = 'annotation_projects'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_name = db.Column(db.String(200), nullable=False, comment='项目名称')
    description = db.Column(db.Text, comment='项目描述')
    # classes: [{"name": "xxx"}, ...] 标注分类配置
    classes = db.Column(db.Text, comment='标注分类配置(JSON)')
    # tags: ["tag1", "tag2"] 标签列表
    tags = db.Column(db.Text, comment='标签列表(JSON)')
    enable_comment = db.Column(db.Boolean, default=False, comment='是否启用评论')
    # tools: ["create-box", "create-polygon", "create-point"] 可用工具
    tools = db.Column(db.Text, comment='可用工具列表(JSON)')
    # member_ids: ["user1", "user2"] 项目组成员用户名列表
    member_ids = db.Column(db.Text, comment='项目组成员(JSON)')
    # 摄像头配置（海康 ISAPI）
    camera_url = db.Column(db.String(500), comment='摄像头ISAPI地址，如 http://192.168.1.64')
    camera_username = db.Column(db.String(100), comment='摄像头用户名')
    camera_password = db.Column(db.String(500), comment='摄像头密码(加密存储)')
    status = db.Column(db.String(20), default='active', comment='状态: active/completed')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建人')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='更新人')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联用户
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_projects')
    updater = db.relationship('User', foreign_keys=[updated_by], backref='updated_projects')

    # 关联图片
    images = db.relationship('AnnotatedImage', back_populates='project', lazy='dynamic',
                             cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'projectName': self.project_name,
            'description': self.description,
            'classes': json.loads(self.classes) if isinstance(self.classes, str) else (self.classes or []),
            'tags': json.loads(self.tags) if isinstance(self.tags, str) else (self.tags or []),
            'enableComment': self.enable_comment if self.enable_comment is not None else False,
            'tools': json.loads(self.tools) if isinstance(self.tools, str) else (self.tools or []),
            'memberIds': json.loads(self.member_ids) if isinstance(self.member_ids, str) else (self.member_ids or []),
            'cameraUrl': self.camera_url or '',
            'cameraUsername': self.camera_username or '',
            'totalImages': self.images.count(),
            'annotatedCount': self.images.filter(AnnotatedImage.is_annotated == True).count(),
            'status': self.status or 'active',
            'createBy': self.creator.username if self.creator else '',
            'createTime': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updateBy': self.updater.username if self.updater else '',
            'updateTime': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }


class AnnotationCategory(db.Model):
    """标注分类表（如：人物、车辆、动物等）"""
    __tablename__ = 'annotation_categories'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='分类名称')
    code = db.Column(db.String(50), unique=True, nullable=False, comment='分类编码')
    color = db.Column(db.String(20), default='#1890ff', comment='标注颜色（前端渲染用）')
    parent_id = db.Column(db.Integer, db.ForeignKey('annotation_categories.id'), comment='父分类ID')
    sort_order = db.Column(db.Integer, default=0, comment='排序')
    description = db.Column(db.String(500), comment='描述')
    status = db.Column(db.Boolean, default=True, comment='状态')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建人')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='更新人')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 自引用关系
    children = db.relationship('AnnotationCategory', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

    # 关联标注数据
    annotations = db.relationship('Annotation', back_populates='category', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'color': self.color,
            'parent_id': self.parent_id,
            'sort_order': self.sort_order,
            'description': self.description,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_by': self.updated_by,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }


class ImageFolder(db.Model):
    """图片文件夹（用于分组管理图片）"""
    __tablename__ = 'image_folders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200), nullable=False, comment='文件夹名称')
    parent_id = db.Column(db.Integer, db.ForeignKey('image_folders.id'), comment='父文件夹ID')
    description = db.Column(db.String(500), comment='描述')
    sort_order = db.Column(db.Integer, default=0, comment='排序')
    status = db.Column(db.Boolean, default=True, comment='状态')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建人')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='更新人')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 自引用关系
    children = db.relationship('ImageFolder', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    # 关联图片
    images = db.relationship('AnnotatedImage', back_populates='folder', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'parent_id': self.parent_id,
            'description': self.description,
            'sort_order': self.sort_order,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_by': self.updated_by,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }


class AnnotatedImage(db.Model):
    """被标注的图片"""
    __tablename__ = 'annotated_images'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filename = db.Column(db.String(300), nullable=False, comment='原始文件名')
    file_path = db.Column(db.String(500), nullable=False, comment='存储路径')
    file_url = db.Column(db.String(500), nullable=False, comment='访问URL')
    file_size = db.Column(db.Integer, comment='文件大小(字节)')
    mime_type = db.Column(db.String(50), comment='MIME类型')
    width = db.Column(db.Integer, comment='图片宽度')
    height = db.Column(db.Integer, comment='图片高度')
    thumbnail_url = db.Column(db.String(500), comment='缩略图URL')
    folder_id = db.Column(db.Integer, db.ForeignKey('image_folders.id'), comment='所属文件夹')
    project_id = db.Column(db.Integer, db.ForeignKey('annotation_projects.id'), comment='所属项目')
    status = db.Column(db.Boolean, default=True, comment='状态')
    is_annotated = db.Column(db.Boolean, default=False, comment='是否已标注')
    annotation_count = db.Column(db.Integer, default=0, comment='标注数量')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建人')
    upload_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='上传人')
    upload_at = db.Column(db.DateTime, default=datetime.now, comment='上传时间')
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='更新人')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联
    folder = db.relationship('ImageFolder', back_populates='images')
    project = db.relationship('AnnotationProject', back_populates='images')
    annotations = db.relationship('Annotation', back_populates='image', lazy='dynamic',
                                   cascade='all, delete-orphan')

    def to_dict(self):
        data = {
            'id': self.id,
            'filename': self.filename,
            'file_url': self.file_url,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'width': self.width,
            'height': self.height,
            'thumbnail_url': self.thumbnail_url,
            'folder_id': self.folder_id,
            'project_id': self.project_id,
            'status': self.status,
            'is_annotated': self.is_annotated,
            'annotation_count': self.annotation_count,
            'created_by': self.created_by,
            'upload_by': self.upload_by,
            'upload_at': self.upload_at.strftime('%Y-%m-%d %H:%M:%S') if self.upload_at else None,
            'updated_by': self.updated_by,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }
        return data


class Annotation(db.Model):
    """图片标注数据"""
    __tablename__ = 'annotations'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    image_id = db.Column(db.Integer, db.ForeignKey('annotated_images.id', ondelete='CASCADE'), nullable=False, comment='图片ID')
    category_id = db.Column(db.Integer, db.ForeignKey('annotation_categories.id'), comment='标注分类ID')

    # 标注形状类型: rect(矩形), polygon(多边形), point(点), line(线), circle(圆形)
    shape_type = db.Column(db.String(20), default='rect', comment='标注形状类型')

    # 坐标数据（JSON格式存储）
    # rect: {x, y, width, height}
    # polygon: [{x, y}, {x, y}, ...]
    # point: {x, y}
    # line: [{x, y}, {x, y}]
    # circle: {cx, cy, r}
    coordinates = db.Column(db.Text, nullable=False, comment='坐标数据(JSON)')

    label = db.Column(db.String(200), comment='标签文本')
    description = db.Column(db.Text, comment='描述/备注')
    color = db.Column(db.String(20), comment='标注颜色')
    attributes = db.Column(db.Text, comment='自定义属性(JSON)，如遮挡、截断等')

    status = db.Column(db.Boolean, default=True, comment='状态')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='创建人')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='更新人')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联
    image = db.relationship('AnnotatedImage', back_populates='annotations')
    category = db.relationship('AnnotationCategory', back_populates='annotations')

    def to_dict(self, include_image=False, include_category=False):
        data = {
            'id': self.id,
            'image_id': self.image_id,
            'category_id': self.category_id,
            'shape_type': self.shape_type,
            'coordinates': json.loads(self.coordinates) if isinstance(self.coordinates, str) else self.coordinates,
            'label': self.label,
            'description': self.description,
            'color': self.color,
            'attributes': json.loads(self.attributes) if isinstance(self.attributes, str) else self.attributes,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_by': self.updated_by,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
        }
        if include_image and self.image:
            data['image'] = self.image.to_dict()
        if include_category and self.category:
            data['category'] = self.category.to_dict()
        return data
