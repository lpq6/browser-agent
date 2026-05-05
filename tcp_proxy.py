"""
TCP Proxy Bridge
将 WSL 的 localhost:9222 转发到 Windows Chrome (通过 HTTP 代理)
"""
import asyncio
import sys

PROXY_HOST = "192.168.31.215"
PROXY_PORT = 7890
LOCAL_PORT = 9222

async def handle_client(reader, writer):
    """处理来自 Playwright 的连接"""
    addr = writer.get_extra_info('peername')
    print(f"[连接] {addr}")
    
    try:
        # 通过 HTTP CONNECT 代理连接到 Windows Chrome
        proxy_reader, proxy_writer = await asyncio.open_connection(PROXY_HOST, PROXY_PORT)
        
        # 发送 CONNECT 请求
        connect_req = f"CONNECT localhost:9222 HTTP/1.1\r\nHost: localhost:9222\r\n\r\n"
        proxy_writer.write(connect_req.encode())
        await proxy_writer.drain()
        
        # 读取代理响应
        response = await proxy_reader.readuntil(b"\r\n\r\n")
        status = response.decode().split('\r\n')[0]
        
        if "200" not in status:
            print(f"[错误] 代理拒绝: {status}")
            writer.close()
            proxy_writer.close()
            return
        
        print(f"[代理] CONNECT 成功")
        
        # 双向转发数据
        async def forward(src, dst, name):
            try:
                while True:
                    data = await src.read(8192)
                    if not data:
                        break
                    dst.write(data)
                    await dst.drain()
            except Exception as e:
                pass
            finally:
                try:
                    dst.close()
                except:
                    pass
        
        # 同时转发两个方向
        await asyncio.gather(
            forward(reader, proxy_writer, "client->proxy"),
            forward(proxy_reader, writer, "proxy->client")
        )
        
    except Exception as e:
        print(f"[错误] {e}")
    finally:
        try:
            writer.close()
        except:
            pass
        print(f"[断开] {addr}")

async def main():
    server = await asyncio.start_server(handle_client, '127.0.0.1', LOCAL_PORT)
    addr = server.sockets[0].getsockname()
    print(f"🚀 TCP 代理启动: {addr[0]}:{addr[1]}")
    print(f"📡 转发到: {PROXY_HOST}:{PROXY_PORT} -> localhost:9222")
    print(f"💡 Playwright 现在可以通过 ws://127.0.0.1:{LOCAL_PORT} 连接 Chrome")
    print(f"按 Ctrl+C 停止")
    
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 代理已停止")
