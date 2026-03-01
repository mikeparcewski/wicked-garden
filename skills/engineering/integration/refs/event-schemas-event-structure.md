# Event Schema Design Guide: Event Structure

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

