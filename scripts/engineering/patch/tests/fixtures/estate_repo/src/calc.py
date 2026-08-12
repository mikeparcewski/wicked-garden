"""Calculator helpers (wicked-patch estate fixture)."""


def add(a, b):
    """Add two numbers."""
    return a + b


def multiply(a, b):
    """Multiply via repeated add."""
    total = 0
    for _ in range(b):
        total = add(total, a)
    return total
