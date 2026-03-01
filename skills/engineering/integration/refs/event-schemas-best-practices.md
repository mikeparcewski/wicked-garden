# Event Schema Design Guide: Best Practices

## Best Practices

### 1. Use Past Tense for Domain Events

```
Good: order.created, payment.completed
Bad:  order.create, payment.complete
```

### 2. Include Event ID

Always include unique identifier for deduplication:
```json
{
  "id": "evt_1234567890",
  "type": "order.created"
}
```

### 3. Timestamp Everything

```json
{
  "timestamp": "2025-01-24T10:00:00.000Z"
}
```

Use ISO 8601 format with UTC timezone.

### 4. Keep Events Small

- Under 1MB (most message brokers have limits)
- Use references for large data
- Store full data separately if needed

```json
// Bad: Full product catalog in event
{
  "type": "order.created",
  "data": {
    "items": [
      {
        "product": { /* 100KB of product data */ }
      }
    ]
  }
}

// Good: Reference to product
{
  "type": "order.created",
  "data": {
    "items": [
      {
        "productId": "prod-123",
        "quantity": 2
      }
    ]
  }
}
```

### 5. Immutable Events

Never modify published events. Publish correction events instead:

```json
// Original
{
  "type": "order.created",
  "data": {
    "orderId": "123",
    "total": 100.00 // Wrong!
  }
}

// Correction
{
  "type": "order.corrected",
  "data": {
    "orderId": "123",
    "field": "total",
    "oldValue": 100.00,
    "newValue": 99.99,
    "reason": "Pricing error"
  }
}
```

### 6. Self-Contained Events

Event should have all information needed to process it:

```json
// Bad: Need to fetch user details
{
  "type": "order.created",
  "data": {
    "userId": "user-123" // Consumer must fetch user
  }
}

// Good: Include relevant user data
{
  "type": "order.created",
  "data": {
    "userId": "user-123",
    "userEmail": "user@example.com",
    "shippingAddress": {...}
  }
}
```

### 7. Schema Registry

Use a schema registry to:
- Version schemas
- Validate events
- Generate code
- Document events

### 8. Namespace Events

```
com.example.orders.created
com.example.payments.completed
```

Prevents collisions across domains.

### 9. Include Context

```json
{
  "metadata": {
    "correlationId": "corr-123",
    "userId": "user-456",
    "tenantId": "tenant-789"
  }
}
```

### 10. Handle Failures Gracefully

- Implement retry logic
- Use dead letter queues
- Log failures comprehensively
- Alert on persistent failures

## Validation Example

```typescript
import Ajv from 'ajv';
import orderCreatedSchema from './schemas/order-created.json';

const ajv = new Ajv();
const validate = ajv.compile(orderCreatedSchema);

function publishEvent(event: any): void {
  // Validate before publishing
  if (!validate(event)) {
    throw new Error(
      `Invalid event: ${JSON.stringify(validate.errors)}`
    );
  }

  // Add metadata
  const enrichedEvent = {
    ...event,
    id: generateEventId(),
    timestamp: new Date().toISOString(),
    metadata: {
      correlationId: getCurrentCorrelationId(),
      traceId: getCurrentTraceId(),
    },
  };

  // Publish to message broker
  messageBroker.publish(enrichedEvent.type, enrichedEvent);
}
```

## Event Catalog Example

Document all events in your system:

```markdown
# Event Catalog

## Order Events

### order.created
**Version**: 1.0
**Producer**: order-service
**Consumers**: inventory-service, notification-service
**Schema**: [order-created.schema.json](schemas/order-created.schema.json)

Published when a new order is created.

**Example**:
\`\`\`json
{
  "type": "order.created",
  "data": {
    "orderId": "order-123",
    "customerId": "customer-456",
    "total": 99.99
  }
}
\`\`\`

### order.shipped
**Version**: 1.0
**Producer**: fulfillment-service
**Consumers**: notification-service, tracking-service
**Schema**: [order-shipped.schema.json](schemas/order-shipped.schema.json)

Published when an order is shipped.
```
