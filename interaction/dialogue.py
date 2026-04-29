import random
import json
from pathlib import Path

class Dialogue:
    def __init__(self, path: str = None):
        if path is None:
            path = Path(__file__).parent / "dialogue.json"
        self._lines = json.load(Path(path).read_text(encoding="utf-8"))

    def get(self, key: str, **kwargs) -> str:
        if key not in self._lines:
            raise KeyError(f"Error: dialogue not found!")
        line = self._lines[key]
        if isinstance(line, list):
            line = random.choice(line)
        try:
            return line.format(**kwargs)
        except KeyError as e:
            raise KeyError(f"Missing placeholder {e} for a dialogue key.") from e