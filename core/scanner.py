"""会话扫描逻辑 - 使用Provider架构"""

import logging
from typing import List, Dict, Any, Optional

from .models import SessionMeta, SessionRecord, extract_project_name
from .parser import find_ai_title, get_jsonl_summary
from providers import get_factory, SessionProvider
from providers.protocol import RemoteHost

logger = logging.getLogger(__name__)


def scan_sessions(
    tool_name: Optional[str] = None,
    host: Optional[RemoteHost] = None,
    force_refresh: bool = False
) -> List[SessionRecord]:
    """扫描活跃会话（使用Provider架构）

    Args:
        tool_name: 指定工具名称（None表示所有工具）
        host: 远程主机（None表示本机）
        force_refresh: 强制刷新缓存

    Returns:
        会话记录列表
    """
    factory = get_factory()
    sessions = []

    if tool_name:
        # 单个Provider
        try:
            provider = factory.create(tool_name)
            provider_sessions = provider.scan_sessions(host, force_refresh)
            sessions.extend(provider_sessions)
        except ValueError as e:
            logger.warning(f"Provider not found: {tool_name}")
    else:
        # 所有已启用的Provider
        providers = factory.get_all_enabled()
        for provider in providers:
            try:
                provider_sessions = provider.scan_sessions(host, force_refresh)
                sessions.extend(provider_sessions)
            except Exception as e:
                logger.warning(f"Provider scan failed: {provider.tool_info.name}: {e}")

    return sessions


def scan_all_sessions(
    tool_name: Optional[str] = None,
    host: Optional[RemoteHost] = None
) -> List[SessionRecord]:
    """扫描所有会话（包括历史会话）

    Args:
        tool_name: 指定工具名称（None表示所有工具）
        host: 远程主机（None表示本机）

    Returns:
        会话记录列表
    """
    return scan_sessions(tool_name, host, force_refresh=True)


def scan_sessions_by_tool(tool_name: str) -> List[SessionRecord]:
    """按工具类型扫描会话

    Args:
        tool_name: 工具名称（claude/codex）

    Returns:
        该工具的会话列表
    """
    return scan_sessions(tool_name=tool_name)


# ========== 兼容旧API的函数 ==========

def get_active_sessions() -> List[SessionRecord]:
    """获取活跃会话（兼容旧API）"""
    sessions = scan_sessions()
    return [s for s in sessions if s.meta.status in ["busy", "active"]]


def get_sessions_by_project(project_name: str) -> List[SessionRecord]:
    """按项目获取会话（兼容旧API）"""
    sessions = scan_sessions()
    return [s for s in sessions if project_name in s.project_name]


def translate_topic(topic: str) -> str:
    """翻译主题为中文（简单关键词匹配）"""
    if not topic:
        return "无主题"

    translations = {
        "Build": "构建",
        "Fix": "修复",
        "Refine": "优化",
        "Generate": "生成",
        "Import": "导入",
        "Categorize": "分类",
        "Create": "创建",
        "Update": "更新",
        "Delete": "删除",
        "Review": "审查",
        "Test": "测试",
        "session": "会话",
        "manager": "管理器",
        "workflow": "工作流",
        "skill": "技能",
        "payment": "支付",
        "fee": "费用",
        "adapter": "适配器",
        "spec": "规格",
        "orchestrator": "编排器",
        "project": "项目",
        "structure": "结构",
        "packages": "包",
        "deletion": "删除",
        "doc": "文档",
        "outbound": "出站",
        "adjustment": "调整",
        "blocking": "阻塞",
        "prove": "验证",
        "phase": "阶段",
        "false": "错误",
        "current": "当前",
        "validation": "验证",
    }

    result = topic
    for eng, chn in translations.items():
        if eng.lower() in topic.lower():
            result = result.replace(eng, chn)

    return result


# ========== 远程主机管理 ==========

def scan_remote_sessions(host: RemoteHost, tool_name: Optional[str] = None) -> List[SessionRecord]:
    """扫描远程主机会话

    Args:
        host: 远程主机配置
        tool_name: 指定工具名称（None表示所有工具）

    Returns:
        远程会话列表
    """
    return scan_sessions(tool_name=tool_name, host=host)


def get_available_tools() -> List[str]:
    """获取所有可用工具列表

    Returns:
        工具名称列表
    """
    factory = get_factory()
    return factory.discover_available()