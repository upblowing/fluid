import uuid
from .constants import ID_FILE

def load_or_create_id() -> str:
    try:
        if ID_FILE.exists():
            existing = ID_FILE.read_text().strip()
            if existing:
                print(f"[system] your id: {existing}")
                choice = input("").strip()
                if choice:
                    ID_FILE.write_text(choice)
                    return choice
                return existing
    except Exception:
        pass
    new_id = str(uuid.uuid4()).replace("-", "")
    ID_FILE.write_text(new_id)
    return new_id
