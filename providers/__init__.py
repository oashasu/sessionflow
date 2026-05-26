"""Provider插件架构 - 会话管理抽象层"""

from .protocol import (
    SessionProvider,
    ToolInfo,
    TmuxMapping,
    RemoteHost,
    ProviderConfig,
)
from .base_provider import BaseSessionProvider
from .factory import (
    SessionProviderFactory,
    get_factory,
    register_provider,
    create_provider,
)
from .claude_provider import ClaudeProvider
from .codex_provider import CodexProvider


# 自动注册Provider
def _auto_register():
    """自动注册已知的Provider"""
    factory = get_factory()
    factory.register(ClaudeProvider)
    factory.register(CodexProvider)


# 模块加载时自动注册
_auto_register()


__all__ = [
    # Protocol
    "SessionProvider",
    "ToolInfo",
    "TmuxMapping",
    "RemoteHost",
    "ProviderConfig",
    # Base
    "BaseSessionProvider",
    # Factory
    "SessionProviderFactory",
    "get_factory",
    "register_provider",
    "create_provider",
    # Providers
    "ClaudeProvider",
    "CodexProvider",
]