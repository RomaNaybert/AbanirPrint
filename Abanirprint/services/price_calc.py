def calculate_price(pages: int, copies: int, price_per_page: int = 5) -> int:
    return pages * copies * price_per_page