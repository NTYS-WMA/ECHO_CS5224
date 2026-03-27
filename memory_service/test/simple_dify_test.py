#!/usr/bin/env python3
"""
简单的Dify测试脚本 - 快速验证Flow是否正常工作
"""
import json
import time
import httpx

def load_config():
    """加载配置"""
    try:
        with open('dify_config.json', 'r') as f:
            return json.load(f)
    except:
        return {}

def test_dify_chat(message="你好，请简单介绍一下你自己"):
    """
    快速测试Dify聊天功能

    Args:
        message: 要发送的测试消息

    Returns:
        测试结果
    """
    config = load_config()
    api_key = config.get('api_key')
    base_url = config.get('base_url', 'http://localhost')

    if not api_key:
        print("❌ 错误：未找到API key")
        return False

    print(f"🚀 测试消息: {message}")
    print(f"🔗 连接到: {base_url}")

    # 发送请求
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{base_url}/v1/chat-messages",
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    "inputs": {},
                    "query": message,
                    "user": "simple_tester",
                    "response_mode": "blocking"
                }
            )

            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', '').strip()

                print("✅ 测试成功！")
                print(f"🤖 AI回复: {answer}")
                print(f"⏱️ 响应时间: {response.elapsed.total_seconds():.2f}秒")
                return True

            else:
                print(f"❌ HTTP错误: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   错误信息: {error_data.get('message', 'Unknown error')}")
                except:
                    print(f"   错误信息: {response.text}")
                return False

    except Exception as e:
        print(f"❌ 连接失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("🎯 Dify Flow 快速测试")
    print("=" * 40)

    # 运行测试
    success = test_dify_chat()

    print("\n" + "=" * 40)
    if success:
        print("🎉 您的Dify Flow工作正常！")
    else:
        print("⚠️ 测试失败，请检查配置和网络连接")