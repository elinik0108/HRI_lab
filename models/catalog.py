import json
from pathlib import Path
from typing import List, Optional
from .product import Product


class ProductCatalog:
    def __init__(self, products: List[Product]):
        self.products = products

    @classmethod
    def load(cls, path: str) -> "ProductCatalog":
        data = json.loads(Path(path).read_text())
        return cls([Product(**row) for row in data])

    def filter(self, product_type=None, screen=None, max_price=None) -> List[Product]:
        return [p for p in self.products
                if p.matches(product_type, screen, max_price)]

    def by_id(self, product_id: str) -> Optional[Product]:
        return next((p for p in self.products if p.id == product_id), None)

    def all(self) -> List[Product]:
        return list(self.products)

    def types(self):
        return sorted({p.type for p in self.products})