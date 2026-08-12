"""Order app (wicked-patch estate fixture)."""

from calc import add, multiply


class Order:
    """An order with a status field."""

    def __init__(self, status):
        self.status = status

    def total(self, prices):
        result = 0
        for p in prices:
            result = add(result, p)
        return result


def main():
    order = Order("open")
    print(order.total([1, 2, 3]))
    print(multiply(2, 3))
