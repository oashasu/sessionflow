"""Tasks API Blueprint"""
from flask import Blueprint, jsonify, request
from datetime import datetime
from core.storage import get_storage, Task

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/tasks')
def api_tasks():
    """获取所有任务"""
    storage = get_storage()
    tasks = storage.load_tasks()
    return jsonify([{
        'id': t.id,
        'title': t.title,
        'status': t.status,
        'priority': t.priority,
        'linked_session_id': t.linked_session_id,
        'progress': t.progress,
    } for t in tasks])


@tasks_bp.route('/tasks/add', methods=['POST'])
def api_tasks_add():
    """添加任务"""
    data = request.get_json()
    storage = get_storage()
    tasks = storage.load_tasks()

    task = Task.create(
        data.get('title', 'Untitled'),
        priority=data.get('priority', 'medium'),
        linked_session_id=data.get('session_id'),
    )
    tasks.append(task)
    storage.save_tasks(tasks)

    return jsonify({'success': True, 'task_id': task.id})


@tasks_bp.route('/tasks/toggle/<task_id>', methods=['POST'])
def api_tasks_toggle(task_id):
    """切换任务状态"""
    storage = get_storage()
    tasks = storage.load_tasks()

    for task in tasks:
        if task.id.startswith(task_id):
            task.status = 'done' if task.status != 'done' else 'todo'
            task.progress = 100 if task.status == 'done' else 0
            task.updated_at = int(datetime.now().timestamp() * 1000)
            break

    storage.save_tasks(tasks)
    return jsonify({'success': True})


@tasks_bp.route('/tasks/delete/<task_id>', methods=['POST'])
def api_tasks_delete(task_id):
    """删除任务"""
    storage = get_storage()
    tasks = storage.load_tasks()
    tasks = [t for t in tasks if not t.id.startswith(task_id)]
    storage.save_tasks(tasks)
    return jsonify({'success': True})