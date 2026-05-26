#!/bin/bash
# SessionFlow 测试脚本
# 创建虚拟环境并运行测试

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv-test"

# 创建虚拟环境（如果不存在）
if [ ! -d "$VENV_DIR" ]; then
    echo "创建测试虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 安装依赖
echo "安装测试依赖..."
pip install --quiet pytest pytest-cov flask

# 运行测试
echo "运行测试..."
cd "$SCRIPT_DIR"
pytest tests/ -v --cov=core --cov=providers --cov=sessionflow --cov-report=term-missing

echo "测试完成！"