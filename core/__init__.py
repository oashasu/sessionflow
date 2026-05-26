"""SessionFlow Core Module"""

from .models import SessionMeta, SessionRecord, extract_project_name
from .scanner import scan_sessions, scan_all_sessions, get_active_sessions, get_sessions_by_project
from .parser import parse_jsonl_file, get_jsonl_stats, get_jsonl_summary, find_ai_title
from .recovery import generate_recovery_cmd, open_session, recover_session
from .storage import JSONStorage, STORAGE_DIR
from .errors import (
    SessionFlowError,
    SessionNotFoundError,
    InvalidSessionIdError,
    DirectoryNotFoundError,
    NoActiveSessionError,
    MultipleMatchError,
    JsonlNotFoundError,
    SecurityError,
)

__all__ = [
    # Models
    "SessionMeta",
    "SessionRecord",
    "extract_project_name",
    # Scanner
    "scan_sessions",
    "scan_all_sessions",
    "get_active_sessions",
    "get_sessions_by_project",
    # Parser
    "parse_jsonl_file",
    "get_jsonl_stats",
    "get_jsonl_summary",
    "find_ai_title",
    # Recovery
    "generate_recovery_cmd",
    "open_session",
    "recover_session",
    # Storage
    "JSONStorage",
    "STORAGE_DIR",
    # Errors
    "SessionFlowError",
    "SessionNotFoundError",
    "InvalidSessionIdError",
    "DirectoryNotFoundError",
    "NoActiveSessionError",
    "MultipleMatchError",
    "JsonlNotFoundError",
    "SecurityError",
]