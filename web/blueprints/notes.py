"""备注管理API"""
from flask import request
from datetime import datetime

from . import notes_bp
from core import get_storage, SessionNote
from web.api import ok


@notes_bp.route('/api/notes')
def api_notes():
    """获取所有备注"""
    storage = get_storage()
    notes = storage.load_notes()
    return ok(data={sid: {'text': n.text, 'tags': n.tags} for sid, n in notes.items()})


@notes_bp.route('/api/notes/save', methods=['POST'])
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
    return ok()
