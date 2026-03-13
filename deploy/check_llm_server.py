#!/usr/bin/env python3
"""
Taxja LLM 服务器健康检查脚本
用法: python deploy/check_llm_server.py [--url URL] [--key KEY]

不传参数时从 backend/.env 读取配置
"""
import argparse
import json
import sys
import time

try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx


def check_server(base_url: str, api_key: str, model: str) -> bool:
    """Check if the LLM server is healthy and responding."""
    print(f"检查服务器: {base_url}")
    print(f"模型: {model}")
    print("-" * 50)

    # 1. Health check
    health_url = base_url.replace("/v1", "/health")
    try:
        r = httpx.get(health_url, timeout=10)
        print(f"[1/3] 健康检查: {'✅ OK' if r.status_code == 200 else f'❌ {r.status_code}'}")
    except Exception as e:
        print(f"[1/3] 健康检查: ❌ 无法连接 ({e})")
        print("\n可能原因:")
        print("  - Pod 还没启动完成（等几分钟再试）")
        print("  - URL 不对（检查 RunPod Dashboard 的 Connect 页面）")
        print("  - Pod 已经停止（去 Dashboard 启动）")
        return False

    # 2. Model list
    try:
        r = httpx.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if r.status_code == 200:
            models = r.json().get("data", [])
            model_ids = [m["id"] for m in models]
            print(f"[2/3] 模型列表: ✅ {model_ids}")
        else:
            print(f"[2/3] 模型列表: ❌ {r.status_code}")
    except Exception as e:
        print(f"[2/3] 模型列表: ❌ {e}")

    # 3. Chat completion test
    print("[3/3] 测试对话生成...")
    start = time.time()
    try:
        r = httpx.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "Du bist ein österreichischer Steuerexperte."},
                    {"role": "user", "content": "Was ist Pendlerpauschale? Antworte in 2 Sätzen."},
                ],
                "max_tokens": 200,
                "temperature": 0.3,
            },
            timeout=60,
        )
        elapsed = time.time() - start
        if r.status_code == 200:
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            print(f"  ✅ 响应时间: {elapsed:.1f}s")
            print(f"  Token 使用: prompt={usage.get('prompt_tokens', '?')}, "
                  f"completion={usage.get('completion_tokens', '?')}")
            print(f"  回答: {content[:200]}")
        else:
            print(f"  ❌ HTTP {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return False

    print("-" * 50)
    print("✅ 服务器正常运行，可以在 backend/.env 中配置:")
    print(f"  GPT_OSS_ENABLED=true")
    print(f"  GPT_OSS_BASE_URL={base_url}")
    print(f"  GPT_OSS_MODEL={model}")
    print(f"  GPT_OSS_API_KEY={api_key}")
    return True


def load_env(env_path: str = "backend/.env") -> dict:
    """Load .env file as dict."""
    env = {}
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Taxja LLM 服务器健康检查")
    parser.add_argument("--url", help="vLLM API base URL (e.g. https://xxx-8000.proxy.runpod.net/v1)")
    parser.add_argument("--key", help="API key", default="not-needed")
    parser.add_argument("--model", help="Model name", default="Qwen/Qwen2.5-7B-Instruct")
    args = parser.parse_args()

    if not args.url:
        env = load_env()
        args.url = env.get("GPT_OSS_BASE_URL", "")
        args.key = env.get("GPT_OSS_API_KEY", args.key)
        args.model = env.get("GPT_OSS_MODEL", args.model)

    if not args.url:
        print("❌ 请提供 --url 参数，或在 backend/.env 中设置 GPT_OSS_BASE_URL")
        sys.exit(1)

    ok = check_server(args.url, args.key, args.model)
    sys.exit(0 if ok else 1)
