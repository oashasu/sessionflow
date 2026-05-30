"""Main Blueprint - Home page route"""
from flask import Blueprint, render_template_string, Response

# Import HTML_TEMPLATE from app.py to avoid circular import
# This will be set by app.py after importing this blueprint
HTML_TEMPLATE = None

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Home page route"""
    if HTML_TEMPLATE is None:
        # Fallback if HTML_TEMPLATE not set
        return "Error: HTML_TEMPLATE not configured", 500
    return render_template_string(HTML_TEMPLATE)


@main_bp.route('/favicon.ico')
def favicon():
    """Return empty favicon to prevent 404"""
    return Response('', status=204)