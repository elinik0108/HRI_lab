""" 
class ShoeCatalog:
    def __init__(self, shoes=None):
        self.shoes = shoes or []

    @classmethod
    def load(cls, path):
        return cls(shoes=[])
        
        
 """

import json
from pathlib import Path
from typing import List, Optional
from .shoe import Shoe


class ShoeCatalog:
    def __init__(self, shoes: List[Shoe]):
        self.shoes = shoes

    @classmethod
    def load(cls, path: str) -> "ShoeCatalog":
        data = json.loads(Path(path).read_text())
        return cls([Shoe(**row) for row in data])

    def filter(self, shoe_type=None, color=None, size=None, max_price=None) -> List[Shoe]:
        return [s for s in self.shoes
                if s.matches(shoe_type, color, size, max_price)]

    def by_id(self, shoe_id: str) -> Optional[Shoe]:
        return next((s for s in self.shoes if s.id == shoe_id), None)

    def all(self) -> List[Shoe]:
        return list(self.shoes)

    def types(self):
        return sorted({s.type for s in self.shoes})