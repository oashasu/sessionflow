"""Notes API Blueprint"""
from flask import Blueprint, jsonify, request
from datetime import datetime
from core.storage import get_storage, SessionNote

notes_bp = Blueprint('notes', __name__)


@notes_bp.route('/notes')
def api_notes():
    """获取所有备注"""
    storage = get_storage()
    notes = storage.load_notes()
    return jsonify({sid: {'text': n.text, 'tags': n.tags} for sid, n in notes.items()})


@notes_bp.route('/notes/save', methods=['POST'])
def api_notes_save():
    """保存备注"""
    data = request.get_json()
    storage = get_storage()
    notes = storage.load_notes()

    session_id = data.get('session_id')
    text = data.get('text', '')

    if session_id in notes:
        notes[session_id].text = text
        notes[session_id].updated_at = int(datetime.now().timestamp() * 1000)
    else:
        notes[session_id] = SessionNote.create(session_id, text)

    storage.save_notes(notes)
    return jsonify({'success': True})