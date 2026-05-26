# SessionFlow 远程会话管理规格说明书

## 1. 问题背景

### 1.1 当前限制

SessionFlow只能扫描本机Claude Code会话（~/.claude/projects/），无法管理远程Mac Mini上的会话。

### 1.2 用户场景

```
用户机器(MacBook)  ←──── SSH ────→  Mac Mini(开发机)

Mac Mini特点：
- Claude Code会话存储在 ~/.claude/projects/
- 会话可能运行在tmux中
- 启动方式: ssh claw-tmux
- 恢复需要: tmux attach 或 claude --resume
```

### 1.3 核心问题

1. **远程扫描**：如何扫描远程Mac Mini的会话？
2. **tmux识别**：如何识别会话是否在tmux中运行？
3. **恢复方式**：如何正确恢复tmux会话？
4. **并发控制**：如何避免重复连接导致的性能问题？

---

## 2. 数据模型扩展

### 2.1 RemoteHost（远程主机）

```python
@dataclass
class RemoteHost:
    id: str                 # host-001
    name: str               # "Mac Mini开发机"
    hostname: str           # 192.168.x.x 或 hostname
    user: str               # SSH用户名
    ssh_alias: str          # SSH别名（如 claw-tmux）
    claude_dir: str         # ~/.claude/projects/
    tmux_prefix: str        # tmux会话前缀（如 claude-）
    enabled: bool           # 是否启用扫描
    last_scan_at: int       # 上次扫描时间
```

### 2.2 SessionMeta扩展

```python
@dataclass
class SessionMeta:
    # ... 现有字段 ...
    host_type: str          # local/remote
    host_id: str            # 主机ID（remote时）
    tmux_session: str       # tmux会话名（如有）
    tmux_window: int        # tmux窗口号
```

### 2.3 TmuxSessionInfo

```python
@dataclass
class TmuxSessionInfo:
    session_name: str       # tmux会话名
    window_id: int          # 窗口ID
    pane_id: int            # 面板ID
    claude_session_id: str  # 关联的Claude session ID
    is_active: bool         # 是否有进程attached
    created_at: int
```

---

## 3. 远程扫描机制（已验证可行）

### 3.1 tmux → Claude Session映射扫描（核心算法）

**已验证的扫描逻辑**：

```bash
#!/bin/bash
# scan_tmux_claude_mapping.sh

echo "=== Step 1: 获取所有tmux会话 ==="
tmux_sessions=$(tmux list-sessions -F '#{session_name}' 2>/dev/null)

echo "=== Step 2: 对每个tmux会话，获取pane进程 ==="
for session in $tmux_sessions; do
    echo "Session: $session"
    
    # 获取所有pane的PID
    for pane_pid in $(tmux list-panes -a -t $session -F '#{pane_pid}' 2>/dev/null); do
        echo "  Pane PID: $pane_pid"
        
        # Step 3: 用lsof获取进程的cwd
        cwd=$(lsof -p $pane_pid 2>/dev/null | grep cwd | awk '{print $NF}')
        echo "    CWD: $cwd"
        
        # Step 4: 检查是否是Claude进程
        cmd=$(ps -p $pane_pid -o command= 2>/dev/null)
        if [[ "$cmd" == *"claude"* ]]; then
            echo "    *** 找到Claude进程! ***"
            
            # Step 5: 根据cwd找到对应的Claude session目录
            # 目录名格式: -Users-claw-sandbox-... → 对应 /Users/claw/sandbox/...
            session_dir=$(echo "$cwd" | sed 's/\//-/g' | sed 's/^/-/')
            
            # Step 6: 找最新修改的jsonl文件
            latest_jsonl=$(ls -t ~/.claude/projects/${session_dir}/*.jsonl 2>/dev/null | head -1)
            if [ -n "$latest_jsonl" ]; then
                session_id=$(basename "$latest_jsonl" .jsonl)
                echo "    Session ID: $session_id"
                echo "    TMUX Mapping: $session → $session_id"
                
                # 输出映射关系
                echo "$session_id:$session:$pane_pid"
            fi
        fi
    done
done
```

**Python实现**：

```python
def scan_tmux_claude_mapping(host: Optional[RemoteHost] = None) -> Dict[str, TmuxMapping]:
    """扫描tmux会话与Claude session的映射关系"""
    
    ssh_prefix = ""
    if host:
        ssh_prefix = f"ssh {host.user}@{host.hostname}"
    
    mappings = {}
    
    # Step 1: 获取所有tmux会话
    result = subprocess.run(
        f"{ssh_prefix} tmux list-sessions -F '{{session_name}}'",
        shell=True, capture_output=True, text=True
    )
    tmux_sessions = result.stdout.strip().split('\n')
    
    for session_name in tmux_sessions:
        if not session_name:
            continue
        
        # Step 2: 获取该session的所有pane PID
        result = subprocess.run(
            f"{ssh_prefix} tmux list-panes -a -t {session_name} -F '{{pane_pid}}'",
            shell=True, capture_output=True, text=True
        )
        pane_pids = result.stdout.strip().split('\n')
        
        for pane_pid in pane_pids:
            if not pane_pid:
                continue
            
            # Step 3: 用lsof获取cwd
            result = subprocess.run(
                f"{ssh_prefix} lsof -p {pane_pid} | grep cwd | awk '{{print $NF}}'",
                shell=True, capture_output=True, text=True
            )
            cwd = result.stdout.strip()
            
            if not cwd:
                continue
            
            # Step 4: 检查是否是Claude进程
            result = subprocess.run(
                f"{ssh_prefix} ps -p {pane_pid} -o command=",
                shell=True, capture_output=True, text=True
            )
            cmd = result.stdout.strip()
            
            if "claude" in cmd or "codex" in cmd:
                # Step 5: 根据cwd找session目录
                # encode_path逻辑
                session_dir_name = encode_path(cwd)
                
                # Step 6: 找最新jsonl文件
                result = subprocess.run(
                    f"{ssh_prefix} ls -t ~/.claude/projects/{session_dir_name}/*.jsonl | head -1",
                    shell=True, capture_output=True, text=True
                )
                jsonl_path = result.stdout.strip()
                
                if jsonl_path:
                    session_id = Path(jsonl_path).stem
                    
                    mappings[session_id] = TmuxMapping(
                        tmux_session_name=session_name,
                        tmux_window_id=0,
                        pane_pid=int(pane_pid),
                        is_attached=True  # 可进一步检查
                    )
    
    return mappings
```

### 3.2 已验证的实际映射数据

**Mac Mini (192.168.100.181) 扫描结果**：

| tmux会话名 | tty | cwd | Claude PID | Claude Session ID |
|-----------|-----|-----|------------|-------------------|
| AI资讯 | s007 | /Users/claw/sandbox | 53432 | `27e0e758-6dfc-43fe-a2cb-5d3b1a26c0f1` |
| ELK故障分析 | s005 | /Users/claw/sandbox/personal/loghunter | 92534 | `eb248e7f-92f7-46a6-aa13-25a8cd85c47e` |
| 多线程任务优化 | s003 | /Users/claw/sandbox/labs/hjly-common-governance | 24628 | `35b3efda-ceb2-4e56-8294-7269057a700d` |
| codex-支付出金优化 | s001 | - | 73282 (node) | `019e5e0f-81d9-7270-b1e1-c11e820e1130` (Codex) |

### 3.3 SSH远程扫描流程

```
1. 读取remote_hosts.json配置
2. 对每个启用的远程主机：
   a. SSH连接执行扫描脚本
   b. 执行: ls ~/.claude/projects/*/session.json
   c. 执行: tmux list-sessions | grep claude-
   d. 返回JSON格式会话数据
3. 合并本地+远程会话列表
```

### 3.2 远程扫描脚本

```bash
#!/bin/bash
# scan_remote_sessions.sh

# 扫描Claude会话
claude_sessions=$(find ~/.claude/projects -name "*.jsonl" -exec basename {} .jsonl \;)

# 扫描tmux会话
tmux_sessions=$(tmux list-sessions -F "#{session_name}:#{session_windows}" 2>/dev/null | grep "claude-" || echo "")

# 输出JSON
echo "{\"claude_sessions\": $claude_sessions, \"tmux_sessions\": \"$tmux_sessions\"}"
```

### 3.3 SSH连接方式

```python
import subprocess

def scan_remote_host(host: RemoteHost) -> List[SessionRecord]:
    """扫描远程主机会话"""
    # 使用SSH别名或完整hostname
    ssh_target = host.ssh_alias or f"{host.user}@{host.hostname}"

    # 执行远程扫描脚本
    cmd = f"ssh {ssh_target} 'find ~/.claude/projects -name \"*.jsonl\"'"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    # 解析结果，构建SessionRecord
    sessions = []
    for jsonl_path in result.stdout.strip().split('\n'):
        # 远程路径格式: ~/.claude/projects/-Users-xxx-.../session-id.jsonl
        # 需要解析session_id和cwd
        ...
    return sessions
```

---

## 4. tmux会话管理

### 4.1 tmux会话识别

```bash
# 查看所有tmux会话
tmux list-sessions

# 查看特定会话的窗口
tmux list-windows -t claude-session-name

# 查看窗口中的进程
tmux list-panes -t claude-session-name:0 -F "#{pane_current_command}"
```

### 4.2 判断会话是否在tmux中

方法一：检查TMUX环境变量
```bash
# 在Claude会话中执行
if [ -n "$TMUX" ]; then
    echo "In tmux: $TMUX"
fi
```

方法二：扫描时标记
```python
# 扫描远程时同时查询tmux状态
tmux_check = subprocess.run(
    f"ssh {host} 'tmux has-session -t claude-{session_id} && echo yes || echo no'",
    shell=True, capture_output=True
)
in_tmux = tmux_check.stdout.strip() == "yes"
```

### 4.3 tmux会话恢复方式

```bash
# 方式A: 创建新tmux会话并启动Claude
ssh claw-tmux
tmux new -s claude-{session_id} -c {cwd}
claude --resume {session_id}

# 方式B: attach到已有tmux会话
ssh claw-tmux
tmux attach -t claude-{session_id}

# 方式C: 在已有tmux会话中新建窗口
ssh claw-tmux
tmux new-window -t claude-main -c {cwd}
claude --resume {session_id}
```

---

## 5. 会话恢复机制（已验证可行）

### 5.1 恢复逻辑（核心算法）

**用户需求**：
- 打开session时，检查是否已有tmux连接
- 有 → 直接attach到已有tmux（不新建）
- 无 → 创建新tmux并恢复Claude

**恢复流程**：

```python
def recover_remote_session(session: SessionRecord, host: RemoteHost) -> bool:
    """恢复远程会话 - 去重逻辑"""
    
    # Step 1: 执行扫描，获取tmux映射
    mappings = scan_tmux_claude_mapping(host)
    
    # Step 2: 检查该session是否已有tmux连接
    tmux_info = mappings.get(session.meta.session_id)
    
    if tmux_info:
        # 已有tmux连接 → 直接attach
        print(f"发现已有tmux连接: {tmux_info.tmux_session_name}")
        
        # 方式A: 通过ssh claw-tmux交互式选择
        # 方式B: 直接SSH并attach
        cmd = f"ssh {host.user}@{host.hostname} 'tmux attach -t {tmux_info.tmux_session_name}'"
        
        # 本机iTerm2执行
        applescript = f'''
        tell application "iTerm"
            activate
            create window with default profile
            tell current session of current window
                write text "{cmd}"
            end tell
        end tell
        '''
        subprocess.run(['osascript', '-e', applescript])
        
        return True
    
    else:
        # 无tmux连接 → 创建新tmux并恢复
        
        # 方式A: 先SSH连接，手动选择tmux会话名
        # 方式B: 自动创建命名tmux
        
        # 先cd到cwd，再启动Claude
        cmd1 = f"cd '{session.meta.cwd}'"
        cmd2 = f"claude --resume {session.meta.session_id}"
        
        applescript = f'''
        tell application "iTerm"
            activate
            create window with default profile
            tell current session of current window
                write text "ssh {host.user}@{host.hostname}"
                delay 1
                write text "tmux new -s claude-{session.meta.session_id[:8]}"
                write text "{cmd1}"
                write text "{cmd2}"
            end tell
        end tell
        '''
        subprocess.run(['osascript', '-e', applescript])
        
        return True
```

### 5.2 恢复方式对比

| 场景 | 已有tmux | 恢复方式 | 命令 |
|------|---------|----------|------|
| AI资讯 session | ✅ 有 | attach已有 | `ssh claw@192.168.100.181 && tmux attach -t "AI资讯"` |
| 新session | ❌ 无 | 创建新tmux | `ssh claw@192.168.100.181 && tmux new -s "新名" -c /cwd && claude --resume id` |

### 5.3 AppleScript实现（本地iTerm2 → 远程Mac Mini）

**attach已有tmux**：

```applescript
tell application "iTerm"
    activate
    create window with default profile
    tell current session of current window
        write text "ssh claw@192.168.100.181"
        delay 1
        write text "tmux attach -t 'AI资讯'"
    end tell
end tell
```

**创建新tmux并恢复**：

```applescript
tell application "iTerm"
    activate
    create window with default profile
    tell current session of current window
        write text "ssh claw@192.168.100.181"
        delay 1
        write text "tmux new -s 'claude-abc123' -c '/Users/claw/sandbox/project'"
        write text "claude --resume abc123"
    end tell
end tell
```

### 5.4 并发控制（去重而非限制）

### 5.1 会话状态检测

```python
def check_session_active(host: RemoteHost, session_id: str) -> bool:
    """检测会话是否已有活跃连接"""
    # 检查tmux会话是否有attached客户端
    cmd = f"ssh {host.ssh_alias} 'tmux list-sessions -F \"#{session_name}:#{session_attached}\"'"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    for line in result.stdout.strip().split('\n'):
        name, attached = line.split(':')
        if name == f"claude-{session_id}" and int(attached) > 0:
            return True
    return False
```

### 5.2 活跃会话限制

```python
# 配置
MAX_REMOTE_SESSIONS = 3  # 最大同时活跃会话数
MAX_TMUX_WINDOWS = 5     # 单tmux会话最大窗口数

def get_active_count(host: RemoteHost) -> int:
    """获取当前活跃会话数"""
    cmd = f"ssh {host.ssh_alias} 'tmux list-sessions | wc -l'"
    result = subprocess.run(cmd, shell=True, capture_output=True)
    return int(result.stdout.strip())
```

### 5.3 恢复策略

```
打开远程会话时：
1. 检查会话是否已活跃
   → 已活跃: 提示"会话已运行，是否attach？"
   → 未活跃: 继续检查并发限制

2. 检查当前活跃数是否超限
   → 超限: 提示"已有{N}个活跃会话，建议关闭部分后继续"
   → 未超限: 执行恢复

3. 选择恢复方式
   → 有tmux会话: tmux attach
   → 无tmux会话: tmux new + claude --resume
```

---

## 6. Web界面远程会话

### 6.1 远程会话标识

```
session列表中区分：
┌──────────────────────────────────┐
│ session-A  [本地]  🔵 进行中     │
│ session-B  [Mac Mini]  ⚪ 闲置   │
│ session-C  [Mac Mini] 🟡 tmux    │
└──────────────────────────────────┘
```

### 6.2 远程会话打开按钮

```
详情页操作按钮：
[🚀 打开本地会话]   → 本地session，本地iTerm2
[🔌 打开远程会话]   → 远程session，SSH+tmux

远程打开流程：
1. SSH连接到远程主机
2. 检查tmux状态
3. cd到项目目录
4. 恢复Claude会话
```

### 6.3 远程会话详情页

```
┌─────────────────────────────────┐
│ 📍 远程主机: Mac Mini           │
│ 🖥️ tmux会话: claude-session-A  │
│ ⚡ 状态: 1个客户端attached       │
│                                 │
│ [attach到tmux] [kill会话]       │
└─────────────────────────────────┘
```

---

## 7. 存储结构扩展

```
~/.sessionflow/
├── remote_hosts.json      # 远程主机配置
├── remote_sessions.json   # 远程会话缓存
├── requirements.json
├── ...
```

### 7.1 remote_hosts.json示例

```json
{
  "hosts": [
    {
      "id": "host-001",
      "name": "Mac Mini开发机",
      "hostname": "192.168.100.181",
      "ssh_alias": "claw-tmux",
      "claude_dir": "~/.claude/projects/",
      "tmux_prefix": "claude-",
      "enabled": true
    }
  ]
}
```

---

## 8. CLI命令扩展

```bash
# 远程主机管理
sessionflow host add "Mac Mini" --alias claw-tmux
sessionflow host list
sessionflow host scan host-001

# 远程会话查看
sessionflow list --remote     # 包含远程会话
sessionflow list --host host-001  # 仅指定主机

# 远程会话打开
sessionflow open <session-id> --remote
sessionflow open <session-id> --tmux attach
```

---

## 9. 安全考虑

### 9.1 SSH密钥认证

- 要求SSH密钥已配置，避免密码交互
- 使用SSH别名简化连接

### 9.2 会话隔离

- 每个远程会话独立tmux session或窗口
- 避免在同一tmux会话中混用多个Claude会话

### 9.3 并发警告

- 活跃会话超限时警告用户
- 提供kill命令清理僵尸会话

---

## 10. 实现计划

### Phase 1: 远程扫描 (3h)
- RemoteHost数据模型
- SSH远程扫描实现
- 合并本地+远程会话列表

### Phase 2: tmux集成 (3h)
- tmux会话识别
- tmux attach/new逻辑
- 并发控制机制

### Phase 3: Web界面 (2h)
- 远程会话标识
- 远程打开按钮
- 活跃状态显示

### Phase 4: CLI命令 (2h)
- host add/list/scan命令
- open --remote/--tmux选项

**总工作量**: 约10小时

---

## 11. 设计决策

### 11.1 为什么用SSH而非Agent？

- SSH已配置，无需额外安装
- 执行简单脚本即可获取数据
- Agent方案需要额外开发+部署

### 11.2 为什么限制并发？

- Claude Code消耗资源较多
- 避免远程主机性能下降
- 用户可控，默认限制3个

### 11.3 为什么用tmux？

- 用户已有tmux使用习惯
- tmux支持会话持久化
- 可在断开后保持Claude运行