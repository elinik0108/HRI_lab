from dataclasses import dataclass
from typing import Optional

@dataclass
class Product:
    id:              str
    type:            str
    screen:          int
    price:           float
    location:        str
    marker_label:    Optional[str] = None
    table_angle_deg: float = 0.0

    def matches(self, product_type=None, screen=None, max_price=None) -> bool:
        if product_type and self.type != product_type:
            return False
        if screen       and self.screen != screen:
            return False
        if max_price    and self.price > max_price:
            return False
        return True