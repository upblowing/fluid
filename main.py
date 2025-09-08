import asyncio
import sys
from functions.persistence import load_or_create_id
from functions.app import App

async def main():
    if len(sys.argv) < 3:
        print("invalid usage, main.py [host] [port]")
        sys.exit(1)
    host = sys.argv[1]
    port = int(sys.argv[2])
    my_id = load_or_create_id()

    app = App(host, port, my_id)
    await app.connect()

    task_net = asyncio.create_task(app.network_reader())
    try:
        await app.run_ui()
    finally:
        if not task_net.done():
            task_net.cancel()
            try:
                await task_net
            except asyncio.CancelledError:
                pass
        try:
            if app.writer is not None:
                app.writer.close()
                await app.writer.wait_closed()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
