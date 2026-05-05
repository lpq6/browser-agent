"""
Multi-Model Browser Agent
全自动化：无需手动启动浏览器，Agent 自己启动 Chromium 执行任务
支持模型: qwen (本地), grok, openai, anthropic, google, ollama
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ========== 模型配置 ==========
MODELS = {
    "qwen": {
        "name": "Qwen 3.6 Plus (本地)",
        "provider": "openai",
        "model": "gpt-4o",  # qwen2api 兼容 OpenAI 格式
        "base_url": "http://127.0.0.1:7860/v1",
        "api_key": "sk-696284a35c73efcb41ba16fbe820c0754997173fa4866cd9",
    },
    "grok": {
        "name": "Grok",
        "provider": "openai",
        "model": "grok-3",
        "base_url": "https://api.x.ai/v1",
        "api_key": os.getenv("XAI_API_KEY", ""),
    },
    "openai": {
        "name": "OpenAI GPT-4o",
        "provider": "openai",
        "model": "gpt-4o",
        "base_url": None,
        "api_key": os.getenv("OPENAI_API_KEY", ""),
    },
    "anthropic": {
        "name": "Claude Sonnet",
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "base_url": None,
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
    },
    "google": {
        "name": "Gemini Flash",
        "provider": "google",
        "model": "gemini-2.5-flash-preview-05-20",
        "base_url": None,
        "api_key": os.getenv("GOOGLE_API_KEY", ""),
    },
    "ollama": {
        "name": "Ollama (本地)",
        "provider": "ollama",
        "model": "qwen3:8b",
        "base_url": "http://localhost:11434",
        "api_key": None,
    },
}


def get_llm(model_key: str):
    """根据模型 key 返回对应的 LLM 实例"""
    from browser_use import ChatOpenAI, ChatGoogle, ChatAnthropic, ChatOllama

    cfg = MODELS.get(model_key)
    if not cfg:
        print(f"❌ 未知模型: {model_key}")
        print(f"   可选: {', '.join(MODELS.keys())}")
        sys.exit(1)

    provider = cfg["provider"]
    model = cfg["model"]

    if provider == "openai":
        kwargs = {"model": model}
        if cfg["base_url"]:
            kwargs["base_url"] = cfg["base_url"]
        if cfg["api_key"]:
            kwargs["api_key"] = cfg["api_key"]
        return ChatOpenAI(**kwargs)

    elif provider == "anthropic":
        return ChatAnthropic(
            model=model,
            api_key=cfg["api_key"],
        )

    elif provider == "google":
        return ChatGoogle(
            model=model,
            api_key=cfg["api_key"],
        )

    elif provider == "ollama":
        return ChatOllama(
            model=model,
            base_url=cfg["base_url"],
        )

    else:
        print(f"❌ 不支持的 provider: {provider}")
        sys.exit(1)


async def run_agent(task: str, model_key: str = "qwen", headless: bool = False, cdp_url: str = None):
    """运行浏览器自动化 Agent - 全自动，无需手动启动浏览器"""
    from browser_use import Agent, Browser

    llm = get_llm(model_key)
    model_name = MODELS[model_key]["name"]

    print(f"🤖 模型: {model_name}")
    print(f"📋 任务: {task}")

    # 配置浏览器 - 全自动
    if cdp_url:
        # 连接已有浏览器 (高级用法)
        print(f"🌐 连接已有浏览器: {cdp_url}")
        browser = Browser(cdp_url=cdp_url)
    else:
        # 全自动模式：Agent 自己启动 Chromium
        if headless:
            print("🌐 无头模式 (后台运行)")
        else:
            print("🌐 有头模式 (显示浏览器窗口)")
        browser = Browser(headless=headless)

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
    )

    print("🚀 开始执行...\n")
    result = await agent.run()
    print(f"\n✅ 完成: {result}")
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="🤖 Multi-Model Browser Agent - 全自动 AI 浏览器自动化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 全自动：用 qwen 模型搜索（自动启动浏览器）
  python3 agent.py "搜索免费的视频生成 API"

  # 无头模式（后台运行，不显示浏览器窗口）
  python3 agent.py "搜索 xxx" --headless

  # 用 grok 模型
  python3 agent.py "打开 x.com" -m grok

  # 用本地 ollama（完全离线免费）
  python3 agent.py "打开百度" -m ollama

  # 交互模式（连续对话）
  python3 agent.py -i

  # 列出可用模型
  python3 agent.py --list-models

支持的模型:
  qwen      - Qwen 3.6 Plus (本地 qwen2api, 默认, 免费)
  ollama    - 本地 Ollama (免费)
  grok      - Grok (x.ai)
  openai    - GPT-4o
  anthropic - Claude Sonnet
  google    - Gemini Flash
        """,
    )
    parser.add_argument("task", nargs="?", help="要执行的任务")
    parser.add_argument("-m", "--model", default="qwen", choices=list(MODELS.keys()),
                        help="使用的模型 (默认: qwen)")
    parser.add_argument("--headless", action="store_true",
                        help="无头模式（后台运行，不显示浏览器窗口）")
    parser.add_argument("--cdp", default=None,
                        help="CDP URL (高级用法，连接已有浏览器)")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="交互模式")
    parser.add_argument("--list-models", action="store_true",
                        help="列出可用模型")

    args = parser.parse_args()

    if args.list_models:
        print("\n可用模型:")
        for k, v in MODELS.items():
            print(f"  {k:12s} - {v['name']}")
        return

    if args.interactive:
        print("🤖 Multi-Model Browser Agent - 交互模式")
        print(f"当前模型: {MODELS[args.model]['name']}")
        print("输入任务描述，输入 'quit' 退出\n")

        while True:
            try:
                task = input("📋 任务> ").strip()
                if task.lower() in ("quit", "exit", "q"):
                    break
                if not task:
                    continue
                asyncio.run(run_agent(task, args.model, args.headless, args.cdp))
            except KeyboardInterrupt:
                print("\n👋 再见!")
                break
            except Exception as e:
                print(f"❌ 错误: {e}")
        return

    if not args.task:
        parser.print_help()
        return

    asyncio.run(run_agent(args.task, args.model, args.headless, args.cdp))


if __name__ == "__main__":
    main()
