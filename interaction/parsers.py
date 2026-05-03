PRODUCT_TYPES = {
    "laptop": ["laptop", "laptops", "computer", "notebook"],
    "gaming": ["gaming", "gaming laptop", "gamer"],
    "ultrabook": ["ultrabook", "ultra book", "thin"],
    "2-in-1": ["2 in 1", "two in one", "convertible", "hybrid", "tablet"],
}

# Spoken numbers Vosk produces; map to integers
SCREEN_SIZE_WORDS = {
    "thirteen":   13,
    "fourteen":   14,
    "fifteen":    15,
    "sixteen":    16,
    "seventeen":  17,
}


def _norm(text: str) -> str:
    return (text or "").lower().strip()


def parse_product_type(text: str):
    t = _norm(text)
    for canonical, aliases in PRODUCT_TYPES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            if alias in t:
                return canonical
    return None


def parse_screen_size(text: str):
    import re
    t = _norm(text)
    for word in sorted(SCREEN_SIZE_WORDS, key=len, reverse=True):
        if word in t:
            return SCREEN_SIZE_WORDS[word]
    m = re.search(r"\b(1[3-7])\b", t)
    return int(m.group(1)) if m else None