#!/usr/bin/env python3
"""
Mem0数据库切换工具
帮助您在不同的数据库配置之间轻松切换
"""
import os
import json
import shutil
import argparse
from pathlib import Path

def get_available_configs():
    """获取可用的数据库配置"""
    return {
        "qdrant": {
            "name": "Qdrant (当前默认)",
            "description": "高性能向量搜索引擎",
            "docker_compose": "docker-compose.yaml",
            "main_file": "main.py"
        },
        "postgresql": {
            "name": "PostgreSQL + pgvector",
            "description": "关系型数据库 + 向量扩展",
            "docker_compose": "docker-compose.postgresql.yaml",
            "main_file": "main_postgresql.py"
        },
        "mongodb": {
            "name": "MongoDB",
            "description": "文档型NoSQL数据库",
            "docker_compose": "docker-compose.mongodb.yaml",
            "main_file": "main_mongodb.py"
        }
    }

def show_configs():
    """显示所有可用配置"""
    configs = get_available_configs()

    print("🗄️  可用的数据库配置:")
    print("=" * 60)

    for key, config in configs.items():
        print(f"  {key:12} - {config['name']}")
        print(f"               {config['description']}")
        print()

def backup_current_config():
    """备份当前配置"""
    project_root = Path(__file__).parent.parent

    backup_dir = project_root / "backups"
    backup_dir.mkdir(exist_ok=True)

    # 备份docker-compose.yaml
    docker_compose = project_root / "docker-compose.yaml"
    if docker_compose.exists():
        backup_compose = backup_dir / "docker-compose.yaml.backup"
        shutil.copy2(docker_compose, backup_compose)
        print(f"✅ 已备份docker-compose.yaml到 {backup_compose}")

    # 备份server/main.py
    main_py = project_root / "server" / "main.py"
    if main_py.exists():
        backup_main = backup_dir / "main.py.backup"
        shutil.copy2(main_py, backup_main)
        print(f"✅ 已备份main.py到 {backup_main}")

def switch_to_config(config_name):
    """切换到指定配置"""
    configs = get_available_configs()

    if config_name not in configs:
        print(f"❌ 未知配置: {config_name}")
        print("可用配置:", list(configs.keys()))
        return False

    config = configs[config_name]
    project_root = Path(__file__).parent.parent
    test_dir = Path(__file__).parent

    print(f"🔄 切换到 {config['name']}...")

    # 备份当前配置
    backup_current_config()

    # 复制docker-compose文件
    source_compose = test_dir / config['docker_compose']
    target_compose = project_root / "docker-compose.yaml"

    if source_compose.exists():
        shutil.copy2(source_compose, target_compose)
        print(f"✅ 已更新docker-compose.yaml")
    else:
        print(f"⚠️ 警告: {source_compose} 不存在")

    # 复制main.py文件
    source_main = test_dir / config['main_file']
    target_main = project_root / "server" / "main.py"

    if source_main.exists():
        shutil.copy2(source_main, target_main)
        print(f"✅ 已更新server/main.py")
    else:
        print(f"⚠️ 警告: {source_main} 不存在")

    print(f"🎉 成功切换到 {config['name']}!")

    # 显示下一步操作建议
    print("\n📋 下一步操作:")
    if config_name == "postgresql":
        print("1. 确保已安装PostgreSQL或使用Docker:")
        print("   docker-compose up -d postgres")
        print("2. 安装pgvector扩展 (如果使用本地PostgreSQL)")
        print("3. 更新环境变量中的数据库连接信息")
        print("4. 重启服务:")
        print("   docker-compose up -d mem0-service")
    elif config_name == "qdrant":
        print("1. 启动Qdrant服务:")
        print("   docker-compose up -d qdrant")
        print("2. 重启Mem0服务:")
        print("   docker-compose up -d mem0-service")

    return True

def create_env_template(config_name):
    """创建环境变量模板"""
    configs = get_available_configs()

    if config_name not in configs:
        print(f"❌ 未知配置: {config_name}")
        return

    templates = {
        "postgresql": """
# PostgreSQL配置
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=mem0_db
POSTGRES_USER=mem0_user
POSTGRES_PASSWORD=mem0_password
POSTGRES_COLLECTION=memories
EMBEDDING_MODEL_DIMS=1536

# API Keys
DEEPSEEK_API_KEY=your_deepseek_api_key
OPENAI_API_KEY=your_openai_api_key

# 其他配置
HISTORY_DB_PATH=/app/history/history.db
""",
        "qdrant": """
# Qdrant配置
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=memories

# API Keys
DEEPSEEK_API_KEY=your_deepseek_api_key
OPENAI_API_KEY=your_openai_api_key

# 其他配置
HISTORY_DB_PATH=/app/history/history.db
"""
    }

    if config_name in templates:
        template_file = Path(__file__).parent / f".env1.{config_name}.template"
        with open(template_file, 'w') as f:
            f.write(templates[config_name].strip())
        print(f"✅ 已创建环境变量模板: {template_file}")
        print("💡 请复制到.env文件并填入实际值")

def main():
    parser = argparse.ArgumentParser(description="Mem0数据库配置切换工具")
    parser.add_argument("command", choices=["list", "switch", "env"], help="操作命令")
    parser.add_argument("--config", help="配置名称 (用于switch和env命令)")

    args = parser.parse_args()

    if args.command == "list":
        show_configs()

    elif args.command == "switch":
        if not args.config:
            print("❌ 请指定配置名称: --config <config_name>")
            show_configs()
            return
        switch_to_config(args.config)

    elif args.command == "env":
        if not args.config:
            print("❌ 请指定配置名称: --config <config_name>")
            return
        create_env_template(args.config)

if __name__ == "__main__":
    main()