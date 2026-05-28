"""SessionFlow Web界面 - Phase 2增强版 + Provider架构"""

from flask import Flask, render_template
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

app = Flask(__name__)

# 注册Blueprints
from web.blueprints.sessions import sessions_bp
from web.blueprints.tasks import tasks_bp
from web.blueprints.bookmarks import bookmarks_bp
from web.blueprints.notes import notes_bp
from web.blueprints.hosts import hosts_bp
from web.blueprints.requirements import requirements_bp
from web.blueprints.archive import archive_bp
from web.blueprints.stats import stats_bp

app.register_blueprint(sessions_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(bookmarks_bp)
app.register_blueprint(notes_bp)
app.register_blueprint(hosts_bp)
app.register_blueprint(requirements_bp)
app.register_blueprint(archive_bp)
app.register_blueprint(stats_bp)

# 注册统一错误处理器
from core.errors import (
    SessionFlowError, NotFoundError, ValidationError, ConflictError
)
from web.api import fail


@app.errorhandler(NotFoundError)
def handle_not_found(e):
    return fail(e.message, 404)


@app.errorhandler(ValidationError)
def handle_validation_error(e):
    return fail(e.message, 400)


@app.errorhandler(ConflictError)
def handle_conflict(e):
    return fail(e.message, 409)


@app.errorhandler(SessionFlowError)
def handle_sessionflow_error(e):
    return fail(e.message, 500)


@app.errorhandler(Exception)
def handle_generic_error(e):
    return fail(f"服务器内部错误: {e}", 500)


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    print("SessionFlow Web界面启动...")
    print("本地访问: http://127.0.0.1:5001")
    print("局域网访问: http://<你的IP>:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)
