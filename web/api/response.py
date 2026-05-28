"""统一API响应格式"""

from flask import jsonify


def ok(data=None, **kwargs):
    """成功响应

    用于查询和操作类接口，返回统一的成功格式。
    """
    body = {"success": True}
    if data is not None:
        body["data"] = data
    body.update(kwargs)
    return jsonify(body)


def ok_list(items):
    """列表成功响应

    用于返回列表数据，自动包装为 {"success": true, "data": [...], "total": N}
    """
    return jsonify({
        "success": True,
        "data": items,
        "total": len(items),
    })


def fail(error, status_code=400):
    """失败响应

    返回统一的错误格式和HTTP状态码。
    """
    return jsonify({"success": False, "error": str(error)}), status_code
