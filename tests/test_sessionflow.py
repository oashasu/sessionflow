"""SessionFlow 单元测试（使用unittest标准库）"""

import unittest
from pathlib import Path
import json
import tempfile
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import SessionMeta, SessionRecord, extract_project_name
from core.scanner import scan_sessions, parse_session_json
from core.recovery import (
    generate_recovery_cmd,
    find_jsonl_path,
    encode_path,
    validate_session_id,
    validate_path,
)
from core.parser import parse_jsonl_file


class TestModels(unittest.TestCase):
    """测试数据模型"""

    def test_session_meta_creation(self):
        """测试SessionMeta创建"""
        meta = SessionMeta(
            session_id="abc123",
            cwd="/Users/test/project",
            status="busy",
            started_at=1000,
            updated_at=2000,
        )
        self.assertEqual(meta.session_id, "abc123")
        self.assertEqual(meta.status, "busy")

    def test_session_record_short_id(self):
        """测试短ID生成"""
        meta = SessionMeta(
            session_id="abcdefgh12345678",
            cwd="/test",
            status="idle",
            started_at=0,
            updated_at=0,
        )
        record = SessionRecord(meta=meta, project_name="test")
        self.assertEqual(record.short_id, "abcdefgh")

    def test_extract_project_name(self):
        """测试项目名提取"""
        self.assertEqual(extract_project_name("/Users/ada/bin"), "ada/bin")
        self.assertEqual(extract_project_name("/home/user/workspace/project"), "workspace/project")


class TestRecovery(unittest.TestCase):
    """测试恢复逻辑"""

    def test_generate_recovery_cmd(self):
        """测试恢复命令生成"""
        cmd = generate_recovery_cmd("abc123", "/test/path")
        self.assertEqual(cmd, "claude --resume abc123")

    def test_encode_path(self):
        """测试路径编码"""
        self.assertEqual(encode_path("/Users/ada/bin"), "-Users-ada-bin")
        self.assertEqual(encode_path("/home/user/project"), "-home-user-project")

    def test_find_jsonl_path_returns_none_for_nonexistent(self):
        """测试不存在路径返回None"""
        result = find_jsonl_path("nonexistent", "/nonexistent/path")
        self.assertIsNone(result)

    def test_validate_session_id_valid(self):
        """测试合法UUID验证"""
        valid_uuid = "f2647cfd-a87f-47f2-8c12-238f0c9594a7"
        self.assertTrue(validate_session_id(valid_uuid))

    def test_validate_session_id_invalid(self):
        """测试非法UUID验证"""
        invalid_uuid = "not-a-uuid"
        self.assertFalse(validate_session_id(invalid_uuid))

    def test_validate_path_in_home(self):
        """测试合法路径验证"""
        home_path = str(Path.home())
        self.assertTrue(validate_path(home_path))

    def test_validate_path_outside_home(self):
        """测试非法路径验证"""
        self.assertFalse(validate_path("/etc/passwd"))


class TestScanner(unittest.TestCase):
    """测试扫描逻辑"""

    def test_parse_session_json(self):
        """测试JSON解析"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "sessionId": "test-id-123",
                "cwd": "/test/path",
                "status": "idle",
                "startedAt": 1000,
                "updatedAt": 2000,
            }, f)
            temp_path = Path(f.name)

        meta = parse_session_json(temp_path)
        self.assertEqual(meta.session_id, "test-id-123")
        self.assertEqual(meta.cwd, "/test/path")
        self.assertEqual(meta.status, "idle")

        temp_path.unlink()


class TestParser(unittest.TestCase):
    """测试解析逻辑"""

    def test_parse_jsonl_file_empty(self):
        """测试空JSONL文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write("")
            temp_path = Path(f.name)

        events = list(parse_jsonl_file(temp_path))
        self.assertEqual(events, [])

        temp_path.unlink()

    def test_parse_jsonl_file_valid(self):
        """测试有效JSONL文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type": "human", "content": "test"}\n')
            f.write('{"type": "assistant", "content": "response"}\n')
            temp_path = Path(f.name)

        events = list(parse_jsonl_file(temp_path))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["type"], "human")

        temp_path.unlink()

    def test_parse_jsonl_file_malformed(self):
        """测试畸形JSONL跳过"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"type": "human"}\n')
            f.write('invalid json line\n')
            f.write('{"type": "assistant"}\n')
            temp_path = Path(f.name)

        events = list(parse_jsonl_file(temp_path))
        self.assertEqual(len(events), 2)  # 跳过畸形行

        temp_path.unlink()


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_scan_sessions_real_data(self):
        """测试扫描真实数据"""
        sessions = scan_sessions()
        self.assertIsInstance(sessions, list)
        self.assertGreater(len(sessions), 0)

    def test_all_sessions_have_recovery_cmd(self):
        """测试所有会话都有恢复命令"""
        sessions = scan_sessions()
        for session in sessions:
            self.assertTrue(session.recovery_cmd.startswith("claude --resume"))


if __name__ == "__main__":
    unittest.main(verbosity=2)