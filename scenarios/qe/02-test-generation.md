---
name: test-generation
title: Test Scenario Generation and Automation
description: Generate comprehensive test scenarios and convert to automated tests
type: testing
difficulty: intermediate
estimated_minutes: 10
---

# Test Scenario Generation and Automation

This scenario demonstrates the full wicked-qe test workflow: generating scenarios, creating a test plan, and automating tests.

## Setup

Create a feature that needs test coverage:

```bash
# Create test project
mkdir -p ~/test-wicked-qe/test-gen
cd ~/test-wicked-qe/test-gen

# Create a shopping cart service
mkdir -p src tests
cat > src/cart.py << 'EOF'
"""Shopping cart service with business rules."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from datetime import datetime


@dataclass
class CartItem:
    product_id: str
    name: str
    price: Decimal
    quantity: int

    @property
    def subtotal(self) -> Decimal:
        return self.price * self.quantity


@dataclass
class Discount:
    code: str
    type: str  # 'percentage' or 'fixed'
    value: Decimal
    min_cart_value: Optional[Decimal] = None
    expires_at: Optional[datetime] = None
    max_uses: Optional[int] = None
    uses: int = 0


@dataclass
class Cart:
    items: list[CartItem] = field(default_factory=list)
    discount: Optional[Discount] = None

    def add_item(self, product_id: str, name: str, price: Decimal, quantity: int = 1) -> None:
        """Add item to cart. If already exists, increase quantity."""
        for item in self.items:
            if item.product_id == product_id:
                item.quantity += quantity
                return
        self.items.append(CartItem(product_id, name, price, quantity))

    def remove_item(self, product_id: str) -> bool:
        """Remove item from cart. Returns True if item was found."""
        for i, item in enumerate(self.items):
            if item.product_id == product_id:
                del self.items[i]
                return True
        return False

    def update_quantity(self, product_id: str, quantity: int) -> bool:
        """Update item quantity. Removes item if quantity is 0."""
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")
        if quantity == 0:
            return self.remove_item(product_id)
        for item in self.items:
            if item.product_id == product_id:
                item.quantity = quantity
                return True
        return False

    def apply_discount(self, discount: Discount) -> bool:
        """Apply discount code to cart."""
        # Check if discount is expired
        if discount.expires_at and discount.expires_at < datetime.now():
            return False

        # Check if discount has reached max uses
        if discount.max_uses and discount.uses >= discount.max_uses:
            return False

        # Check minimum cart value
        if discount.min_cart_value and self.subtotal < discount.min_cart_value:
            return False

        self.discount = discount
        return True

    def remove_discount(self) -> None:
        """Remove applied discount."""
        self.discount = None

    @property
    def subtotal(self) -> Decimal:
        """Total before discount."""
        return sum((item.subtotal for item in self.items), Decimal('0'))

    @property
    def discount_amount(self) -> Decimal:
        """Calculate discount amount."""
        if not self.discount:
            return Decimal('0')

        if self.discount.type == 'percentage':
            return self.subtotal * (self.discount.value / 100)
        elif self.discount.type == 'fixed':
            return min(self.discount.value, self.subtotal)  # Don't go negative

        return Decimal('0')

    @property
    def total(self) -> Decimal:
        """Final total after discount."""
        return self.subtotal - self.discount_amount

    def clear(self) -> None:
        """Remove all items and discount."""
        self.items = []
        self.discount = None
EOF
```

## Steps

### 1. Generate Test Scenarios

```bash
/wicked-qe:scenarios Shopping cart with discounts
```

**Expected**: Comprehensive scenarios covering:
- Happy path cart operations
- Edge cases (empty cart, zero quantity)
- Discount rules (expired, max uses, min value)
- Error conditions (negative quantity)

### 2. Create Test Plan

```bash
/wicked-qe:qe-plan src/cart.py
```

**Expected**: Prioritized test plan with:
- Unit test coverage for each method
- Integration scenarios for workflows
- Priority based on risk

### 3. Generate Automated Tests

```bash
/wicked-qe:automate --framework pytest
```

**Expected**: Working pytest test file with:
- Test functions for each scenario
- Proper fixtures for test data
- Assertions matching expected outcomes

### 4. Review Test Quality

```bash
/wicked-qe:qe-review tests/
```

**Expected**: Test quality review covering:
- Coverage completeness
- Assertion quality
- Edge case coverage
- Test isolation

## Expected Outcome

### Test Scenarios

```markdown
## Test Scenarios: Shopping Cart

### Happy Path Scenarios

#### HP-1: Add single item to empty cart
**Given**: Empty cart
**When**: Add item (id="prod1", name="Widget", price=10.00, quantity=1)
**Then**: Cart has 1 item, subtotal is $10.00
**Test Data**: {} -> {items: [Widget x1], subtotal: 10.00}

#### HP-2: Add same item increases quantity
**Given**: Cart with Widget x1
**When**: Add Widget with quantity=2
**Then**: Cart has Widget x3, subtotal is $30.00

#### HP-3: Apply percentage discount
**Given**: Cart with subtotal $100
**When**: Apply 20% discount
**Then**: Discount amount is $20, total is $80

#### HP-4: Apply fixed discount
**Given**: Cart with subtotal $50
**When**: Apply $10 fixed discount
**Then**: Discount amount is $10, total is $40

### Edge Cases

#### EC-1: Empty cart subtotal
**Given**: Empty cart
**When**: Check subtotal
**Then**: Subtotal is $0.00

#### EC-2: Update quantity to zero removes item
**Given**: Cart with 1 item
**When**: Update quantity to 0
**Then**: Item removed, cart is empty

#### EC-3: Fixed discount larger than subtotal
**Given**: Cart with subtotal $5
**When**: Apply $10 fixed discount
**Then**: Discount capped at $5, total is $0 (not negative)

#### EC-4: Minimum cart value not met
**Given**: Cart with subtotal $20
**When**: Apply discount with min_cart_value=$50
**Then**: Discount not applied, returns False

### Error Conditions

#### ERR-1: Negative quantity
**Given**: Cart with items
**When**: Update quantity to -1
**Then**: ValueError raised with message "Quantity cannot be negative"

#### ERR-2: Remove non-existent item
**Given**: Cart with Widget
**When**: Remove "nonexistent"
**Then**: Returns False, cart unchanged

#### ERR-3: Update non-existent item
**Given**: Cart with Widget
**When**: Update quantity for "nonexistent"
**Then**: Returns False

### Discount Rules

#### DISC-1: Expired discount
**Given**: Discount with expires_at in the past
**When**: Apply to cart
**Then**: Returns False, discount not applied

#### DISC-2: Max uses reached
**Given**: Discount with max_uses=5, uses=5
**When**: Apply to cart
**Then**: Returns False, discount not applied

#### DISC-3: Discount applied then cart cleared
**Given**: Cart with discount applied
**When**: Clear cart
**Then**: Items empty, discount removed
```

### Generated Tests

```python
"""Tests for shopping cart service."""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from src.cart import Cart, CartItem, Discount


class TestCartOperations:
    """Tests for basic cart operations."""

    def test_add_item_to_empty_cart(self):
        """HP-1: Add single item to empty cart."""
        cart = Cart()
        cart.add_item("prod1", "Widget", Decimal("10.00"), 1)

        assert len(cart.items) == 1
        assert cart.items[0].product_id == "prod1"
        assert cart.subtotal == Decimal("10.00")

    def test_add_same_item_increases_quantity(self):
        """HP-2: Add same item increases quantity."""
        cart = Cart()
        cart.add_item("prod1", "Widget", Decimal("10.00"), 1)
        cart.add_item("prod1", "Widget", Decimal("10.00"), 2)

        assert len(cart.items) == 1
        assert cart.items[0].quantity == 3
        assert cart.subtotal == Decimal("30.00")

    def test_empty_cart_subtotal(self):
        """EC-1: Empty cart subtotal is zero."""
        cart = Cart()
        assert cart.subtotal == Decimal("0")

    def test_update_quantity_to_zero_removes_item(self):
        """EC-2: Update quantity to zero removes item."""
        cart = Cart()
        cart.add_item("prod1", "Widget", Decimal("10.00"), 1)

        result = cart.update_quantity("prod1", 0)

        assert result is True
        assert len(cart.items) == 0

    def test_remove_nonexistent_item_returns_false(self):
        """ERR-2: Remove non-existent item."""
        cart = Cart()
        cart.add_item("prod1", "Widget", Decimal("10.00"), 1)

        result = cart.remove_item("nonexistent")

        assert result is False
        assert len(cart.items) == 1

    def test_negative_quantity_raises_error(self):
        """ERR-1: Negative quantity raises ValueError."""
        cart = Cart()
        cart.add_item("prod1", "Widget", Decimal("10.00"), 1)

        with pytest.raises(ValueError, match="Quantity cannot be negative"):
            cart.update_quantity("prod1", -1)


class TestDiscounts:
    """Tests for discount functionality."""

    def test_percentage_discount(self):
        """HP-3: Apply percentage discount."""
        cart = Cart()
        cart.add_item("prod1", "Widget", Decimal("100.00"), 1)
        discount = Discount(code="SAVE20", type="percentage", value=Decimal("20"))

        result = cart.apply_discount(discount)

        assert result is True
        assert cart.discount_amount == Decimal("20.00")
        assert cart.total == Decimal("80.00")

    def test_fixed_discount(self):
        """HP-4: Apply fixed discount."""
        cart = Cart()
        cart.add_item("prod1", "Widget", Decimal("50.00"), 1)
        discount = Discount(code="SAVE10", type="fixed", value=Decimal("10"))

        result = cart.apply_discount(discount)

        assert result is True
        assert cart.discount_amount == Decimal("10.00")
        assert cart.total == Decimal("40.00")

    def test_fixed_discount_capped_at_subtotal(self):
        """EC-3: Fixed discount cannot exceed subtotal."""
        cart = Cart()
        cart.add_item("prod1", "Widget", Decimal("5.00"), 1)
        discount = Discount(code="BIG", type="fixed", value=Decimal("10"))

        cart.apply_discount(discount)

        assert cart.discount_amount == Decimal("5.00")
        assert cart.total == Decimal("0")

    def test_minimum_cart_value_not_met(self):
        """EC-4: Minimum cart value not met."""
        cart = Cart()
        cart.add_item("prod1", "Widget", Decimal("20.00"), 1)
        discount = Discount(
            code="MIN50", type="percentage", value=Decimal("10"),
            min_cart_value=Decimal("50")
        )

        result = cart.apply_discount(discount)

        assert result is False
        assert cart.discount is None

    def test_expired_discount_rejected(self):
        """DISC-1: Expired discount not applied."""
        cart = Cart()
        cart.add_item("prod1", "Widget", Decimal("100.00"), 1)
        discount = Discount(
            code="EXPIRED", type="percentage", value=Decimal("20"),
            expires_at=datetime.now() - timedelta(days=1)
        )

        result = cart.apply_discount(discount)

        assert result is False
        assert cart.discount is None

    def test_max_uses_reached(self):
        """DISC-2: Max uses reached."""
        cart = Cart()
        cart.add_item("prod1", "Widget", Decimal("100.00"), 1)
        discount = Discount(
            code="LIMITED", type="percentage", value=Decimal("20"),
            max_uses=5, uses=5
        )

        result = cart.apply_discount(discount)

        assert result is False

    def test_clear_removes_discount(self):
        """DISC-3: Clear removes discount."""
        cart = Cart()
        cart.add_item("prod1", "Widget", Decimal("100.00"), 1)
        discount = Discount(code="SAVE20", type="percentage", value=Decimal("20"))
        cart.apply_discount(discount)

        cart.clear()

        assert len(cart.items) == 0
        assert cart.discount is None
```

## Success Criteria

- [ ] Scenarios cover all happy paths
- [ ] Edge cases identified (empty, zero, boundaries)
- [ ] Error conditions with expected exceptions
- [ ] Business rules (discount logic) covered
- [ ] Generated tests are syntactically correct
- [ ] Tests follow pytest conventions
- [ ] Each test has clear docstring linking to scenario
- [ ] Tests use appropriate assertions
- [ ] Tests would pass against the implementation
- [ ] No duplicate test coverage

## Value Demonstrated

**Problem solved**: Writing comprehensive tests is time-consuming. Developers often skip edge cases or write tests after bugs are found.

**Real-world value**:
- **Comprehensive coverage**: Systematic scenario generation catches cases developers miss
- **Structured approach**: Given/When/Then format ensures clear test intent
- **Automated generation**: Hours of test writing reduced to minutes
- **Traceability**: Each test links back to its scenario

This replaces:
1. Developer writes code
2. Writes happy path test
3. Ships
4. Bug found in production
5. Adds test for that specific bug
6. Repeat

With scenario-first testing:
1. Generate comprehensive scenarios
2. Review scenarios (minutes)
3. Generate tests (automated)
4. Write code that passes tests
5. Ship with confidence
