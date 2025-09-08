import curses
from collections import deque
from typing import Deque, Tuple, Optional
from .widgets import Button, Modal
from functions.constants import PROMPT, CHAT_PROMPT

class CursesUI:
    def __init__(self, stdscr, my_id: str):
        self.stdscr = stdscr
        self.my_id = my_id

        self.max_log_lines = 2000
        self.log: Deque[str] = deque(maxlen=self.max_log_lines)

        self.input_history: Deque[str] = deque(maxlen=300)
        self.history_index: Optional[int] = None
        self.input_buffer = ""
        self.cursor_pos = 0

        self.chat_peer: Optional[str] = None
        self.pending_from: Optional[str] = None

        self.modal: Optional[Modal] = None
        self.should_exit = False

        self.scroll_offset = 0

        curses.curs_set(1)
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        curses.start_color()
        curses.use_default_colors()

        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE) 
        curses.init_pair(2, curses.COLOR_CYAN, -1)
        curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_CYAN)
        self.blue_bg = curses.color_pair(1)
        self.cyan_text = curses.color_pair(2)
        self.cyan_bg = curses.color_pair(3)

        self.stdscr.nodelay(True)
        self.stdscr.keypad(True)
        curses.noecho()
        curses.cbreak()

        self.stdscr.bkgd(' ', self.cyan_text)

    def draw(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        header = f" ur id {self.my_id} "
        status = f"status: {'chatting with ' + self.chat_peer if self.chat_peer else 'idle'}"
        pad = max(0, w - len(header) - len(status) - 1)
        header_line = header + " " * pad + status
        if w > 0:
            self.stdscr.addstr(0, 0, header_line[: w - 1], curses.A_BOLD | self.cyan_bg)

        self._hline(1, w)

        log_top = 2
        input_height = 3
        log_bottom = max(log_top, h - input_height)
        log_height = max(0, log_bottom - log_top)
        self._draw_log(log_top, w, log_height)

        self._hline(log_bottom, w)

        prompt = CHAT_PROMPT if self.chat_peer else PROMPT
        self._draw_input(log_bottom + 1, w, prompt)

        help_text = "Keys: Enter=send  ↑/↓=history  PgUp/PgDn=scroll  Ctrl+U/Ctrl+K=kill  /help"
        if h - 1 >= 0 and w > 0:
            self.stdscr.addstr(h - 1, 0, help_text[: w - 1], self.blue_bg)

        if self.modal:
            self._draw_modal(self.modal)

        if not self.modal:
            cur_x = len(prompt) + self.cursor_pos
            cy = log_bottom + 1
            if 0 <= cy < h and 0 <= cur_x < w:
                self.stdscr.move(cy, cur_x)

        self.stdscr.refresh()

    def _draw_log(self, top: int, w: int, height: int):
        lines = list(self.log)

        wrapped = []
        wrapw = max(1, w - 1)
        for ln in lines:
            if not ln:
                wrapped.append("")
                continue
            start = 0
            while start < len(ln):
                wrapped.append(ln[start : start + wrapw])
                start += wrapw

        total = len(wrapped)
        start_index = max(0, total - height - self.scroll_offset)
        end_index = max(0, total - self.scroll_offset)
        visible = wrapped[start_index:end_index][-height:]

        y = top
        for ln in visible:
            if y >= top + height:
                break
            if w > 0:
                self.stdscr.addstr(y, 0, ln[: w - 1], self.cyan_text)
            y += 1

    def _draw_input(self, y: int, w: int, prompt: str):
        if y < curses.LINES and w > 0:
            self.stdscr.addstr(y, 0, prompt, self.blue_bg)
            self.stdscr.addstr(y, len(prompt), self.input_buffer[:w-len(prompt)-1], self.cyan_text)

    def _hline(self, y: int, w: int):
        if 0 <= y < curses.LINES and w > 0:
            self.stdscr.hline(y, 0, curses.ACS_HLINE, w - 1, self.cyan_text)

    def _draw_modal(self, modal: Modal):
        h, w = self.stdscr.getmaxyx()
        msg_w = max(len(modal.message) + 8, 40)
        box_w = min(max(40, msg_w), max(40, w - 4))
        box_h = 7
        y0 = max(0, (h - box_h) // 2)
        x0 = max(0, (w - box_w) // 2)

        for i in range(box_h):
            if 0 <= y0 + i < h:
                if i in (0, box_h - 1):
                    self.stdscr.hline(y0 + i, x0, curses.ACS_HLINE, max(1, box_w - 1), self.blue_bg)
                else:
                    self.stdscr.addch(y0 + i, x0, curses.ACS_VLINE, self.blue_bg)
                    self.stdscr.addch(y0 + i, x0 + box_w - 1, curses.ACS_VLINE, self.blue_bg)
        self.stdscr.addch(y0, x0, curses.ACS_ULCORNER, self.blue_bg)
        self.stdscr.addch(y0, x0 + box_w - 1, curses.ACS_URCORNER, self.blue_bg)
        self.stdscr.addch(y0 + box_h - 1, x0, curses.ACS_LLCORNER, self.blue_bg)
        self.stdscr.addch(y0 + box_h - 1, x0 + box_w - 1, curses.ACS_LRCORNER, self.blue_bg)

        title = f" {modal.title} "
        tx = x0 + max(1, (box_w - len(title)) // 2)
        self.stdscr.addstr(y0, tx, title[: max(0, box_w - 2)], curses.A_BOLD | self.cyan_bg)

        self.stdscr.addstr(y0 + 2, x0 + 2, modal.message[: max(0, box_w - 4)], self.cyan_text)

        labels = []
        for i, b in enumerate(modal.buttons):
            if i == modal.selected:
                labels.append(f"> [ {b.label} ] <")
            else:
                labels.append(f"[ {b.label} ]")
        buttons_line = "   ".join(labels)
        by = y0 + 4
        bx = x0 + max(2, (box_w - len(buttons_line)) // 2)

        x = bx
        for i, b in enumerate(modal.buttons):
            text = labels[i]
            try:
                start = text.index("[")
                end = text.index("]") + 1
            except ValueError:
                start, end = 0, len(text)

            if i == modal.selected:
                self.stdscr.addstr(by, x, text, self.blue_bg | curses.A_BOLD)
            else:
                self.stdscr.addstr(by, x, text, self.cyan_text)

            b.set_bounds(by, x + start, 1, max(1, end - start))
            x += len(text) + 3

    def log_line(self, s: str):
        for ln in s.splitlines() or [""]:
            self.log.append(ln)

    def set_chat_peer(self, peer: Optional[str]):
        self.chat_peer = peer

    def set_pending_from(self, f: Optional[str]):
        self.pending_from = f

    def show_chat_request_modal(self, from_id: str):
        self.pending_from = from_id
        self.modal = Modal(
            title="chat request",
            message=f"{from_id} wants to chat.",
            buttons=(Button("accept"), Button("reject")),
        )

    def handle_key(self, ch) -> Optional[str]:
        if self.modal:
            if ch in (curses.KEY_LEFT,):
                self.modal.prev()
                return None
            if ch in (curses.KEY_RIGHT,):
                self.modal.next()
                return None
            if ch == 9:
                self.modal.next()
                return None
            if ch == 353:
                self.modal.prev()
                return None
            if ch in (10, 13):
                choice = self.modal.buttons[self.modal.selected].label
                self.modal = None
                return f"__MODAL__:{choice}"
            if ch == 27:
                self.modal = None
                return None
            if ch == curses.KEY_MOUSE:
                try:
                    _, mx, my, _, bstate = curses.getmouse()
                    if bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED | curses.BUTTON1_RELEASED):
                        for i, btn in enumerate(self.modal.buttons):
                            if btn.contains(my, mx):
                                self.modal.selected = i
                                choice = btn.label
                                self.modal = None
                                return f"__MODAL__:{choice}"
                except Exception:
                    pass
            return None

        if ch in (10, 13):
            cmd = self.input_buffer.strip()
            if cmd:
                self.input_history.append(cmd)
            self.history_index = None
            self.input_buffer = ""
            self.cursor_pos = 0
            return cmd

        if ch == curses.KEY_LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
            return None
        if ch == curses.KEY_RIGHT:
            if self.cursor_pos < len(self.input_buffer):
                self.cursor_pos += 1
            return None
        if ch == curses.KEY_UP:
            self._history_prev()
            return None
        if ch == curses.KEY_DOWN:
            self._history_next()
            return None
        if ch == curses.KEY_PPAGE:
            self.scroll_offset = min(self.scroll_offset + 5, max(0, len(self.log) - 1))
            return None
        if ch == curses.KEY_NPAGE: 
            self.scroll_offset = max(0, self.scroll_offset - 5)
            return None

        if ch == 21:
            self.input_buffer = self.input_buffer[self.cursor_pos:]
            self.cursor_pos = 0
            return None
        if ch == 11: 
            self.input_buffer = self.input_buffer[: self.cursor_pos]
            return None
        if ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor_pos > 0:
                self.input_buffer = self.input_buffer[: self.cursor_pos - 1] + self.input_buffer[self.cursor_pos :]
                self.cursor_pos -= 1
            return None
        if ch == curses.KEY_DC:
            if self.cursor_pos < len(self.input_buffer):
                self.input_buffer = self.input_buffer[: self.cursor_pos] + self.input_buffer[self.cursor_pos + 1 :]
            return None

        if ch == curses.KEY_MOUSE:
            try:
                curses.getmouse()
            except Exception:
                pass
            return None

        if 32 <= ch <= 126:
            c = chr(ch)
            self.input_buffer = self.input_buffer[: self.cursor_pos] + c + self.input_buffer[self.cursor_pos :]
            self.cursor_pos += 1
            return None

        return None

    def _history_prev(self):
        if not self.input_history:
            return
        if self.history_index is None:
            self.history_index = len(self.input_history) - 1
        elif self.history_index > 0:
            self.history_index -= 1
        self.input_buffer = self.input_history[self.history_index]
        self.cursor_pos = len(self.input_buffer)

    def _history_next(self):
        if self.history_index is None:
            return
        if self.history_index < len(self.input_history) - 1:
            self.history_index += 1
            self.input_buffer = self.input_history[self.history_index]
        else:
            self.history_index = None
            self.input_buffer = ""
        self.cursor_pos = len(self.input_buffer)
