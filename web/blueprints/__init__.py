"""Blueprint初始化"""
from flask import Blueprint

# 创建Blueprints
sessions_bp = Blueprint('sessions', __name__)
tasks_bp = Blueprint('tasks', __name__)
bookmarks_bp = Blueprint('bookmarks', __name__)
notes_bp = Blueprint('notes', __name__)
hosts_bp = Blueprint('hosts', __name__)
requirements_bp = Blueprint('requirements', __name__)
archive_bp = Blueprint('archive', __name__)
stats_bp = Blueprint('stats', __name__)

# 导入路由
from . import sessions, tasks, bookmarks, notes, hosts, requirements, archive, stats  # noqa: E402, F401
