# Backend Code Patterns

## API Endpoint Pattern

```python
@router.post("/api/v1/orders", status_code=201)
async def create_order(
    order: OrderCreate,
    current_user: User = Depends(get_current_user)
) -> OrderResponse:
    # Authorization
    if not current_user.can_create_orders:
        raise HTTPException(403, "Insufficient permissions")

    # Validation
    if order.total < 0:
        raise HTTPException(400, "Total must be non-negative")

    # Transaction
    async with db.transaction():
        db_order = await db.orders.create(**order.dict())
        await send_notification.delay(db_order.id)

    return OrderResponse.from_orm(db_order)
```

## Query Optimization Pattern

```python
# Bad: N+1 problem
orders = await Order.all()
for order in orders:
    order.items = await OrderItem.filter(order_id=order.id)

# Good: Eager loading
orders = await Order.prefetch_related('items').all()
```

## Database Patterns

### Transaction Management
```python
async with db.transaction():
    user = await User.create(email=email)
    await Profile.create(user_id=user.id)
    await send_welcome_email.delay(user.id)
```

### Connection Pooling
```python
# Configure connection pool
DATABASE_URL = "postgresql://user:pass@localhost/db"
database = Database(
    DATABASE_URL,
    min_size=5,
    max_size=20
)
```

### Migration Best Practices
```python
# Reversible migration
def upgrade():
    op.add_column('users', sa.Column('status', sa.String(20)))

def downgrade():
    op.drop_column('users', 'status')
```

## Authentication Patterns

### Password Hashing
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

### JWT Token Management
```python
from jose import jwt
from datetime import datetime, timedelta

def create_access_token(user_id: int) -> str:
    expires = datetime.utcnow() + timedelta(hours=1)
    payload = {"sub": str(user_id), "exp": expires}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
```

## Integration Patterns

### External API Resilience
```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def fetch_external_data(url: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

### Webhook Handling
```python
@router.post("/webhooks/stripe")
async def handle_stripe_webhook(
    request: Request,
    signature: str = Header(None, alias="Stripe-Signature")
):
    payload = await request.body()

    # Verify signature
    verify_webhook_signature(payload, signature)

    # Process idempotently
    event = json.loads(payload)
    await process_event_idempotent(event)

    return {"status": "received"}
```

### Circuit Breaker Pattern
```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
async def call_payment_service(order_id: int):
    # Will open circuit after 5 failures
    # Closes automatically after 60 seconds
    return await payment_api.charge(order_id)
```

## Caching Patterns

### Redis Caching
```python
from redis import asyncio as aioredis

async def get_user(user_id: int) -> User:
    cache_key = f"user:{user_id}"

    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return User.parse_raw(cached)

    # Fetch from database
    user = await User.get(id=user_id)

    # Cache for 5 minutes
    await redis.setex(cache_key, 300, user.json())

    return user
```

### Cache Invalidation
```python
async def update_user(user_id: int, data: UserUpdate):
    user = await User.get(id=user_id)
    await user.update(**data.dict())

    # Invalidate cache
    await redis.delete(f"user:{user_id}")

    return user
```
