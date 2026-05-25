# SessionFlow

Claude Code会话管理工具 - 解决会话丢失痛点

## 功能

- `sessionflow scan` - 扫描所有Claude Code会话
- `sessionflow list` - 列出会话（支持--project, --status过滤）
- `sessionflow open <id>` - 打开指定会话（支持前缀匹配）
- `sessionflow status` - 显示当前活跃会话
- `sessionflow recover` - 生成恢复链接

## 使用

```bash
cd /Users/ada/bin/sessionflow
python3 sessionflow.py scan
python3 sessionflow.py list
python3 sessionflow.py open f2647cfd --copy
```

## 测试结果

```
$ python3 sessionflow.py scan
扫描完成，发现 6 个会话

$ python3 sessionflow.py list
共 6 个会话:
🔵 f2647cfd | ada/bin | busy
⚪ 9b5c9bfd | ada/workspace-payment | idle
...

$ python3 sessionflow.py status
当前活跃会话 (1 个):
  f2647cfd... | ada/bin

$ python3 sessionflow.py recover
所有会话恢复链接:
  c280a171... | claude --resume c280a171-a471-4549-bd05-0349c95dbaf2
...
```

## 下一步

- Phase 1: Tauri桌面应用（系统托盘常驻）
- 进度自动分析（analyze命令）
- 甘特图/时间管理界面