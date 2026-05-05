#!/bin/bash
# Waoowaoo 视频工作流测试脚本

cd /mnt/d/OpenClaw_Workspace_full/browser-agent

echo "🎯 Waoowaoo 视频工作流测试"
echo "=========================="
echo ""

# Test 1: 检查服务状态
echo "📋 Test 1: 检查服务状态..."
curl -s --max-time 3 -o /dev/null -w "waoowaoo (13000): %{http_code}\n" http://localhost:13000/
curl -s --max-time 3 -o /dev/null -w "qwen2api (7860): %{http_code}\n" http://localhost:7860/
echo ""

# Test 2: 使用 Browser Agent 测试视频生成
echo "🤖 Test 2: 使用 Browser Agent 测试视频生成..."
echo "任务: 打开 waoowaoo，创建项目，生成视频"
echo ""

python3 agent.py "
访问 http://localhost:13000 并完成以下任务：

1. 登录（如果需要）
2. 创建一个新项目
3. 输入故事文本：'一个小女孩在公园里玩耍，追逐蝴蝶，最后坐在长椅上休息'
4. 点击生成剧本
5. 等待剧本生成完成
6. 点击生成分镜
7. 等待分镜生成完成
8. 尝试生成视频片段
9. 记录每一步的结果和遇到的问题

如果遇到错误，记录错误信息并尝试解决。
" --headless

echo ""
echo "✅ 测试完成！"
