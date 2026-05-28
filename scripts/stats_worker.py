#!/usr/bin/env python3
"""远程统计脚本 - 在远程主机上运行，计算 JSONL 统计并返回 JSON

用法：
    python3 stats_worker.py <jsonl_path>
    python3 stats_worker.py --multi <jsonl_path1> <jsonl_path2> ...

输出：
    JSON 格式的统计结果（单文件）或批量结果（多文件）
"""

import json
import sys
from pathlib import Path


def get_jsonl_stats(jsonl_path: str) -> dict:
    """计算单个 JSONL 文件的统计"""
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
    cwd = None

    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    stats["total_events"] += 1
                    event_type = event.get("type", "")

                    # 提取 cwd
                    if not cwd and "cwd" in event:
                        cwd = event.get("cwd")

                    # 提取 topic
                    if event_type == "ai-title" and not topic:
                        topic = event.get("aiTitle", "")
                    if event_type == "custom-title" and not topic:
                        topic = event.get("customTitle", "")

                    if event_type == "user":
                        stats["user_messages"] += 1
                    elif event_type == "assistant":
                        stats["assistant_messages"] += 1
                        # 统计工具调用
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
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        return {"error": str(e)}

    result = {"stats": stats}
    if topic:
        result["topic"] = topic
    if cwd:
        result["cwd"] = cwd
    return result


def batch_stats(paths: list) -> dict:
    """批量计算多个 JSONL 文件的统计"""
    results = {}
    for path in paths:
        if path and Path(path).exists():
            session_id = Path(path).stem
            results[session_id] = get_jsonl_stats(path)
    return results


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: stats_worker.py <jsonl_path>"}))
        sys.exit(1)

    if sys.argv[1] == "--multi":
        # 批量模式：传入多个路径
        paths = sys.argv[2:]
        if not paths:
            print(json.dumps({"error": "Usage: stats_worker.py --multi <path1> <path2> ..."}))
            sys.exit(1)
        result = batch_stats(paths)
    else:
        # 单文件模式
        result = get_jsonl_stats(sys.argv[1])

    print(json.dumps(result))


if __name__ == "__main__":
    main()