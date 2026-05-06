#!/usr/bin/env python3
"""
CDP Reverse Proxy — WSL → Windows Chrome

在 WSL 上做反向代理，将 localhost 的 CDP 请求通过 HTTP 代理转发到 Windows Chrome。
支持 HTTP 和 WebSocket（Chrome DevTools Protocol 需要两者）。

环境变量:
    CDP_PROXY_TARGET    目标地址，默认 localhost:9222
    CDP_PROXY_LISTEN    监听地址，默认 127.0.0.1:9222
    HTTP_PROXY          上游 HTTP 代理（可选）
"""
import asyncio
import os
import sys


def _parse_addr(s, default_host="127.0.0.1", default_port=9222):
    if ":" in s:
        host, port = s.rsplit(":", 1)
        return host, int(port)
    return s, default_port


TARGET = os.environ.get("CDP_PROXY_TARGET", "localhost:9222")
LISTEN = os.environ.get("CDP_PROXY_LISTEN", "127.0.0.1:9222")
HTTP_PROXY = os.environ.get("HTTP_PROXY", os.environ.get("http_proxy", ""))

TARGET_HOST, TARGET_PORT = _parse_addr(TARGET, "localhost", 9222)
LISTEN_HOST, LISTEN_PORT = _parse_addr(LISTEN, "127.0.0.1", 9222)

PROXY_HOST, PROXY_PORT = (None, None)
if HTTP_PROXY:
    proxy_clean = HTTP_PROXY.replace("http://", "").replace("https://", "").rstrip("/")
    PROXY_HOST, PROXY_PORT = _parse_addr(proxy_clean, "127.0.0.1", 7890)


async def _fwd(reader, writer):
    try:
        while True:
            data = await reader.read(16384)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (asyncio.IncompleteReadError, ConnectionResetError, OSError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _handle_ws_via_connect(reader, writer, full_request):
    if not PROXY_HOST:
        try:
            target_r, target_w = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)
            target_w.write(full_request)
            await target_w.drain()
            await asyncio.gather(_fwd(reader, target_w), _fwd(target_r, writer))
        except Exception as e:
            print(f"❌ WebSocket 直连失败: {e}", file=sys.stderr)
            writer.close()
        return

    try:
        proxy_r, proxy_w = await asyncio.open_connection(PROXY_HOST, PROXY_PORT)
        connect_req = f"CONNECT {TARGET_HOST}:{TARGET_PORT} HTTP/1.1\r\nHost: {TARGET_HOST}:{TARGET_PORT}\r\n\r\n"
        proxy_w.write(connect_req.encode())
        await proxy_w.drain()

        resp = await proxy_r.readuntil(b"\r\n\r\n")
        if b"200" not in resp:
            print(f"❌ CONNECT 隧道失败: {resp.decode(errors='replace').strip()}", file=sys.stderr)
            writer.close()
            proxy_w.close()
            return

        proxy_w.write(full_request)
        await proxy_w.drain()
        await asyncio.gather(_fwd(reader, proxy_w), _fwd(proxy_r, writer))
    except Exception as e:
        print(f"❌ WebSocket 代理失败: {e}", file=sys.stderr)
        writer.close()


async def _handle_http_direct(reader, writer, method, path, headers_raw):
    try:
        target_r, target_w = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)
        target_w.write(f"{method} {path} HTTP/1.1\r\n{headers_raw}\r\n".encode())
        await target_w.drain()
        resp = await target_r.read(65536)
        writer.write(resp)
        await writer.drain()
        target_w.close()
    except Exception as e:
        print(f"❌ HTTP 直连失败: {e}", file=sys.stderr)
    finally:
        writer.close()


async def _handle_http_via_proxy(writer, method, url, headers_raw):
    try:
        proxy_r, proxy_w = await asyncio.open_connection(PROXY_HOST, PROXY_PORT)
        proxy_w.write(f"{method} {url} HTTP/1.1\r\n{headers_raw}\r\n".encode())
        await proxy_w.drain()
        resp = await proxy_r.read(65536)
        writer.write(resp)
        await writer.drain()
        proxy_w.close()
    except Exception as e:
        print(f"❌ HTTP 代理失败: {e}", file=sys.stderr)
    finally:
        writer.close()


async def handle_client(reader, writer):
    try:
        first_line = await asyncio.wait_for(reader.readline(), timeout=10)
        if not first_line:
            writer.close()
            return

        headers = b""
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=10)
            headers += line
            if line in (b"\r\n", b"\n", b""):
                break

        full_request = first_line + headers
        is_ws = b"Upgrade: websocket" in headers or b"upgrade: websocket" in headers

        if is_ws:
            await _handle_ws_via_connect(reader, writer, full_request)
        else:
            method_line = first_line.decode(errors="replace").strip()
            parts = method_line.split()
            if len(parts) >= 2:
                method, path = parts[0], parts[1]
                url = f"http://{TARGET_HOST}:{TARGET_PORT}{path}"
                headers_str = headers.decode(errors="replace")
                if PROXY_HOST:
                    await _handle_http_via_proxy(writer, method, url, headers_str)
                else:
                    await _handle_http_direct(reader, writer, method, path, headers_str)
            else:
                writer.close()
    except asyncio.TimeoutError:
        writer.close()
    except Exception as e:
        print(f"❌ 处理错误: {e}", file=sys.stderr)
        try:
            writer.close()
        except Exception:
            pass


async def main():
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    proxy_info = f"{PROXY_HOST}:{PROXY_PORT}" if PROXY_HOST else "直连（无代理）"
    print(f"🚀 CDP 反向代理启动: {LISTEN_HOST}:{LISTEN_PORT}")
    print(f"📡 转发到: {TARGET_HOST}:{TARGET_PORT}")
    print(f"🔗 上游代理: {proxy_info}")
    print(f"✅ 支持 HTTP + WebSocket (CDP)")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 代理已停止")
