"""Bookmarks API Blueprint"""
from flask import Blueprint, jsonify, request
from core.storage import get_storage

bookmarks_bp = Blueprint('bookmarks', __name__)


@bookmarks_bp.route('/bookmarks')
def api_bookmarks():
    """获取书签列表"""
    storage = get_storage()
    return jsonify(storage.load_bookmarks())


@bookmarks_bp.route('/bookmarks/add/<session_id>', methods=['POST'])
def api_bookmarks_add(session_id):
    """添加书签"""
    storage = get_storage()
    bookmarks = storage.load_bookmarks()
    if session_id not in bookmarks:
        bookmarks.append(session_id)
        storage.save_bookmarks(bookmarks)
    return jsonify({'success': True})


@bookmarks_bp.route('/bookmarks/remove/<session_id>', methods=['POST'])
def api_bookmarks_remove(session_id):
    """移除书签"""
    storage = get_storage()
    bookmarks = storage.load_bookmarks()
    bookmarks = [b for b in bookmarks if b != session_id]
    storage.save_bookmarks(bookmarks)
    return jsonify({'success': True})