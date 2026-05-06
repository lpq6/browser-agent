# win-chrome-cdp

从 WSL 控制 Windows Chrome 浏览器 —— 通过 CDP (Chrome DevTools Protocol) 反向代理桥接。

## 为什么需要这个？

WSL2 无法直接访问 Windows 的 localhost。如果 Windows Chrome 开启了 `--remote-debugging-port=9222`，WSL 里的工具（Playwright、Puppeteer、自定义脚本）直连 `localhost:9222` 会失败。

本项目提供两个工具：

| 文件 | 作用 |
|------|------|
| `cdp_proxy.py` | CDP 反向代理：WSL localhost → HTTP 代理 → Windows Chrome |
| `win_browser.py` | 浏览器控制器：通过 CDP 操控 Chrome（CLI + Python 库） |

## 快速开始

### 1. 启动 Windows Chrome（带远程调试）

```powershell
# Windows PowerShell
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\tmp\chrome-debug"
```

### 2. 启动 CDP 反向代理

```bash
# WSL
python3 cdp_proxy.py
```

### 3. 控制浏览器

```bash
python3 win_browser.py status
python3 win_browser.py open "https://example.com"
python3 win_browser.py screenshot /tmp/page.png
python3 win_browser.py snapshot
python3 win_browser.py click "登录"
python3 win_browser.py fill 'input[name="email"]' 'test@example.com'
python3 win_browser.py task "截图当前页面"
```

## 配置

环境变量或 `.env` 文件：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CDP_PROXY_TARGET` | `localhost:9222` | Windows Chrome CDP 地址 |
| `CDP_PROXY_LISTEN` | `127.0.0.1:9222` | 代理监听地址 |
| `CDP_HTTP` | `http://127.0.0.1:9222` | win_browser 连接的 CDP 地址 |
| `HTTP_PROXY` | (可选) | 上游 HTTP 代理地址 |

## 命令参考

```
status                          # 列出 Chrome 标签页
open <url>                      # 打开新标签页
snapshot [--target <keyword>]   # DOM 快照
find <text>                     # 搜索可见元素
click <text>                    # 按文字点击
click --selector <css>          # 按选择器点击
click --index <n>               # 按索引点击
click-xy <x> <y>                # 按坐标点击
fill <selector> <value>         # 填充表单
type <text> [--selector <css>]  # 键入文字
press <key>                     # 按键 (Enter/Tab/Escape...)
scroll [--x N] [--y N]          # 滚动
wait --text <text>              # 等待文字出现
screenshot <path> [--full-page] # 截图
media                           # 检查音视频状态
task <natural language>          # 自然语言任务（安全模式）
```

## 安全边界

`task` 命令自动检测风险场景并**停止操作**：

- 验证码 / CAPTCHA / 人机验证
- 支付 / 付款 / 充值 / 转账
- 注册 / 创建账号
- MFA / 二次验证 / OTP
- 风控 / 安全验证

## 作为 Python 库使用

```python
import asyncio
from win_browser import PageCDP, pick_tab, tabs, ensure_cdp

async def main():
    ensure_cdp()
    tab = pick_tab("example.com")
    async with PageCDP(tab) as page:
        title = await page.eval("document.title")
        await page.screenshot("/tmp/example.png")
        await page.mouse_click(500, 300)

asyncio.run(main())
```

## 依赖

```bash
pip install websockets httpx
```

## License

MIT
