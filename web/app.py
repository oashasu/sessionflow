"""SessionFlow Web界面 - Blueprint架构"""

from flask import Flask, render_template
import sys
from pathlib import Path

# 设置项目根目录和web目录到sys.path
project_root = Path(__file__).parent.parent
web_dir = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(web_dir))

app = Flask(__name__, template_folder='templates')

# ============================================================================
# 路由
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')


# ============================================================================
# Blueprint注册
# ============================================================================

from blueprints import tasks_bp, notes_bp, bookmarks_bp, hosts_bp, archive_bp, stats_bp, main_bp
from blueprints import sessions_bp, requirements_bp

app.register_blueprint(main_bp)
app.register_blueprint(sessions_bp)
app.register_blueprint(requirements_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(notes_bp)
app.register_blueprint(bookmarks_bp)
app.register_blueprint(hosts_bp)
app.register_blueprint(archive_bp)
app.register_blueprint(stats_bp)


if __name__ == '__main__':
    print("SessionFlow Web界面启动...")
    print("本地访问: http://127.0.0.1:5001")
    print("局域网访问: http://<你的IP>:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)