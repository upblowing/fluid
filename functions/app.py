import curses
import asyncio
import json
from typing import Optional
from functions.net import send_json
from ui.curses_ui import CursesUI

class App:
    def __init__(self, host: str, port: int, my_id: str):
        self.host = host
        self.port = port
        self.my_id = my_id
        self.reader = None
        self.writer = None
        self.ui: Optional[CursesUI] = None
        self.event_q: asyncio.Queue = asyncio.Queue()

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        await send_json(self.writer, {"type": "register", "id": self.my_id})
        await self.event_q.put(("info", f"Connected to {self.host}:{self.port}"))

    async def network_reader(self):
        reader = self.reader
        try:
            while True:
                line = await reader.readline()
                if not line:
                    await self.event_q.put(("info", "disconnected from server"))
                    break
                try:
                    msg = json.loads(line.decode("utf-8").strip())
                except Exception:
                    await self.event_q.put(("info", "invalid frame from server"))
                    continue
                t = msg.get("type")
                if t == "deliver":
                    await self.event_q.put(("deliver", msg))
                elif t == "sent":
                    pass
                elif t == "nodeliver":
                    await self.event_q.put(("nodeliver", msg))
                elif t == "registered":
                    await self.event_q.put(("registered", msg))
                elif t == "info":
                    await self.event_q.put(("info", msg.get("message")))
                elif t == "error":
                    await self.event_q.put(("error", msg.get("error")))
                elif t == "chat_request":
                    await self.event_q.put(("chat_request", msg.get("from")))
                elif t == "chat_accept":
                    await self.event_q.put(("chat_accept", msg.get("from")))
                elif t == "chat_reject":
                    await self.event_q.put(("chat_reject", msg.get("from")))
                elif t == "chat_message":
                    await self.event_q.put(("chat_message", msg))
        except asyncio.CancelledError:
            pass

    def _apply_event(self, kind: str, payload):
        ui = self.ui
        if not ui:
            return
        if kind == "info":
            ui.log_line(f"[system] {payload}")
        elif kind == "error":
            ui.log_line(f"[error] {payload}")
        elif kind == "registered":
            ui.log_line(f"[system] session registered as {payload.get('id')}")
        elif kind == "nodeliver":
            ui.log_line(f"[system] user {payload.get('to')} is offline")
        elif kind == "deliver":
            ui.log_line(f"[from {payload.get('from')}]: {payload.get('payload','')}")
        elif kind == "chat_message":
            ui.log_line(f"(chat) {payload.get('from')}: {payload.get('payload','')}")
        elif kind == "chat_request":
            from_id = payload
            ui.show_chat_request_modal(from_id)
        elif kind == "chat_accept":
            from_id = payload
            ui.set_chat_peer(from_id)
            ui.log_line(f"[chat] {from_id} accepted your chat")
        elif kind == "chat_reject":
            from_id = payload
            ui.log_line(f"[chat] {from_id} rejected your chat request")

    async def _handle_command(self, cmd: str):
        if cmd.startswith("__MODAL__:"):
            choice = cmd.split(":", 1)[1]
            from_id = self.ui.pending_from
            if choice == "accept" and from_id:
                await send_json(self.writer, {"type": "chat_accept", "to": from_id})
                self.ui.set_chat_peer(from_id)
                self.ui.set_pending_from(None)
                self.ui.log_line(f"accepted chat with {self.ui.chat_peer}.")
            elif choice == "reject" and from_id:
                await send_json(self.writer, {"type": "chat_reject", "to": from_id})
                self.ui.log_line(f"rejected chat with {from_id}.")
                self.ui.set_pending_from(None)
            return

        text = cmd

        if self.ui.chat_peer:
            if text == "/leave":
                self.ui.log_line(f"left chat {self.ui.chat_peer}.")
                self.ui.set_chat_peer(None)
            else:
                await send_json(self.writer, {"type": "chat_message", "to": self.ui.chat_peer, "payload": text})
                self.ui.log_line(f"[me] {text}")
            return

        if text.startswith("/chat "):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                self.ui.log_line("usage: /chat <peer_id>")
                return
            to = parts[1]
            await send_json(self.writer, {"type": "chat_request", "to": to})
            self.ui.log_line(f"requested {to}")
            return

        if text == "/whoami":
            self.ui.log_line(self.my_id)
            return

        if text == "/help":
            self.ui.log_line(
                "Commands:\n"
                "  /chat <peer_id>           start a chat session\n"
                "  /leave                    leave chat session\n"
                "  /quit                     exit"
            )
            return

        if text == "/quit":
            self.ui.should_exit = True
            return

        self.ui.log_line("unknown command")

    async def run_ui(self):
        stdscr = curses.initscr()
        try:
            curses.noecho()
            curses.cbreak()
            stdscr.keypad(True)

            self.ui = CursesUI(stdscr, self.my_id)
            self.ui.log_line("/help to view all commands")
            self.ui.draw()

            while not self.ui.should_exit:
                drained = 0
                try:
                    while True:
                        kind, payload = self.event_q.get_nowait()
                        self._apply_event(kind, payload)
                        drained += 1
                except asyncio.QueueEmpty:
                    pass

                try:
                    ch = stdscr.getch()
                except Exception:
                    ch = -1

                if ch != -1:
                    cmd = self.ui.handle_key(ch)
                    if cmd is not None:
                        await self._handle_command(cmd)

                self.ui.draw()
                await asyncio.sleep(0.01)

        finally:
            try:
                curses.nocbreak()
                stdscr.keypad(False)
                curses.echo()
            except Exception:
                pass
            curses.endwin()
