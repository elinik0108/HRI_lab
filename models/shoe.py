from dataclasses import dataclass
from typing import List

@dataclass
class Shoe:
    id: str
    type: str
    color: str
    sizes: List[int]
    price: float
    location: str

    def matches(self, shoe_type=None, color=None, size=None, max_price=None) -> bool:
        if shoe_type and self.type != shoe_type:    
            return False
        if color and self.color != color:       
            return False
        if size and size not in self.sizes:    
            return False
        if max_price and self.price > max_price:    
            return False

        return True