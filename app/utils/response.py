from flask import jsonify


def success(data=None, message='操作成功', code=200):
    """成功响应"""
    return jsonify({
        'code': code,
        'message': message,
        'data': data,
    }), code


def error(message='操作失败', code=400, data=None):
    """失败响应"""
    return jsonify({
        'code': code,
        'message': message,
        'data': data,
    }), code


def paginate(query, page=1, per_page=10, schema=None):
    """分页响应"""
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    items = pagination.items
    if schema:
        items = [schema.dump(item) for item in items]
    elif hasattr(items[0], 'to_dict') if items else False:
        items = [item.to_dict() for item in items]

    return {
        'code': 200,
        'message': '查询成功',
        'data': {
            'list': items,
            'total': pagination.total,
            'page': pagination.page,
            'page_size': pagination.per_page,
            'pages': pagination.pages,
        }
    }
