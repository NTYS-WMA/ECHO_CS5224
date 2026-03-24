"""
测试 basic_info 教育字段提取和存储

测试场景：
1. 完整教育信息提取（中文）
2. 完整教育信息提取（英文）
3. 部分教育信息提取（只有年级）
4. 教育信息更新
5. 中英文混合
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
import time

# API 配置
BASE_URL = "http://localhost:18088"
TEST_USER_ID = f"test_education_{int(time.time())}"

def test_complete_education_chinese():
    """测试完整教育信息提取 - 中文"""
    print("\n=== 测试1: 完整教育信息提取（中文） ===")

    # POST: 更新 profile
    response = requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": TEST_USER_ID,
            "messages": [
                {"role": "user", "content": "我叫小明，在北京实验小学上三年级2班"}
            ]
        }
    )
    assert response.status_code == 200, f"POST 调用失败: {response.status_code}"

    # GET: 验证提取结果
    response = requests.get(f"{BASE_URL}/profile?user_id={TEST_USER_ID}")
    assert response.status_code == 200, f"GET 调用失败: {response.status_code}"
    data = response.json()
    basic_info = data.get("basic_info", {})
    print(f"提取的 basic_info: {basic_info}")

    assert basic_info.get("name") == "小明", f"name 提取错误: {basic_info.get('name')}"
    assert basic_info.get("school_name") == "北京实验小学", f"school_name 提取错误: {basic_info.get('school_name')}"
    assert basic_info.get("grade") == "三年级", f"grade 提取错误: {basic_info.get('grade')}"
    assert basic_info.get("class_name") == "2班", f"class_name 提取错误: {basic_info.get('class_name')}"

    print("✅ 测试1通过: 成功提取完整教育信息（中文）")
    return True

def test_complete_education_english():
    """测试完整教育信息提取 - 英文"""
    print("\n=== 测试2: 完整教育信息提取（英文） ===")

    user_id = f"{TEST_USER_ID}_en"
    # POST: 更新 profile
    response = requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": "My name is Alice, I'm in Grade 3 Class A at Beijing International School"}
            ]
        }
    )
    assert response.status_code == 200, f"POST 调用失败: {response.status_code}"

    # GET: 验证提取结果
    response = requests.get(f"{BASE_URL}/profile?user_id={user_id}")
    assert response.status_code == 200, f"GET 调用失败: {response.status_code}"
    data = response.json()
    basic_info = data.get("basic_info", {})
    print(f"提取的 basic_info: {basic_info}")

    assert basic_info.get("name") == "Alice", f"name 提取错误: {basic_info.get('name')}"
    assert "Beijing International School" in basic_info.get("school_name", ""), f"school_name 提取错误: {basic_info.get('school_name')}"
    assert "Grade 3" in basic_info.get("grade", ""), f"grade 提取错误: {basic_info.get('grade')}"
    assert "Class A" in basic_info.get("class_name", ""), f"class_name 提取错误: {basic_info.get('class_name')}"

    print("✅ 测试2通过: 成功提取完整教育信息（英文）")
    return True

def test_partial_education():
    """测试部分教育信息提取"""
    print("\n=== 测试3: 部分教育信息提取（只有年级） ===")

    user_id = f"{TEST_USER_ID}_partial"
    # POST: 更新 profile
    response = requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": "我现在读小学四年级"}
            ]
        }
    )
    assert response.status_code == 200, f"POST 调用失败: {response.status_code}"

    # GET: 验证提取结果
    response = requests.get(f"{BASE_URL}/profile?user_id={user_id}")
    assert response.status_code == 200, f"GET 调用失败: {response.status_code}"
    data = response.json()
    basic_info = data.get("basic_info", {})
    print(f"提取的 basic_info: {basic_info}")

    # 应该只提取到年级
    assert "四年级" in basic_info.get("grade", ""), f"grade 提取错误: {basic_info.get('grade')}"
    assert basic_info.get("school_name") is None or basic_info.get("school_name") == "", "不应该提取 school_name"
    assert basic_info.get("class_name") is None or basic_info.get("class_name") == "", "不应该提取 class_name"

    print("✅ 测试3通过: 成功提取部分教育信息")
    return True

def test_education_update():
    """测试教育信息更新"""
    print("\n=== 测试4: 教育信息更新 ===")

    user_id = f"{TEST_USER_ID}_update"

    # 第一次设置
    print("第一次设置: 三年级")
    response1 = requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": "我在上小学三年级"}
            ]
        }
    )
    assert response1.status_code == 200

    # GET: 验证第一次结果
    response1_get = requests.get(f"{BASE_URL}/profile?user_id={user_id}")
    assert response1_get.status_code == 200
    basic_info1 = response1_get.json().get("basic_info", {})
    print(f"第一次提取: {basic_info1}")
    assert "三年级" in basic_info1.get("grade", "")

    # 第二次更新
    print("\n第二次更新: 升到四年级")
    time.sleep(1)  # 避免时间戳冲突
    response2 = requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": "我升到四年级了"}
            ]
        }
    )
    assert response2.status_code == 200

    # GET: 验证第二次结果
    response2_get = requests.get(f"{BASE_URL}/profile?user_id={user_id}")
    assert response2_get.status_code == 200
    basic_info2 = response2_get.json().get("basic_info", {})
    print(f"第二次提取: {basic_info2}")
    assert "四年级" in basic_info2.get("grade", ""), f"grade 更新失败: {basic_info2.get('grade')}"

    print("✅ 测试4通过: 成功更新教育信息")
    return True

def test_mixed_language():
    """测试中英文混合"""
    print("\n=== 测试5: 中英文混合 ===")

    user_id = f"{TEST_USER_ID}_mixed"
    # POST: 更新 profile
    response = requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": "我在上海实验小学读Grade 3"}
            ]
        }
    )
    assert response.status_code == 200, f"POST 调用失败: {response.status_code}"

    # GET: 验证提取结果
    response = requests.get(f"{BASE_URL}/profile?user_id={user_id}")
    assert response.status_code == 200, f"GET 调用失败: {response.status_code}"
    data = response.json()
    basic_info = data.get("basic_info", {})
    print(f"提取的 basic_info: {basic_info}")

    assert basic_info.get("school_name") == "上海实验小学", f"school_name 提取错误: {basic_info.get('school_name')}"
    assert "Grade 3" in basic_info.get("grade", ""), f"grade 提取错误: {basic_info.get('grade')}"

    print("✅ 测试5通过: 成功处理中英文混合")
    return True

def test_get_profile_with_education():
    """测试获取包含教育字段的 profile"""
    print("\n=== 测试6: 获取包含教育字段的 profile ===")

    # 先设置一个完整的 profile
    user_id = f"{TEST_USER_ID}_get"
    requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": "我叫小红，在杭州外国语学校上五年级3班"}
            ]
        }
    )

    # 获取 profile
    response = requests.get(f"{BASE_URL}/profile?user_id={user_id}")
    assert response.status_code == 200

    data = response.json()
    basic_info = data.get("basic_info", {})
    print(f"获取的 basic_info: {basic_info}")

    assert basic_info.get("name") == "小红"
    assert basic_info.get("school_name") == "杭州外国语学校"
    assert basic_info.get("grade") == "五年级"
    assert basic_info.get("class_name") == "3班"

    print("✅ 测试6通过: 成功获取包含教育字段的 profile")
    return True

def cleanup():
    """清理测试数据"""
    print("\n=== 清理测试数据 ===")

    test_users = [
        TEST_USER_ID,
        f"{TEST_USER_ID}_en",
        f"{TEST_USER_ID}_partial",
        f"{TEST_USER_ID}_update",
        f"{TEST_USER_ID}_mixed",
        f"{TEST_USER_ID}_get"
    ]

    for user_id in test_users:
        try:
            response = requests.delete(f"{BASE_URL}/profile?user_id={user_id}")
            if response.status_code == 200:
                print(f"✅ 删除测试用户: {user_id}")
        except Exception as e:
            print(f"⚠️  删除失败 {user_id}: {e}")

def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("basic_info 教育字段测试")
    print("=" * 60)

    try:
        # 运行所有测试
        tests = [
            test_complete_education_chinese,
            test_complete_education_english,
            test_partial_education,
            test_education_update,
            test_mixed_language,
            test_get_profile_with_education
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                if test():
                    passed += 1
            except AssertionError as e:
                print(f"❌ 测试失败: {e}")
                failed += 1
            except Exception as e:
                print(f"❌ 测试错误: {e}")
                failed += 1

        # 清理
        cleanup()

        # 总结
        print("\n" + "=" * 60)
        print(f"测试完成: {passed} 通过, {failed} 失败")
        print("=" * 60)

        return failed == 0

    except KeyboardInterrupt:
        print("\n测试中断")
        cleanup()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)