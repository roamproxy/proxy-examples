"""Local forwarder that injects Proxy-Authorization, so the browser sees a
proxy with no auth and needs no request interception.

    UPSTREAM=gw.roamproxy.com:41080 PROXY_USER=alice-country-us PROXY_PASS=... python auth_forwarder.py

Then point the browser at http://127.0.0.1:18081. Covers HTTPS (CONNECT); for
plain-HTTP keep-alive, rewrite every request head, not just the first.
Why: Playwright + an authenticated proxy can hang on google.com over HTTP/2
(Chrome restarts the navigation after an ACCEPT_CH frame and the restart is
lost under request interception). Without proxy auth in the browser, it works.
"""
import asyncio, base64, os

LISTEN = ("127.0.0.1", 18081)
UP_HOST, UP_PORT = os.environ["UPSTREAM"].rsplit(":", 1)
TOKEN = base64.b64encode(
    f"{os.environ['PROXY_USER']}:{os.environ['PROXY_PASS']}".encode()).decode()

async def pipe(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except ConnectionError:
        pass
    finally:
        writer.close()

async def handle(c_reader, c_writer):
    head = await c_reader.readuntil(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    lines = [l for l in lines if not l.lower().startswith("proxy-authorization:")]
    lines.insert(1, f"Proxy-Authorization: Basic {TOKEN}")
    u_reader, u_writer = await asyncio.open_connection(UP_HOST, int(UP_PORT))
    u_writer.write("\r\n".join(lines).encode("latin-1"))
    await u_writer.drain()
    await asyncio.gather(pipe(c_reader, u_writer), pipe(u_reader, c_writer))

async def main():
    async with await asyncio.start_server(handle, *LISTEN) as server:
        await server.serve_forever()

asyncio.run(main())
