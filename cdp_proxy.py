"""
CDP Reverse Proxy
在 WSL localhost:9222 上做反向代理，通过 HTTP 代理转发到 Windows Chrome
同时支持 HTTP 和 WebSocket（CDP 需要两者）
"""
import asyncio
import httpx

PROXY = "http://192.168.31.215:7890"
TARGET = "localhost:9222"
LISTEN_PORT = 9222

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    try:
        # Read the first line to determine if it's HTTP or WebSocket upgrade
        first_line = await asyncio.wait_for(reader.readline(), timeout=5)
        if not first_line:
            writer.close()
            return
        
        # Read rest of headers
        headers = b""
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            headers += line
            if line == b"\r\n" or line == b"\n" or not line:
                break
        
        full_request = first_line + headers
        
        # Check if this is a WebSocket upgrade
        is_websocket = b"Upgrade: websocket" in headers or b"upgrade: websocket" in headers
        
        if is_websocket:
            # WebSocket: use CONNECT tunnel
            proxy_r, proxy_w = await asyncio.open_connection(
                "192.168.31.215", 7890
            )
            proxy_w.write(f"CONNECT {TARGET} HTTP/1.1\r\nHost: {TARGET}\r\n\r\n".encode())
            await proxy_w.drain()
            
            resp = await proxy_r.readuntil(b"\r\n\r\n")
            if b"200" not in resp:
                writer.close()
                proxy_w.close()
                return
            
            # Forward the original upgrade request
            proxy_w.write(full_request)
            await proxy_w.drain()
            
            # Bridge both directions
            async def fwd(r, w):
                try:
                    while True:
                        data = await r.read(16384)
                        if not data:
                            break
                        w.write(data)
                        await w.drain()
                except:
                    pass
                try:
                    w.close()
                except:
                    pass
            
            await asyncio.gather(
                fwd(reader, proxy_w),
                fwd(proxy_r, writer)
            )
        else:
            # Regular HTTP: forward through proxy
            method_line = first_line.decode().strip()
            parts = method_line.split()
            if len(parts) >= 2:
                path = parts[1]
                # Build absolute URL
                url = f"http://{TARGET}{path}"
                
                async with httpx.AsyncClient(proxy=PROXY, timeout=10) as client:
                    # Reconstruct the request
                    resp = await client.request(
                        method=parts[0],
                        url=url,
                        headers={"Host": TARGET},
                    )
                    
                    # Send response back
                    status_line = f"HTTP/1.1 {resp.status_code} OK\r\n"
                    writer.write(status_line.encode())
                    for k, v in resp.headers.items():
                        if k.lower() not in ('transfer-encoding', 'connection'):
                            writer.write(f"{k}: {v}\r\n".encode())
                    writer.write(b"\r\n")
                    writer.write(resp.content)
                    await writer.drain()
            
            writer.close()
    except Exception as e:
        try:
            writer.close()
        except:
            pass

async def main():
    server = await asyncio.start_server(handle_client, '127.0.0.1', LISTEN_PORT)
    print(f"🚀 CDP 反向代理启动: 127.0.0.1:{LISTEN_PORT}")
    print(f"📡 转发到: {TARGET} (via {PROXY})")
    print(f"✅ 支持 HTTP + WebSocket (CDP)")
    print(f"💡 Playwright 现在可以 connect_over_cdp('http://127.0.0.1:{LISTEN_PORT}')")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 代理已停止")
