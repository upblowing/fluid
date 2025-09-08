import json
from typing import Any

async def send_json(writer, obj: Any):
    writer.write((json.dumps(obj) + "\n").encode("utf-8"))
    await writer.drain()
