import re


SHOE_TYPES = {
    "sneaker": ["sneaker", "sneakers", "trainer", "trainers"],
    "boot": ["boot", "boots"],
    "sandal": ["sandal", "sandals"],
    "running": ["running", "runner", "running shoe", "running shoes"],
}

COLORS = ["white", "black", "red", "blue", "brown", "green", "yellow", "grey", "gray"]


def _norm(text: str) -> str:
    return (text or "").lower().strip()


def parse_shoe_type(text: str):
    t = _norm(text)
    for canonical, aliases in SHOE_TYPES.items():
        if any(a in t for a in aliases):
            return canonical
    return None


def parse_color(text: str):
    t = _norm(text)
    for c in COLORS:
        if c in t:
            return "gray" if c == "grey" else c
    return None


def parse_size(text: str):
    m = re.search(r"\b(3[5-9]|4[0-9]|50)\b", _norm(text))   # sizes for shoes between 35-50 regEx
    return int(m.group(1)) if m else None