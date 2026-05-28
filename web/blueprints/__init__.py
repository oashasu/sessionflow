"""Blueprints package for SessionFlow Web API"""
from .tasks import tasks_bp
from .notes import notes_bp
from .bookmarks import bookmarks_bp
from .hosts import hosts_bp
from .archive import archive_bp
from .stats import stats_bp
from .main import main_bp
from .sessions import sessions_bp
from .requirements import requirements_bp

__all__ = [
    'tasks_bp',
    'notes_bp',
    'bookmarks_bp',
    'hosts_bp',
    'archive_bp',
    'stats_bp',
    'main_bp',
    'sessions_bp',
    'requirements_bp',
]