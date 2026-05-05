# 🤖 Multi-Model Browser Agent

**全自动 AI 浏览器自动化** — 无需手动启动浏览器，Agent 自己搞定一切。

## 快速开始

```bash
cd /mnt/d/OpenClaw_Workspace_full/browser-agent

# 直接运行（自动启动浏览器）
python3 agent.py "搜索免费的视频生成 API"

# 无头模式（后台运行，不显示浏览器窗口）
python3 agent.py "搜索 xxx" --headless

# 交互模式（连续对话）
python3 agent.py -i
```

**就这么简单！** 不需要手动启动 Chrome，不需要配置端口，不需要任何前置步骤。

## 🎬 Waoowaoo 视频工作流测试

```bash
# 测试 waoowaoo 视频生成工作流
./test_waoowaoo.sh

# 或使用 Python 脚本
python3 waoowaoo_debug.py
```

## 使用示例

```bash
# 用免费的 qwen 模型（默认）
python3 agent.py "打开百度搜索 AI 视频生成"

# 用 grok 模型
python3 agent.py "打开 x.com 查看消息" -m grok

# 用本地 ollama（完全离线免费）
python3 agent.py "打开百度" -m ollama

# 无头模式
python3 agent.py "登录 dreamina.capcut.com 领取积分" --headless

# 列出可用模型
python3 agent.py --list-models
```

## 可用模型

| Key       | 名称                | 费用     | 说明                     |
|-----------|---------------------|----------|--------------------------|
| `qwen`    | Qwen 3.6 Plus (本地) | **免费** | 通过 qwen2api, 默认模型  |
| `ollama`  | Ollama (本地)        | **免费** | 需要安装 ollama          |
| `grok`    | Grok (x.ai)         | 付费     | 需要 XAI_API_KEY         |
| `openai`  | GPT-4o              | 付费     | 需要 OPENAI_API_KEY      |
| `anthropic`| Claude Sonnet       | 付费     | 需要 ANTHROPIC_API_KEY   |
| `google`  | Gemini Flash         | 付费     | 需要 GOOGLE_API_KEY      |

## 工作原理

1. **输入任务** → 你用自然语言描述要做什么
2. **AI 规划** → LLM 分析任务，规划浏览器操作步骤
3. **自动执行** → Playwright 自动启动 Chromium，执行点击、输入、导航等操作
4. **返回结果** → 完成后告诉你结果

## 文件说明

```
browser-agent/
├── agent.py              # 主程序（全自动）
├── .env.example          # 环境变量模板
└── README.md             # 本文档
```

## 常见问题

**Q: 需要手动启动浏览器吗？**
A: 不需要！Agent 会自动启动 Chromium 浏览器执行任务。

**Q: 可以看到浏览器操作过程吗？**
A: 可以！默认是有头模式（显示浏览器窗口）。加 `--headless` 可以后台运行。

**Q: 支持哪些网站？**
A: 理论上支持所有网站。但某些网站可能有反爬机制，需要特殊处理。

**Q: 可以登录网站吗？**
A: 可以！Agent 可以自动填写表单、点击按钮、处理登录流程。

**Q: 如何免费使用？**
A: 默认使用本地 qwen2api（免费），或使用 ollama（完全离线免费）。

## 🎯 Waoowaoo 自动化调试

本 Agent 可以自动化调试 waoowaoo 视频生成平台：

1. **自动配置** — 自动设置模型、API Key 等
2. **自动测试** — 自动创建项目、生成剧本、分镜、视频
3. **问题诊断** — 自动记录错误并尝试解决

### 配置检查

```bash
# 检查 waoowaoo 配置
docker exec waoowaoo-mysql mysql -u root -pwaoowaoo123 waoowaoo -e "
SELECT userId, analysisModel, videoModel, audioModel 
FROM user_preferences 
WHERE userId = '59341b5a-8d29-4c3f-8eb9-7fd1fad64f78';
"
```

### 当前配置状态

| 模型 | 配置值 | 状态 |
|------|--------|------|
| 分析模型 | mimo-v2-pro | ✅ 已配置 |
| 视频模型 | cogvideox-3 | ✅ 已配置 |
| 音频模型 | mimo-v2.5-tts | ✅ 已配置 |
| 口型同步 | fal-ai/kling-video | ⚠️ 需要 FAL API Key |

### 需要配置的 API Key

1. **FAL API Key** — 用于口型同步功能
   - 注册: https://fal.ai
   - 免费额度: $5/月

2. **智谱 API Key** — 用于 cogvideox-3 视频生成
   - 注册: https://open.bigmodel.cn
   - 免费额度: 有

3. **Google AI Key** — 用于 Gemini 模型（可选）
   - 注册: https://ai.google.dev
   - 免费额度: 有
