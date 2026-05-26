"""Provider工厂 - 创建和管理Provider实例"""

from typing import Dict, List, Optional, Any, Type

from .protocol import SessionProvider, ProviderConfig
from .base_provider import BaseSessionProvider


class SessionProviderFactory:
    """Provider工厂 - 实例级缓存

    改进点（基于Agent评估）：
    - 实例级缓存（非类级），支持测试隔离
    - clear_cache()方法
    - create()支持force_new参数

    使用方式：
        factory = SessionProviderFactory()
        factory.register(ClaudeProvider)
        provider = factory.create("claude", config)
    """

    def __init__(self):
        self._providers: Dict[str, SessionProvider] = {}
        self._registered_classes: Dict[str, Type[BaseSessionProvider]] = {}

    def register(self, provider_class: Type[BaseSessionProvider]) -> None:
        """注册Provider类

        Args:
            provider_class: Provider类（必须继承BaseSessionProvider）
        """
        # 自动从类中获取tool_info
        info = provider_class(config={}).tool_info
        self._registered_classes[info.name] = provider_class

    def create(
        self,
        tool_name: str,
        config: Dict[str, Any] = None,
        force_new: bool = False
    ) -> SessionProvider:
        """创建Provider实例

        Args:
            tool_name: 工具名称（claude/codex/qwen）
            config: Provider配置
            force_new: 强制创建新实例（忽略缓存）

        Returns:
            Provider实例

        Raises:
            ValueError: 未知的Provider
        """
        if tool_name not in self._registered_classes:
            raise ValueError(f"Unknown provider: {tool_name}. "
                           f"Available: {list(self._registered_classes.keys())}")

        # 检查缓存
        if not force_new and tool_name in self._providers:
            return self._providers[tool_name]

        # 创建新实例
        provider = self._registered_classes[tool_name](config)
        self._providers[tool_name] = provider
        return provider

    def get_or_create(self, tool_name: str, config: Dict[str, Any] = None) -> SessionProvider:
        """获取或创建Provider（别名方法）"""
        return self.create(tool_name, config, force_new=False)

    def clear_cache(self, tool_name: Optional[str] = None) -> None:
        """清除缓存

        Args:
            tool_name: 指定工具名（None清除全部）
        """
        if tool_name:
            self._providers.pop(tool_name, None)
        else:
            self._providers.clear()

    def get_all_enabled(self, config: Dict[str, Any] = None) -> List[SessionProvider]:
        """获取所有启用的Provider

        Args:
            config: 全局配置，包含enabled_tools列表

        Returns:
            启用的Provider列表
        """
        if config is None:
            config = {}
        enabled_tools = config.get("enabled_tools", list(self._registered_classes.keys()))
        providers = []

        for tool_name in enabled_tools:
            if tool_name in self._registered_classes:
                providers.append(self.create(tool_name, config))

        return providers

    def discover_available(self) -> List[str]:
        """自动发现已安装的工具

        Returns:
            可用工具名称列表
        """
        available = []
        for tool_name, provider_class in self._registered_classes.items():
            try:
                provider = provider_class(config={})
                if provider.is_installed():
                    available.append(tool_name)
            except Exception:
                pass
        return available

    def list_registered(self) -> List[str]:
        """列出已注册的Provider

        Returns:
            已注册工具名称列表
        """
        return list(self._registered_classes.keys())


# 全局工厂实例（方便直接使用）
_global_factory: Optional[SessionProviderFactory] = None


def get_factory() -> SessionProviderFactory:
    """获取全局工厂实例"""
    global _global_factory
    if _global_factory is None:
        _global_factory = SessionProviderFactory()
    return _global_factory


def register_provider(provider_class: Type[BaseSessionProvider]) -> None:
    """注册Provider到全局工厂"""
    get_factory().register(provider_class)


def create_provider(tool_name: str, config: Dict[str, Any] = None) -> SessionProvider:
    """创建Provider（使用全局工厂）"""
    return get_factory().create(tool_name, config)