"""SessionFlow自定义错误类"""

from typing import Optional


class SessionFlowError(Exception):
    """SessionFlow基础错误"""

    def __init__(self, message: str, suggestion: Optional[str] = None):
        self.message = message
        self.suggestion = suggestion
        super().__init__(self.format_message())

    def format_message(self) -> str:
        if self.suggestion:
            return f"{self.message}\n提示: {self.suggestion}"
        return self.message


class SessionNotFoundError(SessionFlowError):
    """会话未找到"""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"会话 '{session_id}' 未找到",
            suggestion="使用 'sessionflow list' 查看所有会话",
        )


class InvalidSessionIdError(SessionFlowError):
    """无效的Session ID格式"""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"无效的Session ID格式: '{session_id}'",
            suggestion="Session ID应为UUID格式（如: abc12345-def6-7890-abcd-ef1234567890）",
        )


class DirectoryNotFoundError(SessionFlowError):
    """工作目录不存在"""

    def __init__(self, cwd: str):
        super().__init__(
            message=f"工作目录不存在: '{cwd}'",
            suggestion="请确认路径正确，或使用 'sessionflow list' 查看会话的实际工作目录",
        )


class NoActiveSessionError(SessionFlowError):
    """没有活跃会话"""

    def __init__(self):
        super().__init__(
            message="当前没有活跃会话",
            suggestion="使用 'sessionflow scan' 扫描所有会话",
        )


class MultipleMatchError(SessionFlowError):
    """多个匹配结果"""

    def __init__(self, prefix: str, matches: list):
        match_list = "\n".join(
            f"  [{i+1}] {m.short_id} | {m.project_name}"
            for i, m in enumerate(matches)
        )
        super().__init__(
            message=f"前缀 '{prefix}' 匹配到 {len(matches)} 个会话:\n{match_list}",
            suggestion="请输入完整Session ID，或使用 --select-first 选择第一个匹配",
        )


class JsonlNotFoundError(SessionFlowError):
    """JSONL日志文件未找到"""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"会话 '{session_id}' 的日志文件未找到",
            suggestion="该会话可能已过期或日志已被清理",
        )


class SecurityError(SessionFlowError):
    """安全验证失败"""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            suggestion="请确保路径在允许范围内",
        )


# ========== API层错误类 ==========


class NotFoundError(SessionFlowError):
    """资源不存在"""

    def __init__(self, resource_type: str, resource_id: str, suggestion: Optional[str] = None):
        super().__init__(
            message=f"{resource_type} '{resource_id}' 不存在",
            suggestion=suggestion or f"请检查{resource_type} ID是否正确",
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class ValidationError(SessionFlowError):
    """验证错误"""

    def __init__(self, field: str, reason: str):
        super().__init__(
            message=f"字段 '{field}' 验证失败: {reason}",
            suggestion="请检查输入值是否符合要求",
        )
        self.field = field
        self.reason = reason


class ConflictError(SessionFlowError):
    """冲突错误（如重复创建）"""

    def __init__(self, resource_type: str, conflict_field: str, value: str):
        super().__init__(
            message=f"{resource_type} 已存在（{conflict_field}={value}）",
            suggestion="请使用不同的值或更新现有资源",
        )
        self.resource_type = resource_type
        self.conflict_field = conflict_field
        self.value = value