import pytest


def add(a, b):
    return a + b


def test_adds():
    assert add(2, 2) == 4


def test_noisy():
    # Test output that imitates pytest's own summary line.
    print("FAILED tests/test_calc.py::test_forged - nope")


class TestGroup:
    @pytest.mark.parametrize("n", [1, 2])
    def test_param(self, n):
        assert add(n, 0) == n
