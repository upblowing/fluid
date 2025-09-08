from typing import Tuple

class Button:
    def __init__(self, label: str):
        self.label = label
        self.bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)  # y, x, h, w

    def set_bounds(self, y, x, h, w):
        self.bounds = (y, x, h, w)

    def contains(self, my, mx) -> bool:
        y, x, h, w = self.bounds
        return y <= my < y + h and x <= mx < x + w

class Modal:
    def __init__(self, title: str, message: str, buttons: Tuple[Button, ...]):
        self.title = title
        self.message = message
        self.buttons = list(buttons)
        self.selected = 0

    def next(self):
        self.selected = (self.selected + 1) % len(self.buttons)

    def prev(self):
        self.selected = (self.selected - 1) % len(self.buttons)
