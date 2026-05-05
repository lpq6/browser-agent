"""
Waoowaoo 自动化调试脚本
使用 Browser Agent 自动完成视频工作流配置和测试
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from browser_agent.agent import run_agent, MODELS


async def check_waoowaoo_status():
    """检查 waoowaoo 当前状态"""
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        # Check if waoowaoo is running
        try:
            async with session.get("http://localhost:13000/", allow_redirects=False) as resp:
                print(f"✅ waoowaoo 状态: {resp.status}")
        except Exception as e:
            print(f"❌ waoowaoo 未运行: {e}")
            return False
        
        # Check API endpoints
        endpoints = [
            "/api/health",
            "/api/models",
            "/api/user/preferences",
        ]
        
        for endpoint in endpoints:
            try:
                async with session.get(f"http://localhost:13000{endpoint}") as resp:
                    print(f"  {endpoint}: {resp.status}")
            except Exception as e:
                print(f"  {endpoint}: 错误 - {e}")
    
    return True


async def configure_waoowaoo():
    """使用 Browser Agent 配置 waoowaoo"""
    task = """
    访问 http://localhost:13000 并完成以下配置：
    
    1. 登录（如果需要）
    2. 进入设置中心
    3. 检查并配置以下模型：
       - 分析模型: qwen (本地)
       - 视频模型: cogvideox-3 (智谱)
       - 音频模型: mimo-tts
       - 口型同步: 需要 FAL API Key
    4. 保存配置
    
    如果遇到问题，记录下来并尝试解决。
    """
    
    print("🤖 启动 Browser Agent 配置 waoowaoo...")
    print(f"任务: {task[:100]}...")
    
    result = await run_agent(
        task=task,
        model_key="qwen",
        headless=True
    )
    
    return result


async def test_video_workflow():
    """测试视频生成工作流"""
    task = """
    在 waoowaoo 中测试完整的视频生成工作流：
    
    1. 创建一个新项目
    2. 输入简单的故事文本（如："一个小女孩在公园里玩耍"）
    3. 生成剧本
    4. 生成分镜
    5. 生成视频片段
    6. 合成最终视频
    
    记录每一步的结果和遇到的问题。
    """
    
    print("🎬 启动视频工作流测试...")
    print(f"任务: {task[:100]}...")
    
    result = await run_agent(
        task=task,
        model_key="qwen",
        headless=True
    )
    
    return result


async def main():
    """主函数"""
    print("=" * 60)
    print("🎯 Waoowaoo 自动化调试")
    print("=" * 60)
    
    # Step 1: 检查状态
    print("\n📋 Step 1: 检查 waoowaoo 状态...")
    if not await check_waoowaoo_status():
        print("❌ waoowaoo 未运行，请先启动服务")
        return
    
    # Step 2: 配置 waoowaoo
    print("\n🔧 Step 2: 配置 waoowaoo...")
    try:
        config_result = await configure_waoowaoo()
        print(f"✅ 配置完成: {config_result}")
    except Exception as e:
        print(f"❌ 配置失败: {e}")
        return
    
    # Step 3: 测试视频工作流
    print("\n🎬 Step 3: 测试视频工作流...")
    try:
        test_result = await test_video_workflow()
        print(f"✅ 测试完成: {test_result}")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return
    
    print("\n" + "=" * 60)
    print("✅ Waoowaoo 自动化调试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
