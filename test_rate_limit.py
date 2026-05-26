"""测试API限流功能。"""

import requests
import time

BASE_URL = "http://localhost:8080"


def test_login_rate_limit():
    """测试登录接口限流（10次/分钟）。"""
    print("=== 测试登录接口限流 ===")
    print("快速发送11次登录请求，第11次应该返回429\n")

    url = f"{BASE_URL}/api/v1/users/login"
    headers = {"Content-Type": "application/json"}
    data = {"username": "test", "password": "123456"}

    for i in range(1, 12):
        try:
            response = requests.post(url, json=data, headers=headers)
            print(f"请求 {i}: 状态码 {response.status_code}")

            if response.status_code == 429:
                print(f"\n✓ 限流生效！第{i}次请求被拒绝")
                return True
        except requests.exceptions.ConnectionError:
            print(f"请求 {i}: 连接失败（服务器未启动？）")
            return False

    print("\n✗ 限流未生效，所有请求都成功了")
    return False


def test_error_handling():
    """测试错误处理。"""
    print("\n=== 测试错误处理 ===")

    # 测试访问不存在的资源
    url = f"{BASE_URL}/api/v1/documents/99999"
    try:
        response = requests.get(url)
        print(f"访问不存在的文档: 状态码 {response.status_code}")

        if response.status_code in [401, 403, 404]:
            print("✓ 错误处理正常")
            return True
    except requests.exceptions.ConnectionError:
        print("连接失败（服务器未启动？）")
        return False

    return False


def test_health_check():
    """测试健康检查接口。"""
    print("\n=== 测试健康检查 ===")

    url = f"{BASE_URL}/health"
    try:
        response = requests.get(url)
        print(f"健康检查: 状态码 {response.status_code}")

        if response.status_code == 200:
            print(f"响应内容: {response.json()}")
            print("✓ 健康检查正常")
            return True
    except requests.exceptions.ConnectionError:
        print("连接失败（服务器未启动？）")
        return False

    return False


def main():
    print("API限流与错误处理测试")
    print("=" * 50)
    print("请确保服务器已启动: python start_server.py\n")

    results = []
    results.append(("健康检查", test_health_check()))
    results.append(("错误处理", test_error_handling()))
    results.append(("限流功能", test_login_rate_limit()))

    print("\n" + "=" * 50)
    print("测试结果汇总:")
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    main()
