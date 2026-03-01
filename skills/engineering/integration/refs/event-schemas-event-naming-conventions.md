# Event Schema Design Guide: Event Naming Conventions

## Event Naming Conventions

### Pattern: resource.action

```
user.created
user.updated
user.deleted

order.created
order.confirmed
order.shipped
order.delivered
order.cancelled

payment.initiated
payment.completed
payment.failed

inventory.reserved
inventory.released
```

### Pattern: resource.field.changed

```
user.email.changed
user.status.changed

order.status.changed
order.address.updated
```

### Pattern: domain.resource.action

```
ecommerce.order.created
ecommerce.order.shipped

authentication.user.logged_in
authentication.user.logged_out

billing.invoice.generated
billing.payment.received
```

## Event Versioning

### Semantic Versioning

```json
{
  "type": "order.created",
  "version": "2.1.0",
  "data": {
    // v2.1.0 schema
  }
}
```

**Rules**:
- Major: Breaking changes
- Minor: Backward-compatible additions
- Patch: Bug fixes, clarifications

### Multiple Versions

```json
// Version 1
{
  "type": "order.created.v1",
  "data": {
    "orderId": "123",
    "total": 99.99
  }
}

// Version 2 (added items)
{
  "type": "order.created.v2",
  "data": {
    "orderId": "123",
    "items": [...],
    "total": 99.99
  }
}
```

### Schema Evolution

**Backward Compatible** (safe):
- Add optional fields
- Add new event types
- Make required fields optional
- Widen value ranges

**Breaking Changes** (major version):
- Remove fields
- Rename fields
- Change field types
- Narrow value ranges
- Make optional fields required

## Common Event Patterns

### CRUD Events

```json
// Create
{
  "type": "product.created",
  "data": {
    "productId": "prod-123",
    "name": "Widget",
    "price": 29.99
  }
}

// Update
{
  "type": "product.updated",
  "data": {
    "productId": "prod-123",
    "changes": {
      "price": {
        "old": 29.99,
        "new": 24.99
      }
    }
  }
}

// Delete
{
  "type": "product.deleted",
  "data": {
    "productId": "prod-123",
    "deletedAt": "2025-01-24T10:00:00Z"
  }
}
```

### Batch Events

```json
{
  "type": "products.imported",
  "data": {
    "batchId": "batch-789",
    "productsCreated": 150,
    "productsUpdated": 25,
    "productsFailed": 3,
    "failedProducts": [
      {
        "sku": "WIDGET-001",
        "error": "Invalid price"
      }
    ]
  }
}
```

### Aggregate Events

```json
{
  "type": "daily.sales.summary",
  "data": {
    "date": "2025-01-24",
    "totalOrders": 1250,
    "totalRevenue": 45678.90,
    "topProducts": [
      {"productId": "prod-123", "unitsSold": 89}
    ]
  }
}
```

### Failed Event

```json
{
  "type": "payment.failed",
  "data": {
    "paymentId": "pay-123",
    "orderId": "order-456",
    "failureReason": "insufficient_funds",
    "failureCode": "card_declined",
    "retriable": true,
    "failedAt": "2025-01-24T10:00:00Z"
  }
}
```

## Event Metadata

### Correlation and Causation

```json
{
  "metadata": {
    // Links related events together
    "correlationId": "corr-abc-123",

    // What caused this event
    "causationId": "evt-previous-event",

    // Distributed tracing
    "traceId": "trace-xyz-789",
    "spanId": "span-123"
  }
}
```

### Idempotency

```json
{
  "id": "evt_1234567890", // Unique event ID

  "metadata": {
    // For duplicate detection
    "idempotencyKey": "order-12345-created"
  }
}
```

### Temporal Information

```json
{
  "timestamp": "2025-01-24T10:00:00.000Z", // Event creation
  "data": {
    "occurredAt": "2025-01-24T09:59:58.000Z", // Actual occurrence
    "processedAt": "2025-01-24T10:00:01.000Z", // Processing time
    "scheduledFor": "2025-01-25T10:00:00.000Z" // Future action
  }
}
```

## CloudEvents Specification

Standard event format for cloud-native applications.

```json
{
  "specversion": "1.0",
  "type": "com.example.order.created",
  "source": "https://example.com/orders",
  "id": "A234-1234-1234",
  "time": "2025-01-24T10:00:00Z",
  "datacontenttype": "application/json",
  "subject": "orders/12345",
  "data": {
    "orderId": "12345",
    "customerId": "customer-456",
    "total": 99.99
  }
}
```

**Required Fields**:
- `specversion`: CloudEvents version
- `type`: Event type
- `source`: Event source
- `id`: Unique identifier

**Optional Fields**:
- `time`: Timestamp
- `datacontenttype`: Content type
- `subject`: Subject of event
- `data`: Event payload

## Dead Letter Queues

Events that fail processing:

```json
{
  "originalEvent": {
    "type": "order.created",
    "data": {...}
  },
  "failureInfo": {
    "attemptCount": 3,
    "lastAttempt": "2025-01-24T10:05:00Z",
    "error": "Database connection timeout",
    "stackTrace": "...",
    "consumerService": "inventory-service"
  },
  "metadata": {
    "correlationId": "corr-abc-123",
    "originalTimestamp": "2025-01-24T10:00:00Z"
  }
}
```

