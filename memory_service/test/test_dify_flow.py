#!/usr/bin/env python3
"""
专门测试Dify Flow的脚本
用于测试简单的LLM调用flow，验证基本的聊天功能
"""
import os
import json
import time
import logging
from typing import Dict, Any, Optional, List
import httpx

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DifyFlowTester:
    """Dify Flow测试器"""

    def __init__(self, api_key: str, base_url: str = "http://localhost"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')

        # 从API key提取app_id
        self.app_id = api_key.replace('app-', '') if api_key.startswith('app-') else api_key

        self.client = httpx.Client(
            base_url=self.base_url,
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'DifyFlowTester/1.0'
            },
            timeout=60.0  # 增加超时时间，因为LLM调用可能需要更长时间
        )

        logger.info(f"🚀 初始化Dify Flow测试器")
        logger.info(f"   Base URL: {self.base_url}")
        logger.info(f"   App ID: {self.app_id}")

    def test_simple_chat(self, message: str, user_id: str = "flow_tester") -> Dict[str, Any]:
        """
        测试简单的聊天功能（LLM调用）

        Args:
            message: 要发送的消息
            user_id: 用户ID

        Returns:
            包含测试结果的字典
        """
        logger.info(f"💬 测试消息: \"{message}\"")

        payload = {
            "inputs": {},
            "query": message,
            "user": user_id,
            "response_mode": "blocking"
        }

        start_time = time.time()

        try:
            response = self.client.post('/v1/chat-messages', json=payload)
            response.raise_for_status()

            end_time = time.time()
            response_time = end_time - start_time

            data = response.json()

            # 提取关键信息
            answer = data.get('answer', '').strip()
            conversation_id = data.get('conversation_id', '')
            message_id = data.get('id', '')

            logger.info(f"✅ 响应成功 (用时: {response_time:.2f}s)")
            logger.info(f"📝 AI回复: {answer[:100]}{'...' if len(answer) > 100 else ''}")

            return {
                'success': True,
                'answer': answer,
                'conversation_id': conversation_id,
                'message_id': message_id,
                'response_time': response_time,
                'raw_response': data
            }

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_data = e.response.json()
                error_detail = error_data.get('message', str(e))
            except:
                error_detail = str(e)

            logger.error(f"❌ HTTP错误: {e.response.status_code} - {error_detail}")
            return {
                'success': False,
                'error': 'HTTP_ERROR',
                'status_code': e.response.status_code,
                'message': error_detail
            }

        except Exception as e:
            logger.error(f"❌ 请求失败: {str(e)}")
            return {
                'success': False,
                'error': 'REQUEST_ERROR',
                'message': str(e)
            }

    def test_conversation_flow(self, messages: List[str], user_id: str = "flow_tester") -> List[Dict[str, Any]]:
        """
        测试多轮对话流程

        Args:
            messages: 消息列表
            user_id: 用户ID

        Returns:
            每条消息的测试结果列表
        """
        logger.info(f"🔄 开始多轮对话测试 ({len(messages)}条消息)")

        results = []
        conversation_id = None

        for i, message in enumerate(messages, 1):
            logger.info(f"\n--- 第{i}轮对话 ---")

            result = self.test_simple_chat(message, user_id)

            if result['success']:
                # 保持会话连续性
                if conversation_id is None:
                    conversation_id = result.get('conversation_id')
                    logger.info(f"🆔 会话ID: {conversation_id}")

            results.append({
                'round': i,
                'question': message,
                'result': result
            })

            # 如果失败，停止后续测试
            if not result['success']:
                logger.warning(f"⚠️ 第{i}轮对话失败，停止后续测试")
                break

            # 轮次间稍作延迟
            if i < len(messages):
                time.sleep(1)

        return results

    def test_app_info(self) -> Dict[str, Any]:
        """测试应用信息获取"""
        try:
            response = self.client.get('/v1/info')
            response.raise_for_status()

            data = response.json()
            logger.info("📱 应用信息:")
            logger.info(f"   名称: {data.get('name', 'Unknown')}")
            logger.info(f"   描述: {data.get('description', 'No description')}")
            logger.info(f"   模式: {data.get('mode', 'Unknown')}")
            logger.info(f"   作者: {data.get('author_name', 'Unknown')}")

            return {
                'success': True,
                'app_info': data
            }

        except Exception as e:
            logger.error(f"❌ 获取应用信息失败: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def run_comprehensive_flow_test(self) -> Dict[str, Any]:
        """运行完整的flow测试"""
        logger.info("🧪 开始完整Flow测试")
        logger.info("=" * 60)

        # 测试1: 应用信息
        logger.info("\n📋 测试1: 获取应用信息")
        app_info_result = self.test_app_info()

        # 测试2: 单条消息测试
        logger.info("\n💬 测试2: 单条消息测试")
        simple_test_messages = [
            "你好",
            "请介绍一下你自己",
            "今天天气怎么样？"
        ]

        single_message_results = []
        for msg in simple_test_messages:
            result = self.test_simple_chat(msg)
            single_message_results.append(result)
            time.sleep(2)  # 避免频率限制

        # 测试3: 多轮对话测试
        logger.info("\n🔄 测试3: 多轮对话测试")
        conversation_messages = [
            "我想学习Python编程",
            "从哪里开始比较好？",
            "有什么推荐的学习资源吗？"
        ]

        conversation_results = self.test_conversation_flow(conversation_messages)

        # 统计结果
        total_tests = len(single_message_results) + len(conversation_results)
        successful_tests = sum(1 for r in single_message_results if r['success']) + \
                          sum(1 for r in conversation_results if r['result']['success'])

        logger.info(f"\n📊 测试总结:")
        logger.info(f"   总测试数: {total_tests}")
        logger.info(f"   成功: {successful_tests}")
        logger.info(f"   失败: {total_tests - successful_tests}")
        logger.info(f"   成功率: {successful_tests/total_tests*100:.1f}%")

        return {
            'app_info': app_info_result,
            'single_message_tests': single_message_results,
            'conversation_tests': conversation_results,
            'summary': {
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'success_rate': successful_tests/total_tests*100
            }
        }

    def close(self):
        """关闭客户端"""
        self.client.close()
        logger.info("🔌 连接已关闭")

def load_config() -> Dict[str, str]:
    """从配置文件加载设置"""
    config_file = "dify_config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"📄 从 {config_file} 加载配置")
            return config
        except Exception as e:
            logger.warning(f"⚠️ 加载配置文件失败: {e}")

    return {}

def main():
    """主函数"""
    logger.info("🎯 Dify Flow 测试工具")
    logger.info("=" * 60)

    # 加载配置
    config = load_config()
    api_key = config.get('api_key') or os.getenv('DIFY_API_KEY')
    base_url = config.get('base_url') or os.getenv('DIFY_BASE_URL', 'http://localhost')

    if not api_key:
        logger.error("❌ 未找到API密钥！")
        logger.info("💡 请确保:")
        logger.info("   1. dify_config.json文件中有api_key")
        logger.info("   2. 或设置DIFY_API_KEY环境变量")
        return

    tester = None
    try:
        # 初始化测试器
        tester = DifyFlowTester(api_key=api_key, base_url=base_url)

        # 运行测试
        results = tester.run_comprehensive_flow_test()

        # 保存测试结果
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        result_file = f"flow_test_results_{timestamp}.json"

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"📁 测试结果已保存到: {result_file}")

    except Exception as e:
        logger.error(f"❌ 测试过程中发生错误: {str(e)}")

    finally:
        if tester:
            tester.close()

if __name__ == "__main__":
    main()