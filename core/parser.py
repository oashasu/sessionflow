"""JSON/JSONL解析逻辑"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, Iterator, List


def parse_jsonl_file(jsonl_path: Path) -> Iterator[Dict[str, Any]]:
    """解析JSONL文件（流式读取）"""
    if not jsonl_path.exists():
        return

    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def get_jsonl_stats(jsonl_path: Path) -> Dict[str, int]:
    """获取JSONL文件统计信息"""
    stats = {
        "total_events": 0,
        "tool_calls": 0,
        "user_messages": 0,
        "assistant_messages": 0,
    }

    for event in parse_jsonl_file(jsonl_path):
        stats["total_events"] += 1
        event_type = event.get("type", "")

        if event_type == "tool_use":
            stats["tool_calls"] += 1
        elif event_type == "human":
            stats["user_messages"] += 1
        elif event_type == "assistant":
            stats["assistant_messages"] += 1

    return stats


def find_ai_title(jsonl_path: Path) -> Optional[str]:
    """从JSONL中提取AI标题"""
    for event in parse_jsonl_file(jsonl_path):
        if event.get("type") == "ai-title":
            return event.get("aiTitle", "")
        # 也检查custom-title
        if event.get("type") == "custom-title":
            return event.get("customTitle", "")
    return None


def find_first_user_message(jsonl_path: Path) -> Optional[str]:
    """提取第一条用户消息（作为任务描述）"""
    for event in parse_jsonl_file(jsonl_path):
        if event.get("type") == "user":
            message = event.get("message", {})
            content = message.get("content", "")
            # 处理content可能是列表的情况
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")
                        if text:
                            return text[:200]  # 截取前200字符
            elif isinstance(content, str) and content:
                return content[:200]
    return None


def get_session_tasks(jsonl_path: Path) -> list:
    """从JSONL中提取任务列表"""
    tasks = []

    for event in parse_jsonl_file(jsonl_path):
        if event.get("type") == "TaskCreate":
            task_data = event.get("task", {})
            tasks.append({
                "id": task_data.get("taskId"),
                "subject": task_data.get("subject"),
                "status": task_data.get("status"),
            })

    return tasks


def get_jsonl_summary(jsonl_path: Path) -> Dict[str, Any]:
    """获取JSONL完整摘要（主题、统计、任务）

    支持两种格式：
    - Claude格式: type=user/assistant
    - Codex格式: type=response_item (input_text/output_text)
    """
    stats = {
        "total_events": 0,
        "tool_calls": 0,
        "user_messages": 0,
        "assistant_messages": 0,
        "system_messages": 0,
        "read_count": 0,
        "edit_count": 0,
        "write_count": 0,
        "bash_count": 0,
    }
    topic = None
    first_user_msg = None
    tasks = []
    cwd = None  # 从JSONL提取真实cwd

    for event in parse_jsonl_file(jsonl_path):
        stats["total_events"] += 1
        event_type = event.get("type", "")

        # 提取cwd（从第一个包含cwd的事件）
        if not cwd:
            # Claude格式
            if "cwd" in event:
                cwd = event.get("cwd")
            # Codex格式
            if event_type == "session_meta":
                payload = event.get("payload", {})
                cwd = payload.get("cwd")

        # Claude格式事件处理
        if event_type == "user":
            stats["user_messages"] += 1
            # 提取第一条用户消息
            if not first_user_msg:
                message = event.get("message", {})
                content = message.get("content", "")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            first_user_msg = item.get("text", "")[:200]
                elif isinstance(content, str):
                    first_user_msg = content[:200]
        elif event_type == "assistant":
            stats["assistant_messages"] += 1
            # 统计工具调用（在content数组中）
            message = event.get("message", {})
            content = message.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        stats["tool_calls"] += 1
                        tool_name = item.get("name", "")
                        if tool_name == "Read":
                            stats["read_count"] += 1
                        elif tool_name == "Edit":
                            stats["edit_count"] += 1
                        elif tool_name == "Write":
                            stats["write_count"] += 1
                        elif tool_name == "Bash":
                            stats["bash_count"] += 1
        elif event_type == "system":
            stats["system_messages"] += 1

        # Codex格式事件处理
        elif event_type == "response_item":
            payload = event.get("payload", {})
            payload_type = payload.get("type", "")
            content = payload.get("content", [])

            if payload_type == "message" and isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        item_type = item.get("type", "")
                        if item_type == "input_text":
                            stats["user_messages"] += 1
                            if not first_user_msg:
                                first_user_msg = item.get("text", "")[:200]
                        elif item_type == "output_text":
                            stats["assistant_messages"] += 1
                        elif item_type == "tool_call":
                            stats["tool_calls"] += 1

        # 提取主题
        if event_type == "ai-title" and not topic:
            topic = event.get("aiTitle", "")
        if event_type == "custom-title" and not topic:
            topic = event.get("customTitle", "")

        # 提取任务
        if event_type == "TaskCreate":
            task_data = event.get("task", {})
            tasks.append({
                "id": task_data.get("taskId"),
                "subject": task_data.get("subject"),
                "status": task_data.get("status"),
            })

    return {
        "topic": topic,
        "first_user_message": first_user_msg,
        "stats": stats,
        "tasks": tasks,
        "has_ai_title": topic is not None,
        "cwd": cwd,  # 真实cwd（从JSONL提取）
    }