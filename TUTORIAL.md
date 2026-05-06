# 从零控制 Windows Chrome — 完整教程

本教程手把手教你从 WSL (或远程服务器) 控制 Windows 上运行的真实 Chrome 浏览器，保留所有登录状态和 Cookie。

## 目录

- [背景：为什么需要这个？](#背景为什么需要这个)
- [架构总览](#架构总览)
- [第一步：Windows Chrome 开启远程调试](#第一步windows-chrome-开启远程调试)
- [第二步：WSL 环境准备](#第二步wsl-环境准备)
- [第三步：启动 CDP 反向代理](#第三步启动-cdp-反向代理)
- [第四步：验证连接](#第四步验证连接)
- [第五步：基础操作（CLI）](#第五步基础操作cli)
- [第六步：Python 编程接口](#第六步python-编程接口)
- [第七步：自然语言任务模式](#第七步自然语言任务模式)
- [第八步：实战案例](#第八步实战案例)
- [常见问题](#常见问题)

---

## 背景：为什么需要这个？

WSL2 运行在独立的虚拟机里，网络栈和 Windows 本机不同。即使 Windows Chrome 监听 `localhost:9222`，WSL 里的 `localhost` 是 WSL 自己的，不是 Windows 的。

```
WSL2 localhost  ──✗──→  Windows localhost:9222   (不通！)
```

常规方案要么需要额外代理，要么需要绕一圈走网络。本项目通过 **CDP 反向代理** 解决这个问题。

## 架构总览

```
┌─────────────────────────┐
│        WSL2 (Linux)      │
│                          │
│  win_browser.py (CLI)    │
│        │                 │
│        ▼                 │
│  cdp_proxy.py (代理)     │
│  监听 127.0.0.1:9222     │
│        │                 │
└────────┼────────────────┘
         │ TCP (通过 HTTP_PROXY 可选)
         ▼
┌─────────────────────────┐
│     Windows Host         │
│                          │
│  Chrome                  │
│  --remote-debugging-port=9222
│  监听 localhost:9222     │
└─────────────────────────┘
```

**数据流：**
1. `win_browser.py` → 连接 `127.0.0.1:9222`（WSL 本地）
2. `cdp_proxy.py` → 转发到 `Windows Chrome`（可能经过 HTTP 代理）
3. Chrome 处理请求，原路返回

---

## 第一步：Windows Chrome 开启远程调试

### 方法 A：命令行启动（推荐）

打开 Windows **PowerShell**，运行：

```powershell
# 关掉所有 Chrome 进程
taskkill /IM chrome.exe /F

# 用远程调试端口重新启动
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="C:\tmp\chrome-debug"
```

**参数说明：**
- `--remote-debugging-port=9222`：开放 CDP 调试端口
- `--user-data-dir="C:\tmp\chrome-debug"`：使用独立的用户数据目录（避免和正常 Chrome 冲突）

> ⚠️ 不要同时运行两个使用相同 `--user-data-dir` 的 Chrome 实例。

### 方法 B：创建快捷方式

1. 右键桌面 → 新建 → 快捷方式
2. 目标填：
   ```
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\tmp\chrome-debug"
   ```
3. 命名为 "Chrome Debug"
4. 双击启动

### 方法 C：创建 .bat 脚本

创建 `start-chrome-debug.bat`：

```bat
@echo off
echo Starting Chrome with remote debugging...
taskkill /IM chrome.exe /F 2>nul
timeout /t 2 /nobreak >nul
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\tmp\chrome-debug"
echo Chrome started on port 9222
```

双击运行即可。

### 验证 Chrome 调试端口

Chrome 启动后，在 Windows 浏览器中访问：

```
http://localhost:9222/json/version
```

看到类似以下 JSON 就说明成功：

```json
{
  "Browser": "Chrome/136.0.7103.93",
  "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/xxxxx",
  "User-Agent": "Mozilla/5.0 ..."
}
```

---

## 第二步：WSL 环境准备

### 安装依赖

```bash
pip install websockets httpx
```

### 克隆/进入项目

```bash
cd /mnt/d/OpenClaw_Workspace_full/browser-agent
```

### 配置环境变量

编辑 `.env` 文件（或直接用 `.env.example` 复制）：

```bash
# CDP 连接地址（WSL 代理监听的地址）
CDP_HTTP=http://127.0.0.1:9222

# 代理转发目标（Windows Chrome 地址）
CDP_PROXY_TARGET=localhost:9222

# WSL 上代理监听的地址
CDP_PROXY_LISTEN=127.0.0.1:9222

# 如果你的 WSL 需要通过 HTTP 代理访问 Windows 网络：
# HTTP_PROXY=http://192.168.31.215:7890
```

### 关键环境变量

在 WSL 中运行脚本前，**必须**设置：

```bash
export no_proxy="127.0.0.1,localhost"
export NO_PROXY="127.0.0.1,localhost"
```

这是为了让 Python/Node.js 不走代理直连本地的 CDP 代理，否则会连接失败。

---

## 第三步：启动 CDP 反向代理

```bash
cd /mnt/d/OpenClaw_Workspace_full/browser-agent

# 前台运行（看日志）
python3 cdp_proxy.py

# 或后台运行
python3 cdp_proxy.py &
```

看到输出：

```
🚀 CDP 反向代理启动: 127.0.0.1:9222
📡 转发到: localhost:9222
🔗 上游代理: 直连（无代理）
✅ 支持 HTTP + WebSocket (CDP)
```

> 💡 `win_browser.py` 会自动检测并启动代理，所以大多数时候你不需要手动运行这步。

---

## 第四步：验证连接

```bash
python3 win_browser.py status
```

成功输出：

```json
{
  "ok": true,
  "cdp": "http://127.0.0.1:9222",
  "pages": [
    {
      "id": "xxxxx",
      "title": "新标签页",
      "url": "chrome://newtab/",
      "type": "page"
    }
  ]
}
```

如果报错 `Windows Chrome CDP not reachable`：
1. 确认 Chrome 已用 `--remote-debugging-port=9222` 启动
2. 确认代理已启动
3. 确认 `NO_PROXY` 环境变量已设置

---

## 第五步：基础操作（CLI）

### 打开网页

```bash
python3 win_browser.py open "https://www.baidu.com"
```

### 查看页面快照（DOM 树）

```bash
python3 win_browser.py snapshot
```

输出包含：页面标题、URL、可见文本、所有可交互元素（链接、按钮、输入框）及其坐标。

### 按文字搜索元素

```bash
python3 win_browser.py find "搜索"
```

### 点击元素

```bash
# 按文字点击
python3 win_browser.py click "百度一下"

# 按 CSS 选择器点击
python3 win_browser.py click --selector "#su"

# 按索引点击（从 snapshot 列表中）
python3 win_browser.py click --index 3

# 按坐标点击
python3 win_browser.py click-xy 500 400
```

### 填写表单

```bash
# 填充输入框（清空后填入）
python3 win_browser.py fill 'input[name="wd"]' 'Hello World'

# 追加键入文字
python3 win_browser.py type '搜索内容' --selector '#kw'
```

### 按键

```bash
python3 win_browser.py press Enter
python3 win_browser.py press Tab
python3 win_browser.py press Escape
```

### 滚动

```bash
# 向下滚动 700px
python3 win_browser.py scroll --y 700

# 向上滚动
python3 win_browser.py scroll --y -500
```

### 等待元素出现

```bash
# 等待文字出现
python3 win_browser.py wait --text "搜索结果" --timeout 10000

# 等待选择器出现
python3 win_browser.py wait --selector ".result" --timeout 10000
```

### 截图

```bash
# 普通截图
python3 win_browser.py screenshot /tmp/page.png

# 全页截图（含滚动区域）
python3 win_browser.py screenshot /tmp/full.png --full-page
```

### 检查音视频状态

```bash
python3 win_browser.py media
```

---

## 第六步：Python 编程接口

### 基本用法

```python
import asyncio
from win_browser import PageCDP, pick_tab, tabs, ensure_cdp

async def main():
    # 确保 CDP 可达（自动启动代理）
    ensure_cdp()

    # 打开一个网页
    import urllib.request, json
    with urllib.request.urlopen('http://127.0.0.1:9222/json/new?https://example.com') as r:
        tab_info = json.loads(r.read())

    # 选中标签页
    tab = pick_tab("example.com")

    # 操作页面
    async with PageCDP(tab) as page:
        # 获取标题
        title = await page.eval("document.title")
        print(f"页面标题: {title}")

        # 截图
        await page.screenshot("/tmp/example.png")

        # 点击坐标
        await page.mouse_click(500, 300)

        # 输入文字
        await page.insert_text("Hello World")

        # 按键
        await page.key("Enter")

asyncio.run(main())
```

### `PageCDP` 方法速查

| 方法 | 说明 | 示例 |
|------|------|------|
| `await page.eval(js)` | 执行 JavaScript，返回结果 | `await page.eval("document.title")` |
| `await page.screenshot(path, full)` | 截图到文件 | `await page.screenshot("/tmp/a.png", True)` |
| `await page.mouse_click(x, y)` | 鼠标点击 | `await page.mouse_click(100, 200)` |
| `await page.insert_text(text)` | 输入文字 | `await page.insert_text("hello")` |
| `await page.key(key)` | 按键 | `await page.key("Enter")` |
| `await page.send(method, params)` | 发送原始 CDP 命令 | 见下方高级用法 |

### 高级：原始 CDP 操作

```python
# 设置 Cookie
await page.send('Network.setCookie', {
    'name': 'session-token',
    'value': 'abc123',
    'domain': '.example.com',
    'path': '/'
})

# 导航到新页面
await page.send('Page.navigate', {'url': 'https://example.com/dashboard'})

# 获取所有标签页
all_tabs = tabs()
for t in all_tabs:
    print(t['title'], t['url'])
```

---

## 第七步：自然语言任务模式

`task` 命令让你用自然语言描述要做什么，系统会自动分析页面并执行安全操作：

```bash
# 截图
python3 win_browser.py task "截图当前页面"

# 检查媒体
python3 win_browser.py task "检查有没有视频在播放"

# 点击操作
python3 win_browser.py task "点击登录按钮"
```

### 安全边界

`task` 命令遇到以下场景会**自动停止**并要求人工介入：

- 🔒 验证码 / CAPTCHA / 人机验证
- 💳 支付 / 付款 / 充值 / 转账
- 📝 注册 / 创建账号
- 🔐 MFA / 二次验证 / OTP
- ⚠️ 风控 / 安全验证

---

## 第八步：实战案例

### 案例 1：自动搜索百度

```python
import asyncio
from win_browser import PageCDP, pick_tab, ensure_cdp

async def baidu_search(query):
    ensure_cdp()
    import urllib.request, json
    with urllib.request.urlopen(f'http://127.0.0.1:9222/json/new?https://www.baidu.com') as r:
        json.loads(r.read())
    await asyncio.sleep(2)

    tab = pick_tab("baidu.com")
    async with PageCDP(tab) as p:
        # 找到搜索框并填入
        await p.eval(f'''
            document.getElementById("kw").value = "{query}";
            document.getElementById("kw").dispatchEvent(new Event("input", {{bubbles:true}}));
        ''')
        await asyncio.sleep(0.5)

        # 点击搜索按钮
        box = await p.eval('''
            (() => {
                const e = document.getElementById("su");
                const r = e.getBoundingClientRect();
                return {x: r.x + r.width/2, y: r.y + r.height/2};
            })()
        ''')
        await p.mouse_click(int(box['x']), int(box['y']))

        await asyncio.sleep(2)
        title = await p.eval("document.title")
        await p.screenshot("/tmp/baidu_result.png")
        print(f"搜索完成: {title}")

asyncio.run(baidu_search("Python 自动化"))
```

### 案例 2：利用已有登录态操作

```python
import asyncio
from win_browser import PageCDP, pick_tab, ensure_cdp

async def operate_logged_in_site():
    ensure_cdp()
    # 选中已经登录的标签页
    tab = pick_tab("目标网站域名")
    async with PageCDP(tab) as p:
        # 直接操作，Cookie 和登录态都在
        title = await p.eval("document.title")
        print(f"当前页面: {title}")

        # 执行需要登录才能做的操作
        await p.eval('''
            // 例如点击某个菜单
            document.querySelector(".nav-item-xxx").click();
        ''')
        await asyncio.sleep(1)
        await p.screenshot("/tmp/operation_result.png")

asyncio.run(operate_logged_in_site())
```

### 案例 3：批量截图

```python
import asyncio
from win_browser import PageCDP, pick_tab, ensure_cdp, tabs

async def screenshot_all_tabs():
    ensure_cdp()
    for i, tab in enumerate(tabs()):
        if tab.get('url', '').startswith('devtools://'):
            continue
        async with PageCDP(tab) as p:
            safe_title = "".join(c if c.isalnum() else "_" for c in tab.get('title', 'unknown'))[:50]
            path = f"/tmp/tab_{i}_{safe_title}.png"
            await p.screenshot(path)
            print(f"✅ {tab['title'][:40]} → {path}")

asyncio.run(screenshot_all_tabs())
```

---

## 常见问题

### Q: 连接失败 `CDP not reachable`

**检查清单：**
1. ✅ Windows Chrome 是用 `--remote-debugging-port=9222` 启动的吗？
2. ✅ 在 Windows 访问 `http://localhost:9222/json/version` 能看到 JSON 吗？
3. ✅ CDP 代理已启动了吗？（`python3 cdp_proxy.py`）
4. ✅ `no_proxy` 和 `NO_PROXY` 环境变量设了吗？

```bash
# 快速检查
curl http://127.0.0.1:9222/json/version
echo $no_proxy $NO_PROXY
```

### Q: WebSocket 连接超时

通常是代理问题。确保：
```bash
export no_proxy="127.0.0.1,localhost"
export NO_PROXY="127.0.0.1,localhost"
```

### Q: Chrome 端口被占用

```bash
# Windows PowerShell 查看谁占了 9222
netstat -ano | findstr :9222
# 杀掉该进程
taskkill /PID <PID> /F
```

### Q: 操作后页面没反应

可能页面还在加载，加个等待：
```bash
python3 win_browser.py wait --selector "目标元素" --timeout 5000
```

### Q: 截图是空白的

页面可能还没渲染完，操作前先等一下：
```python
await asyncio.sleep(2)
await p.screenshot("/tmp/page.png")
```

### Q: 想保留正常 Chrome 的登录态

用同一个 `--user-data-dir` 启动：
```powershell
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\Users\你的用户名\AppData\Local\Google\Chrome\User Data"
```

> ⚠️ 同一目录不能被两个 Chrome 实例同时使用。先关掉普通 Chrome 再启动调试版。

### Q: 从远程服务器（非本机 WSL）连接

`.env` 中设置：
```bash
CDP_HTTP=http://192.168.x.x:9222  # Windows 机器的实际 IP
```

确保 Windows 防火墙允许 9222 端口入站。

### Q: 如何用 Playwright/Puppeteer 控制已有 Chrome？

它们都支持 `connect_over_cdp`：

```python
# Playwright Python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    context = browser.contexts[0]  # 使用已有上下文（含 Cookie）
    page = context.pages[0]
    print(page.title())
```

```javascript
// Puppeteer (Node.js)
const puppeteer = require('puppeteer-core');
const browser = await puppeteer.connect({
  browserURL: 'http://127.0.0.1:9222'
});
const pages = await browser.pages();
console.log(await pages[0].title());
```

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `cdp_proxy.py` | CDP 反向代理，桥接 WSL 和 Windows Chrome |
| `win_browser.py` | 浏览器控制器，CLI + Python 库 |
| `tcp_proxy.py` | 通用 TCP 代理（备用） |
| `.env` | 配置文件 |
| `requirements.txt` | Python 依赖 |
