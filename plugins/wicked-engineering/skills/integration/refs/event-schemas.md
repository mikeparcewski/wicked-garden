# Event Schema Design Guide

Comprehensive guide to designing event schemas for event-driven architectures, with formats and best practices.

## Event Structure

### Core Components

Every event should include:

1. **Event Metadata**: Type, ID, timestamp, version
2. **Event Payload**: Business data
3. **Context**: Trace ID, correlation ID, source
4. **Schema Information**: Version, format

### Standard Event Envelope

```json
{
  "id": "evt_1234567890",
  "type": "order.created",
  "version": "1.0",
  "timestamp": "2025-01-24T10:00:00.000Z",
  "source": "order-service",
  "subject": "orders/12345",
  "dataContentType": "application/json",
  "data": {
    "orderId": "12345",
    "customerId": "customer-456",
    "items": [...],
    "total": 99.99
  },
  "metadata": {
    "correlationId": "corr-abc-123",
    "traceId": "trace-xyz-789",
    "causationId": "evt_0987654321",
    "userId": "user-123"
  }
}
```

## Event Types

### Domain Events

Business occurrences that have already happened (past tense).

```json
{
  "type": "order.created",
  "version": "1.0",
  "timestamp": "2025-01-24T10:00:00.000Z",
  "source": "order-service",
  "data": {
    "orderId": "order-12345",
    "customerId": "customer-456",
    "status": "pending",
    "items": [
      {
        "productId": "prod-789",
        "quantity": 2,
        "price": 29.99
      }
    ],
    "subtotal": 59.98,
    "tax": 5.40,
    "total": 65.38,
    "currency": "USD",
    "createdAt": "2025-01-24T10:00:00.000Z"
  }
}
```

### Command Events

Requests for action (imperative).

```json
{
  "type": "order.process",
  "version": "1.0",
  "timestamp": "2025-01-24T10:01:00.000Z",
  "source": "checkout-service",
  "data": {
    "orderId": "order-12345",
    "paymentMethod": {
      "type": "credit_card",
      "last4": "4242"
    }
  },
  "metadata": {
    "requestedBy": "user-123",
    "correlationId": "corr-abc-123"
  }
}
```

### Integration Events

Cross-service communication.

```json
{
  "type": "payment.completed",
  "version": "1.0",
  "timestamp": "2025-01-24T10:02:00.000Z",
  "source": "payment-service",
  "data": {
    "paymentId": "pay-xyz-789",
    "orderId": "order-12345",
    "amount": 65.38,
    "currency": "USD",
    "status": "succeeded",
    "transactionId": "txn-abc-123"
  }
}
```

### State Change Events

Object state transitions.

```json
{
  "type": "order.status.changed",
  "version": "1.0",
  "timestamp": "2025-01-24T10:03:00.000Z",
  "source": "order-service",
  "data": {
    "orderId": "order-12345",
    "previousStatus": "pending",
    "newStatus": "processing",
    "changedAt": "2025-01-24T10:03:00.000Z",
    "changedBy": "system"
  }
}
```

## Schema Formats

### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://example.com/events/order-created.schema.json",
  "title": "OrderCreated",
  "description": "Event published when a new order is created",
  "type": "object",
  "required": ["type", "version", "timestamp", "source", "data"],
  "properties": {
    "type": {
      "type": "string",
      "const": "order.created"
    },
    "version": {
      "type": "string",
      "pattern": "^[0-9]+\\.[0-9]+$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "source": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "required": ["orderId", "customerId", "items", "total"],
      "properties": {
        "orderId": {
          "type": "string",
          "pattern": "^order-[a-z0-9]+$"
        },
        "customerId": {
          "type": "string"
        },
        "items": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "required": ["productId", "quantity", "price"],
            "properties": {
              "productId": {"type": "string"},
              "quantity": {"type": "integer", "minimum": 1},
              "price": {"type": "number", "minimum": 0}
            }
          }
        },
        "total": {
          "type": "number",
          "minimum": 0
        },
        "currency": {
          "type": "string",
          "pattern": "^[A-Z]{3}$",
          "default": "USD"
        }
      }
    }
  }
}
```

### Avro Schema

```json
{
  "type": "record",
  "name": "OrderCreated",
  "namespace": "com.example.events",
  "doc": "Event published when a new order is created",
  "fields": [
    {
      "name": "eventId",
      "type": "string",
      "doc": "Unique event identifier"
    },
    {
      "name": "timestamp",
      "type": "long",
      "logicalType": "timestamp-millis"
    },
    {
      "name": "orderId",
      "type": "string"
    },
    {
      "name": "customerId",
      "type": "string"
    },
    {
      "name": "items",
      "type": {
        "type": "array",
        "items": {
          "type": "record",
          "name": "OrderItem",
          "fields": [
            {"name": "productId", "type": "string"},
            {"name": "quantity", "type": "int"},
            {"name": "price", "type": "double"}
          ]
        }
      }
    },
    {
      "name": "total",
      "type": "double"
    },
    {
      "name": "currency",
      "type": "string",
      "default": "USD"
    }
  ]
}
```

### Protocol Buffers

```protobuf
syntax = "proto3";

package events.v1;

import "google/protobuf/timestamp.proto";

message OrderCreated {
  string event_id = 1;
  google.protobuf.Timestamp timestamp = 2;
  string order_id = 3;
  string customer_id = 4;
  repeated OrderItem items = 5;
  double total = 6;
  string currency = 7;
}

message OrderItem {
  string product_id = 1;
  int32 quantity = 2;
  double price = 3;
}
```

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
