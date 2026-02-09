---
name: new-developer-onboarding
title: New Developer Onboarding
description: Complete onboarding flow for a developer new to an unfamiliar codebase
type: workflow
difficulty: basic
estimated_minutes: 8
---

# New Developer Onboarding

This scenario validates that wicked-delivery can effectively onboard a new developer to an unfamiliar codebase, providing orientation, personalized learning paths, and actionable first tasks.

## Setup

Create a realistic Python API project that a new developer would need to understand:

```bash
# Create test project directory
mkdir -p ~/test-wicked-delivery/ecommerce-api
cd ~/test-wicked-delivery/ecommerce-api

# Initialize as a git repo with basic structure
git init

# Create README
cat > README.md <<'EOF'
# E-Commerce API

A Python FastAPI backend for processing orders.

## Quick Start
```bash
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## Architecture
- `src/` - Application source code
- `tests/` - Test suite
- `docs/` - Additional documentation
EOF

# Create requirements.txt
cat > requirements.txt <<'EOF'
fastapi==0.104.0
uvicorn==0.24.0
sqlalchemy==2.0.23
pydantic==2.5.0
pytest==7.4.3
EOF

# Create main application structure
mkdir -p src/api src/services src/models src/db tests docs

# Create main entry point
cat > src/main.py <<'EOF'
from fastapi import FastAPI
from src.api import orders, products, users

app = FastAPI(title="E-Commerce API", version="1.0.0")

app.include_router(orders.router, prefix="/orders", tags=["orders"])
app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(users.router, prefix="/users", tags=["users"])

@app.get("/health")
def health_check():
    return {"status": "healthy"}
EOF

# Create orders API
cat > src/api/orders.py <<'EOF'
from fastapi import APIRouter, Depends, HTTPException
from src.services.order_service import OrderService
from src.models.order import Order, OrderCreate

router = APIRouter()

@router.post("/", response_model=Order)
def create_order(order: OrderCreate, service: OrderService = Depends()):
    return service.create_order(order)

@router.get("/{order_id}", response_model=Order)
def get_order(order_id: int, service: OrderService = Depends()):
    order = service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
EOF

# Create order service
cat > src/services/order_service.py <<'EOF'
from src.db.repository import OrderRepository
from src.models.order import OrderCreate

class OrderService:
    def __init__(self):
        self.repository = OrderRepository()

    def create_order(self, order_data: OrderCreate):
        # Validate inventory
        # Calculate pricing
        # Create order record
        return self.repository.create(order_data)

    def get_order(self, order_id: int):
        return self.repository.get(order_id)
EOF

# Create order model
cat > src/models/order.py <<'EOF'
from pydantic import BaseModel
from typing import List
from datetime import datetime

class OrderItem(BaseModel):
    product_id: int
    quantity: int
    price: float

class OrderCreate(BaseModel):
    user_id: int
    items: List[OrderItem]

class Order(BaseModel):
    id: int
    user_id: int
    items: List[OrderItem]
    total: float
    status: str
    created_at: datetime
EOF

# Create __init__.py files
touch src/__init__.py src/api/__init__.py src/services/__init__.py src/models/__init__.py src/db/__init__.py

# Create a simple test file
cat > tests/test_orders.py <<'EOF'
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_create_order():
    order_data = {
        "user_id": 1,
        "items": [{"product_id": 1, "quantity": 2, "price": 29.99}]
    }
    # Would test order creation
    pass
EOF

# Commit the initial structure
git add -A
git commit -m "Initial project structure"

echo "Setup complete. Project created at ~/test-wicked-delivery/ecommerce-api"
```

## Steps

### 1. Orient to the Codebase

Use the onboarding-guide agent to get oriented:

```
Task tool: subagent_type="wicked-delivery:onboarding-guide"
prompt="I just joined the team and need to understand this e-commerce API project. Help me get oriented."
```

**Expected Output**:
- Project overview (E-Commerce API, FastAPI backend)
- Technology stack identification (Python, FastAPI, SQLAlchemy, Pydantic)
- Project structure explanation
- Key entry points identified (src/main.py)
- Getting started steps (install deps, run uvicorn)

### 2. Get Detailed Code Explanation

Ask for explanation of a specific component:

```
Task tool: subagent_type="wicked-delivery:codebase-narrator"
prompt="Explain how the order creation flow works, from API endpoint to database"
```

**Expected Output**:
- Clear narrative of the order flow
- Step-by-step explanation: API route -> Service -> Repository
- Code snippets with file paths
- Design pattern identification (Service layer, Repository pattern)
- Related components mentioned

### 3. Request Personalized Learning Path

Get a customized learning plan:

```
Task tool: subagent_type="wicked-delivery:onboarding-guide"
prompt="I'm experienced with Django but new to FastAPI. Create a learning path for me to become productive on this codebase."
```

**Expected Output**:
- Assessment acknowledgment (Django experience -> FastAPI transition)
- Phased learning plan:
  - Phase 1: Foundation (FastAPI basics, dependency injection)
  - Phase 2: Exploration (trace a request, read tests)
  - Phase 3: Contribution (first PR)
- Specific file paths to study
- Time estimates for each phase

### 4. Get First Task Recommendations

Ask for actionable first contributions:

```
Task tool: subagent_type="wicked-delivery:onboarding-guide"
prompt="What should my first contribution be? Give me something I can complete today."
```

**Expected Output**:
- 2-3 specific task suggestions, such as:
  - Add missing docstrings to order_service.py
  - Complete the test_create_order test
  - Add input validation to OrderCreate model
- Each task includes:
  - File location
  - What to change
  - How to verify success
  - Estimated time (<2 hours)

### 5. Verify Memory Integration (if available)

If wicked-mem is installed:

```
Task tool: subagent_type="wicked-delivery:onboarding-guide"
prompt="What did I learn in my last session?"
```

**Expected Output**:
- Recall of previous orientation session
- Suggestion to continue from where left off
- Progress tracking acknowledgment

## Expected Outcome

- Developer receives clear, actionable orientation in unfamiliar codebase
- Learning path is personalized based on stated experience level
- First tasks are achievable and build confidence
- Code explanations transform complexity into understandable narratives
- All recommendations include specific file paths and concrete steps
- Integration with wicked-mem (if available) provides cross-session continuity

## Success Criteria

- [ ] Orient skill produces TL;DR summary of project purpose
- [ ] Technology stack correctly identified (Python, FastAPI, SQLAlchemy)
- [ ] Project structure mapped with directory explanations
- [ ] Key entry point (src/main.py) identified
- [ ] Getting started steps are executable (pip install, uvicorn)
- [ ] Code explanation follows request flow end-to-end
- [ ] Learning path has distinct phases with time estimates
- [ ] First task recommendations include specific file paths
- [ ] All suggestions are actionable (not "read the code" generic advice)
- [ ] If wicked-mem available: previous session recalled correctly

## Value Demonstrated

**Real-world value**: New developer onboarding is one of the most expensive activities in software teams. Studies show it takes 3-6 months for developers to become fully productive on a new codebase. This time is spent wandering through unfamiliar code, asking colleagues questions, and making false starts.

wicked-delivery's onboarding capabilities compress this ramp-up time by:

1. **Immediate orientation**: Instead of spending days figuring out project structure, developers get a clear map in minutes
2. **Personalized paths**: Learning recommendations adapt to the developer's existing skills (Django -> FastAPI transition)
3. **Actionable first tasks**: Developers contribute value on day one instead of feeling lost
4. **Continuous context**: With wicked-mem integration, progress persists across sessions - no starting from scratch

For teams with frequent hiring, contractor onboarding, or internal mobility, this capability pays for itself quickly. A new developer who contributes their first PR in day one instead of week two represents significant productivity gain.

## Cleanup

```bash
rm -rf ~/test-wicked-delivery/ecommerce-api
```
