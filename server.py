import asyncio, json, signal
from typing import Dict

CLIENTS: Dict[str, asyncio.StreamWriter] = {}
CHAT_SESSIONS: Dict[str, str] = {}  # key: user, value: peer
PENDING_CHATS: Dict[str, str] = {}   # key: target, value: requester

async def send_json(writer: asyncio.StreamWriter, obj: dict):
    data = (json.dumps(obj) + "\n").encode("utf-8")
    writer.write(data)
    await writer.drain()

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    client_id = None
    try:
        line = await reader.readline()
        if not line:
            writer.close(); await writer.wait_closed(); return
        try:
            msg = json.loads(line.decode('utf-8').strip())
        except json.JSONDecodeError:
            await send_json(writer, {"type": "error", "error": "invalid_json"})
            writer.close(); await writer.wait_closed(); return

        if msg.get("type") != "register" or "id" not in msg:
            await send_json(writer, {"type": "error", "error": "must_register_first"})
            writer.close(); await writer.wait_closed(); return

        client_id = str(msg["id"])[:128]

        old = CLIENTS.get(client_id)
        if old:
            try:
                await send_json(old, {"type": "info", "message": "signed_in_elsewhere"})
                old.close()
            except Exception:
                pass
        CLIENTS[client_id] = writer
        await send_json(writer, {"type": "registered", "id": client_id})
        print(f"+ {client_id} connected")

        while not reader.at_eof():
            line = await reader.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode('utf-8').strip())
            except json.JSONDecodeError:
                await send_json(writer, {"type": "error", "error": "invalid_json"})
                continue

            mtype = msg.get("type")
            if mtype == "send":
                to = msg.get("to"); payload = msg.get("payload", "")
                if not to:
                    await send_json(writer, {"type": "error", "error": "missing_to"})
                    continue
                target = CLIENTS.get(to)
                if not target:
                    await send_json(writer, {"type": "nodeliver", "to": to})
                else:
                    await send_json(target, {"type": "deliver", "from": client_id, "payload": payload})
                    await send_json(writer, {"type": "sent", "to": to})
            elif mtype == "chat_request":
                to = msg.get("to")
                if not to or to == client_id:
                    await send_json(writer, {"type": "error", "error": "invalid_chat_target"})
                    continue
                target = CLIENTS.get(to)
                if not target:
                    await send_json(writer, {"type": "nodeliver", "to": to})
                elif CHAT_SESSIONS.get(client_id) or CHAT_SESSIONS.get(to):
                    await send_json(writer, {"type": "error", "error": "already_in_chat"})
                else:
                    PENDING_CHATS[to] = client_id
                    await send_json(target, {"type": "chat_request", "from": client_id})
            elif mtype == "chat_accept":
                from_id = PENDING_CHATS.get(client_id)
                if not from_id:
                    await send_json(writer, {"type": "error", "error": "no_pending_chat"})
                    continue
                peer_writer = CLIENTS.get(from_id)
                if peer_writer:
                    CHAT_SESSIONS[client_id] = from_id
                    CHAT_SESSIONS[from_id] = client_id
                    await send_json(peer_writer, {"type": "chat_accept", "from": client_id})
                    await send_json(writer, {"type": "chat_accept", "from": from_id})
                PENDING_CHATS.pop(client_id, None)
            elif mtype == "chat_reject":
                from_id = PENDING_CHATS.get(client_id)
                if from_id:
                    peer_writer = CLIENTS.get(from_id)
                    if peer_writer:
                        await send_json(peer_writer, {"type": "chat_reject", "from": client_id})
                PENDING_CHATS.pop(client_id, None)
                await send_json(writer, {"type": "info", "message": "chat request rejected"})
            elif mtype == "chat_message":
                to = msg.get("to")
                payload = msg.get("payload", "")
                if CHAT_SESSIONS.get(client_id) == to and CHAT_SESSIONS.get(to) == client_id:
                    target = CLIENTS.get(to)
                    if target:
                        await send_json(target, {"type": "chat_message", "from": client_id, "payload": payload})
                else:
                    await send_json(writer, {"type": "error", "error": "not_in_chat"})
            elif mtype == "ping":
                await send_json(writer, {"type": "pong"})
            else:
                await send_json(writer, {"type": "error", "error": "unknown_type"})
    except Exception as e:
        try:
            await send_json(writer, {"type": "error", "error": "server_exception"})
        except Exception:
            pass
    finally:
        if client_id and CLIENTS.get(client_id) is writer:
            CLIENTS.pop(client_id, None)
            print(f"- {client_id} disconnected")
            peer = CHAT_SESSIONS.pop(client_id, None)
            if peer:
                CHAT_SESSIONS.pop(peer, None)
                peer_writer = CLIENTS.get(peer)
                if peer_writer:
                    try:
                        await send_json(peer_writer, {"type": "info", "message": f"chat ended with {client_id}"})
                    except Exception:
                        pass
            for k, v in list(PENDING_CHATS.items()):
                if k == client_id or v == client_id:
                    PENDING_CHATS.pop(k, None)
        try:
            writer.close(); await writer.wait_closed()
        except Exception:
            pass

async def main(host="0.0.0.0", port=4040):
    server = await asyncio.start_server(handle_client, host, port)
    print(f"relay running on {host}:{port}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
