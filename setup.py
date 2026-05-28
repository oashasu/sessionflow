#!/usr/bin/env python3
"""SessionFlow安装配置"""

from setuptools import setup, find_packages

setup(
    name="sessionflow",
    version="0.1.0",
    description="Claude Code会话管理工具",
    author="SessionFlow Team",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "sessionflow=cli:main",
        ],
    },
    python_requires=">=3.10",
    install_requires=[
        "rich>=13.0.0",
    ],
    extras_require={
        "web": ["flask>=3.0.0"],
    },
)