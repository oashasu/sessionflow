"""会话扫描逻辑"""

import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from .models import SessionMeta, SessionRecord, extract_project_name
from .recovery import generate_recovery_cmd, find_jsonl_path, encode_path, PROJECTS_DIR
from .parser import find_ai_title, get_jsonl_summary, parse_jsonl_file


SESSIONS_DIR = Path.home() / ".claude" / "sessions"


def scan_sessions() -> List[SessionRecord]:
    """扫描活跃会话（sessions/*.json）"""
    sessions = []

    if not SESSIONS_DIR.exists():
        return sessions

    for json_file in SESSIONS_DIR.glob("*.json"):
        try:
            meta = parse_session_json(json_file)
            if meta:
                project_name = extract_project_name(meta.cwd)
                log_path = find_jsonl_path(meta.session_id, meta.cwd)
                recovery_cmd = generate_recovery_cmd(meta.session_id, meta.cwd)

                # 提取主题
                topic = None
                if log_path:
                    topic = find_ai_title(Path(log_path))

                record = SessionRecord(
                    meta=meta,
                    project_name=project_name,
                    log_path=log_path,
                    recovery_cmd=recovery_cmd,
                    topic=topic,
                )
                sessions.append(record)
        except Exception as e:
            # 跳过解析失败的文件
            continue

    return sessions


def scan_all_sessions() -> List[SessionRecord]:
    """扫描所有会话（包括历史会话）- 从projects目录扫描JSONL文件"""
    sessions = []

    # 1. 先获取活跃会话（可恢复）
    active_sessions = scan_sessions()
    active_ids = {s.meta.session_id for s in active_sessions}
    sessions.extend(active_sessions)

    # 2. 扫描所有JSONL文件获取历史会话
    if not PROJECTS_DIR.exists():
        return sessions

    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue

        # 从目录名解码工作目录
        cwd = decode_project_dir(project_dir.name)

        # 只扫描第一级目录下的JSONL文件（跳过子目录如subagents）
        for jsonl_file in project_dir.glob("*.jsonl"):
            session_id = jsonl_file.stem  # 文件名就是session_id

            # 跳过已添加的活跃会话
            if session_id in active_ids:
                continue

            try:
                # 从JSONL提取完整摘要
                summary = get_jsonl_summary(jsonl_file)
                topic = summary.get("topic") or summary.get("first_user_message")
                stats = summary.get("stats", {})

                # 创建虚拟meta（历史会话无法恢复，只能查看）
                meta = SessionMeta(
                    session_id=session_id,
                    cwd=cwd,
                    status="closed",  # 已关闭
                    started_at=0,
                    updated_at=int(jsonl_file.stat().st_mtime * 1000),
                )

                record = SessionRecord(
                    meta=meta,
                    project_name=extract_project_name(cwd),
                    log_path=str(jsonl_file),
                    recovery_cmd="",  # 已关闭会话无法恢复
                    topic=translate_topic(topic),
                )
                # 附加统计数据
                record.stats = stats
                sessions.append(record)
            except Exception:
                continue

    return sessions


def translate_topic(topic: str) -> str:
    """翻译主题为中文（简单关键词匹配）"""
    if not topic:
        return "无主题"

    # 简单关键词翻译映射
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

    # 如果翻译后还是英文为主，标记为需人工翻译
    if result == topic and any(c.isalpha() and ord(c) < 128 for c in topic):
        # 尝试提取关键信息
        return topic  # 暂时保留原文，后续可接入翻译API

    return result


def decode_project_dir(encoded: str) -> str:
    """解码项目目录名回原始路径"""
    # -Users-ada-bin -> /Users/ada/bin
    if encoded.startswith("-"):
        path = encoded[1:]  # 移除开头的-
        path = path.replace("-", "/")
        return "/" + path
    return encoded


def extract_jsonl_info(jsonl_path: Path) -> Dict[str, Any]:
    """从JSONL文件提取统计信息、主题和时间戳"""
    stats = {"total_events": 0, "tool_calls": 0, "user_messages": 0}
    topic = None
    timestamps = {"started_at": 0, "updated_at": 0}

    first_timestamp = None
    last_timestamp = None

    for event in parse_jsonl_file(jsonl_path):
        stats["total_events"] += 1
        event_type = event.get("type", "")

        if event_type == "tool_use":
            stats["tool_calls"] += 1
        elif event_type == "human":
            stats["user_messages"] += 1
        elif event_type == "ai-title":
            topic = event.get("aiTitle", "")

        # 提取时间戳
        ts = event.get("timestamp")
        if ts:
            if first_timestamp is None:
                first_timestamp = ts
            last_timestamp = ts

    if first_timestamp:
        # 尝试解析ISO格式时间戳
        try:
            dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
            timestamps["started_at"] = int(dt.timestamp() * 1000)
        except Exception:
            timestamps["started_at"] = 0

    if last_timestamp:
        try:
            dt = datetime.fromisoformat(last_timestamp.replace("Z", "+00:00"))
            timestamps["updated_at"] = int(dt.timestamp() * 1000)
        except Exception:
            timestamps["updated_at"] = 0

    return stats, topic, timestamps


def parse_session_json(json_path: Path) -> SessionMeta:
    """解析会话JSON文件"""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    return SessionMeta(
        session_id=data.get("sessionId", ""),
        cwd=data.get("cwd", ""),
        status=data.get("status", "idle"),
        started_at=data.get("startedAt", 0),
        updated_at=data.get("updatedAt", 0),
        pid=data.get("pid"),
        version=data.get("version"),
    )


def get_active_sessions() -> List[SessionRecord]:
    """获取活跃会话"""
    sessions = scan_sessions()
    return [s for s in sessions if s.meta.status == "busy"]


def get_sessions_by_project(project_name: str) -> List[SessionRecord]:
    """按项目获取会话"""
    sessions = scan_sessions()
    return [s for s in sessions if project_name in s.project_name]