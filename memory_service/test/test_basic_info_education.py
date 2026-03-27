"""
Test basic_info work & education field extraction and storage

Test scenarios:
1. Full work + education info extraction (English)
2. Full work + education info extraction (Chinese)
3. Partial info extraction (occupation only)
4. Education info update (e.g., user changes job)
5. Mixed language
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
import time

BASE_URL = "http://localhost:18088"
TEST_USER_ID = f"test_education_{int(time.time())}"


def test_complete_work_education_english():
    """Test full work & education extraction - English"""
    print("\n=== Test 1: Full work & education extraction (English) ===")

    response = requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": TEST_USER_ID,
            "messages": [
                {"role": "user", "content": "I'm Alice, a software engineer at Google. I got my master's degree in Computer Science from NUS."}
            ]
        }
    )
    assert response.status_code == 200, f"POST failed: {response.status_code}"

    response = requests.get(f"{BASE_URL}/profile?user_id={TEST_USER_ID}")
    assert response.status_code == 200, f"GET failed: {response.status_code}"
    data = response.json()
    basic_info = data.get("basic_info", {})
    print(f"Extracted basic_info: {basic_info}")

    assert basic_info.get("name") == "Alice", f"name wrong: {basic_info.get('name')}"
    assert "engineer" in basic_info.get("occupation", "").lower(), f"occupation wrong: {basic_info.get('occupation')}"
    assert "Google" in basic_info.get("company", ""), f"company wrong: {basic_info.get('company')}"
    assert "master" in basic_info.get("education_level", "").lower(), f"education_level wrong: {basic_info.get('education_level')}"
    assert "NUS" in basic_info.get("university", ""), f"university wrong: {basic_info.get('university')}"

    print("Test 1 passed: full work & education info extracted (English)")
    return True


def test_complete_work_education_chinese():
    """Test full work & education extraction - Chinese"""
    print("\n=== Test 2: Full work & education extraction (Chinese) ===")

    user_id = f"{TEST_USER_ID}_cn"
    response = requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": "我叫李明，是一名产品经理，在字节跳动工作。我本科毕业于北京大学，学的是计算机科学。"}
            ]
        }
    )
    assert response.status_code == 200, f"POST failed: {response.status_code}"

    response = requests.get(f"{BASE_URL}/profile?user_id={user_id}")
    assert response.status_code == 200, f"GET failed: {response.status_code}"
    data = response.json()
    basic_info = data.get("basic_info", {})
    print(f"Extracted basic_info: {basic_info}")

    assert basic_info.get("name") == "李明", f"name wrong: {basic_info.get('name')}"
    assert basic_info.get("company") is not None, f"company should be extracted"
    assert basic_info.get("university") is not None, f"university should be extracted"

    print("Test 2 passed: full work & education info extracted (Chinese)")
    return True


def test_partial_occupation_only():
    """Test partial extraction - occupation only"""
    print("\n=== Test 3: Partial extraction (occupation only) ===")

    user_id = f"{TEST_USER_ID}_partial"
    response = requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": "I work as a data analyst."}
            ]
        }
    )
    assert response.status_code == 200, f"POST failed: {response.status_code}"

    response = requests.get(f"{BASE_URL}/profile?user_id={user_id}")
    assert response.status_code == 200, f"GET failed: {response.status_code}"
    data = response.json()
    basic_info = data.get("basic_info", {})
    print(f"Extracted basic_info: {basic_info}")

    assert "analyst" in basic_info.get("occupation", "").lower(), f"occupation wrong: {basic_info.get('occupation')}"
    assert basic_info.get("company") is None or basic_info.get("company") == "", "company should not be extracted"

    print("Test 3 passed: partial info (occupation only) extracted")
    return True


def test_job_update():
    """Test job update (user changes employer)"""
    print("\n=== Test 4: Job update ===")

    user_id = f"{TEST_USER_ID}_update"

    print("Step 1: Set initial job")
    response1 = requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": "I'm a software engineer at Microsoft."}
            ]
        }
    )
    assert response1.status_code == 200

    response1_get = requests.get(f"{BASE_URL}/profile?user_id={user_id}")
    assert response1_get.status_code == 200
    basic_info1 = response1_get.json().get("basic_info", {})
    print(f"Initial basic_info: {basic_info1}")
    assert "Microsoft" in basic_info1.get("company", "")

    print("Step 2: Update job (changed employer)")
    time.sleep(1)
    response2 = requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": "I just joined Google as a senior engineer."}
            ]
        }
    )
    assert response2.status_code == 200

    response2_get = requests.get(f"{BASE_URL}/profile?user_id={user_id}")
    assert response2_get.status_code == 200
    basic_info2 = response2_get.json().get("basic_info", {})
    print(f"Updated basic_info: {basic_info2}")
    assert "Google" in basic_info2.get("company", ""), f"company update failed: {basic_info2.get('company')}"

    print("Test 4 passed: job info updated successfully")
    return True


def test_mixed_language():
    """Test mixed language (Chinese + English)"""
    print("\n=== Test 5: Mixed language ===")

    user_id = f"{TEST_USER_ID}_mixed"
    response = requests.post(
        f"{BASE_URL}/profile",
        json={
            "user_id": user_id,
            "messages": [
                {"role": "user", "content": "我在Shopee做product manager，本科在NTU读的Computer Engineering。"}
            ]
        }
    )
    assert response.status_code == 200, f"POST failed: {response.status_code}"

    response = requests.get(f"{BASE_URL}/profile?user_id={user_id}")
    assert response.status_code == 200, f"GET failed: {response.status_code}"
    data = response.json()
    basic_info = data.get("basic_info", {})
    print(f"Extracted basic_info: {basic_info}")

    assert basic_info.get("company") is not None, "company should be extracted"
    assert basic_info.get("university") is not None, "university should be extracted"

    print("Test 5 passed: mixed language extraction successful")
    return True


def cleanup():
    """Clean up test data"""
    print("\n=== Cleanup ===")
    test_users = [
        TEST_USER_ID,
        f"{TEST_USER_ID}_cn",
        f"{TEST_USER_ID}_partial",
        f"{TEST_USER_ID}_update",
        f"{TEST_USER_ID}_mixed",
    ]
    for user_id in test_users:
        try:
            response = requests.delete(f"{BASE_URL}/profile?user_id={user_id}")
            if response.status_code == 200:
                print(f"Deleted test user: {user_id}")
        except Exception as e:
            print(f"Failed to delete {user_id}: {e}")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("basic_info work & education field tests")
    print("=" * 60)

    try:
        tests = [
            test_complete_work_education_english,
            test_complete_work_education_chinese,
            test_partial_occupation_only,
            test_job_update,
            test_mixed_language,
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                if test():
                    passed += 1
            except AssertionError as e:
                print(f"FAIL: {e}")
                failed += 1
            except Exception as e:
                print(f"ERROR: {e}")
                failed += 1

        cleanup()

        print("\n" + "=" * 60)
        print(f"Done: {passed} passed, {failed} failed")
        print("=" * 60)

        return failed == 0

    except KeyboardInterrupt:
        print("\nInterrupted")
        cleanup()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
