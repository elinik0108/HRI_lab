import re


SHOE_TYPES = {
    "sneaker": ["sneaker", "sneakers", "trainer", "trainers"],
    "boot": ["boot", "boots"],
    "sandal": ["sandal", "sandals"],
    "running": ["running", "runner", "running shoe", "running shoes"],
}

COLORS = ["white", "black", "red", "blue", "brown", "green", "yellow", "grey", "gray"]

NUMBER_WORDS = {
    "thirty five": 35, "thirty six": 36, "thirty seven": 37, "thirty eight": 38, "thirty nine": 39,
    "forty": 40, "forty one": 41, "forty two": 42, "forty three": 43, "forty four": 44,
    "forty five": 45, "forty six": 46, "forty seven": 47, "forty eight": 48, "forty nine": 49,
    "fifty": 50, "fifty one": 51, "fifty two": 52, "fifty three": 53, "fifty four": 54, "fifty five": 55,
}


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
    t = _norm(text)
    for phrase in sorted(NUMBER_WORDS, key=len, reverse=True):
        if phrase in t:
            return NUMBER_WORDS[phrase]
    m = re.search(r"\b(3[5-9]|4[0-9]|5[0-9])\b", t)
    return int(m.group(1)) if m else None