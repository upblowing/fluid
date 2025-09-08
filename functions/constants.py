import pathlib

APP_DIR = pathlib.Path.cwd()
APP_DIR.mkdir(parents=True, exist_ok=True)
ID_FILE = APP_DIR / "id.txt"

PROMPT = "> "
CHAT_PROMPT = "(chat)> "
