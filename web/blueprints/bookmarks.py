"""书签管理API"""
from . import bookmarks_bp
from core import get_storage
from web.api import ok, ok_list


@bookmarks_bp.route('/api/bookmarks')
def api_bookmarks():
    """获取书签列表"""
    storage = get_storage()
    return ok_list(storage.load_bookmarks())


@bookmarks_bp.route('/api/bookmarks/add/<session_id>', methods=['POST'])
def api_bookmarks_add(session_id):
    """添加书签"""
    storage = get_storage()
    bookmarks = storage.load_bookmarks()
    if session_id not in bookmarks:
        bookmarks.append(session_id)
        storage.save_bookmarks(bookmarks)
    return ok()


@bookmarks_bp.route('/api/bookmarks/remove/<session_id>', methods=['POST'])
def api_bookmarks_remove(session_id):
    """移除书签"""
    storage = get_storage()
    bookmarks = storage.load_bookmarks()
    bookmarks = [b for b in bookmarks if b != session_id]
    storage.save_bookmarks(bookmarks)
    return ok()
