#!/bin/bash
# SessionFlow启动脚本

cd "$(dirname "$0")"

echo "SessionFlow Web界面启动..."
echo "访问: http://127.0.0.1:5000"
echo "按 Ctrl+C 停止"

python3 web/app.py