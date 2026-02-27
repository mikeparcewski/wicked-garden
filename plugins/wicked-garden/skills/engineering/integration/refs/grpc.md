# gRPC API Design Guide

Comprehensive guide to designing gRPC services with Protocol Buffers, patterns, and best practices.

## gRPC Overview

### What is gRPC?

- High-performance RPC framework
- Uses Protocol Buffers (protobuf) for serialization
- HTTP/2 for transport
- Supports streaming
- Generated client/server code
- Strong typing

### When to Use gRPC

**Good Fit**:
- Service-to-service communication
- Performance critical applications
- Streaming requirements
- Polyglot environments (multi-language)
- Internal APIs

**Poor Fit**:
- Browser clients (limited support)
- Public APIs (REST more accessible)
- Simple CRUD operations
- Human-readable requirements

## Protocol Buffers Basics

### Message Definition

```protobuf
syntax = "proto3";

package user.v1;

// Import common types
import "google/protobuf/timestamp.proto";
import "google/protobuf/empty.proto";

// Simple message
message User {
  string id = 1;
  string email = 2;
  string name = 3;
  google.protobuf.Timestamp created_at = 4;
}

// Message with nested types
message CreateUserRequest {
  string email = 1;
  string name = 2;
  string password = 3;
  UserRole role = 4;
}

message CreateUserResponse {
  User user = 1;
  repeated ValidationError errors = 2;
}

// Enums
enum UserRole {
  USER_ROLE_UNSPECIFIED = 0;  // Always have zero value
  USER_ROLE_ADMIN = 1;
  USER_ROLE_USER = 2;
  USER_ROLE_GUEST = 3;
}

// Nested message
message ValidationError {
  string field = 1;
  string message = 2;
  string code = 3;
}

// Repeated fields (arrays)
message ListUsersResponse {
  repeated User users = 1;
  int32 total_count = 2;
  string next_page_token = 3;
}

// Maps
message UserPreferences {
  map<string, string> settings = 1;
}

// Oneof (union type)
message SearchRequest {
  string query = 1;
  oneof filter {
    UserFilter user_filter = 2;
    PostFilter post_filter = 3;
  }
}
```

### Field Numbers

- Unique within message
- 1-15: Single byte encoding (use for frequent fields)
- 16-2047: Two byte encoding
- 19000-19999: Reserved
- Can't reuse deleted field numbers

### Field Rules

```protobuf
// Optional (default in proto3)
string name = 1;

// Repeated (array)
repeated string tags = 2;

// Map
map<string, int32> scores = 3;

// Reserved (prevent reuse)
reserved 4, 5, 6;
reserved "old_field_name";
```

## Service Definition

### Basic Service

```protobuf
service UserService {
  // Unary RPC (request-response)
  rpc GetUser(GetUserRequest) returns (GetUserResponse);

  // Create
  rpc CreateUser(CreateUserRequest) returns (CreateUserResponse);

  // Update
  rpc UpdateUser(UpdateUserRequest) returns (UpdateUserResponse);

  // Delete
  rpc DeleteUser(DeleteUserRequest) returns (google.protobuf.Empty);

  // List with pagination
  rpc ListUsers(ListUsersRequest) returns (ListUsersResponse);
}

// Request/Response messages
message GetUserRequest {
  string id = 1;
}

message GetUserResponse {
  User user = 1;
}

message UpdateUserRequest {
  string id = 1;
  // Use oneof for optional fields to detect if set
  oneof name {
    string name_value = 2;
  }
  oneof email {
    string email_value = 3;
  }
}

message UpdateUserResponse {
  User user = 1;
}

message DeleteUserRequest {
  string id = 1;
}

message ListUsersRequest {
  int32 page_size = 1;
  string page_token = 2;
  UserFilter filter = 3;
  string order_by = 4;
}

message ListUsersResponse {
  repeated User users = 1;
  string next_page_token = 2;
  int32 total_size = 3;
}

message UserFilter {
  string email = 1;
  UserRole role = 2;
  google.protobuf.Timestamp created_after = 3;
}
```

### Streaming RPCs

```protobuf
service StreamingService {
  // Server streaming (one request, stream of responses)
  rpc WatchUser(WatchUserRequest) returns (stream UserEvent);

  // Client streaming (stream of requests, one response)
  rpc UploadFile(stream FileChunk) returns (UploadFileResponse);

  // Bidirectional streaming
  rpc Chat(stream ChatMessage) returns (stream ChatMessage);
}

message WatchUserRequest {
  string user_id = 1;
}

message UserEvent {
  string user_id = 1;
  EventType type = 2;
  User user = 3;

  enum EventType {
    EVENT_TYPE_UNSPECIFIED = 0;
    EVENT_TYPE_CREATED = 1;
    EVENT_TYPE_UPDATED = 2;
    EVENT_TYPE_DELETED = 3;
  }
}

message FileChunk {
  bytes data = 1;
  int32 offset = 2;
}

message UploadFileResponse {
  string file_id = 1;
  int64 size = 2;
}

message ChatMessage {
  string user_id = 1;
  string content = 2;
  google.protobuf.Timestamp timestamp = 3;
}
```

## Implementation Examples

### Server Implementation (Node.js)

```typescript
import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';

// Load proto file
const packageDefinition = protoLoader.loadSync('user.proto', {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true,
});

const userProto = grpc.loadPackageDefinition(packageDefinition).user.v1;

// Implement service methods
const userService = {
  async GetUser(
    call: grpc.ServerUnaryCall<GetUserRequest, GetUserResponse>,
    callback: grpc.sendUnaryData<GetUserResponse>
  ) {
    try {
      const user = await db.users.findById(call.request.id);

      if (!user) {
        return callback({
          code: grpc.status.NOT_FOUND,
          message: 'User not found',
        });
      }

      callback(null, { user });
    } catch (error) {
      callback({
        code: grpc.status.INTERNAL,
        message: error.message,
      });
    }
  },

  async CreateUser(
    call: grpc.ServerUnaryCall<CreateUserRequest, CreateUserResponse>,
    callback: grpc.sendUnaryData<CreateUserResponse>
  ) {
    try {
      const user = await db.users.create(call.request);
      callback(null, { user, errors: [] });
    } catch (error) {
      if (error.code === 'DUPLICATE_EMAIL') {
        callback(null, {
          user: null,
          errors: [
            {
              field: 'email',
              message: 'Email already exists',
              code: 'DUPLICATE_EMAIL',
            },
          ],
        });
      } else {
        callback({
          code: grpc.status.INTERNAL,
          message: error.message,
        });
      }
    }
  },

  async ListUsers(
    call: grpc.ServerUnaryCall<ListUsersRequest, ListUsersResponse>,
    callback: grpc.sendUnaryData<ListUsersResponse>
  ) {
    const { page_size, page_token, filter } = call.request;

    const result = await db.users.findMany({
      limit: page_size || 20,
      cursor: page_token,
      filter,
    });

    callback(null, {
      users: result.users,
      next_page_token: result.nextCursor,
      total_size: result.totalCount,
    });
  },

  // Server streaming
  WatchUser(call: grpc.ServerWritableStream<WatchUserRequest, UserEvent>) {
    const userId = call.request.user_id;

    // Subscribe to changes
    const subscription = eventBus.subscribe(`user:${userId}`, (event) => {
      call.write({
        user_id: userId,
        type: event.type,
        user: event.user,
      });
    });

    // Cleanup on client disconnect
    call.on('cancelled', () => {
      subscription.unsubscribe();
    });
  },
};

// Create and start server
const server = new grpc.Server();
server.addService(userProto.UserService.service, userService);

server.bindAsync(
  '0.0.0.0:50051',
  grpc.ServerCredentials.createInsecure(),
  (err, port) => {
    if (err) {
      console.error('Failed to start server:', err);
      return;
    }
    console.log(`Server running on port ${port}`);
    server.start();
  }
);
```

### Client Implementation (Node.js)

```typescript
import * as grpc from '@grpc/grpc-js';
import * as protoLoader from '@grpc/proto-loader';

// Load proto
const packageDefinition = protoLoader.loadSync('user.proto');
const userProto = grpc.loadPackageDefinition(packageDefinition).user.v1;

// Create client
const client = new userProto.UserService(
  'localhost:50051',
  grpc.credentials.createInsecure()
);

// Unary call
client.GetUser({ id: '123' }, (err, response) => {
  if (err) {
    console.error('Error:', err.message);
    return;
  }
  console.log('User:', response.user);
});

// Promisified version
function getUser(id: string): Promise<GetUserResponse> {
  return new Promise((resolve, reject) => {
    client.GetUser({ id }, (err, response) => {
      if (err) reject(err);
      else resolve(response);
    });
  });
}

// Server streaming
const stream = client.WatchUser({ user_id: '123' });

stream.on('data', (event: UserEvent) => {
  console.log('User event:', event);
});

stream.on('error', (err) => {
  console.error('Stream error:', err);
});

stream.on('end', () => {
  console.log('Stream ended');
});

// Client streaming
const uploadStream = client.UploadFile((err, response) => {
  if (err) {
    console.error('Upload failed:', err);
    return;
  }
  console.log('Upload complete:', response.file_id);
});

// Send chunks
uploadStream.write({ data: chunk1, offset: 0 });
uploadStream.write({ data: chunk2, offset: 1024 });
uploadStream.end();

// Bidirectional streaming
const chatStream = client.Chat();

chatStream.on('data', (message: ChatMessage) => {
  console.log('Received:', message.content);
});

chatStream.write({
  user_id: '123',
  content: 'Hello',
  timestamp: new Date().toISOString(),
});
```

## Error Handling

### Status Codes

| Code | Meaning | Use Case |
|------|---------|----------|
| OK | Success | Operation completed |
| CANCELLED | Cancelled | Client cancelled request |
| UNKNOWN | Unknown error | Unexpected error |
| INVALID_ARGUMENT | Bad request | Invalid input |
| DEADLINE_EXCEEDED | Timeout | Request timed out |
| NOT_FOUND | Not found | Resource doesn't exist |
| ALREADY_EXISTS | Conflict | Resource already exists |
| PERMISSION_DENIED | Forbidden | Not authorized |
| UNAUTHENTICATED | Unauthorized | Not authenticated |
| RESOURCE_EXHAUSTED | Too many requests | Rate limit exceeded |
| FAILED_PRECONDITION | Precondition failed | Invalid state |
| UNIMPLEMENTED | Not implemented | Method not supported |
| INTERNAL | Server error | Internal error |
| UNAVAILABLE | Service unavailable | Service down |

### Error Details

```typescript
import { status as Status } from '@grpc/grpc-js';

// Simple error
callback({
  code: Status.NOT_FOUND,
  message: 'User not found',
});

// Error with metadata
const metadata = new grpc.Metadata();
metadata.add('user-id', userId);
metadata.add('trace-id', traceId);

callback({
  code: Status.INVALID_ARGUMENT,
  message: 'Invalid email format',
  metadata,
});

// Structured error in response (preferred)
callback(null, {
  user: null,
  errors: [
    {
      field: 'email',
      message: 'Invalid email format',
      code: 'INVALID_EMAIL',
    },
  ],
});
```

## Metadata (Headers)

### Sending Metadata (Client)

```typescript
const metadata = new grpc.Metadata();
metadata.add('authorization', 'Bearer token123');
metadata.add('request-id', 'req-abc-123');

client.GetUser({ id: '123' }, metadata, (err, response) => {
  // ...
});
```

### Reading Metadata (Server)

```typescript
const userService = {
  GetUser(call, callback) {
    const metadata = call.metadata;
    const auth = metadata.get('authorization')[0];
    const requestId = metadata.get('request-id')[0];

    // Validate token
    const userId = validateToken(auth);
    if (!userId) {
      return callback({
        code: Status.UNAUTHENTICATED,
        message: 'Invalid token',
      });
    }

    // Process request
    // ...
  },
};
```

### Sending Response Metadata

```typescript
const userService = {
  GetUser(call, callback) {
    const responseMetadata = new grpc.Metadata();
    responseMetadata.add('server-version', '1.0.0');
    responseMetadata.add('request-id', requestId);

    call.sendMetadata(responseMetadata);

    // Send response
    callback(null, { user });
  },
};
```

## Advanced Patterns

### Interceptors (Middleware)

```typescript
// Client interceptor
function authInterceptor(options, nextCall) {
  return new grpc.InterceptingCall(nextCall(options), {
    start(metadata, listener, next) {
      // Add auth token to all requests
      metadata.add('authorization', `Bearer ${getToken()}`);
      next(metadata, listener);
    },
  });
}

// Use interceptor
const client = new userProto.UserService(
  'localhost:50051',
  grpc.credentials.createInsecure(),
  { interceptors: [authInterceptor] }
);
```

### Deadlines/Timeouts

```typescript
// Set deadline (client)
const deadline = new Date();
deadline.setSeconds(deadline.getSeconds() + 5); // 5 second timeout

client.GetUser({ id: '123' }, { deadline }, (err, response) => {
  if (err && err.code === Status.DEADLINE_EXCEEDED) {
    console.error('Request timed out');
  }
});
```

### Retry Policy

```typescript
const retryPolicy = {
  maxAttempts: 3,
  initialBackoff: '0.1s',
  maxBackoff: '10s',
  backoffMultiplier: 2,
  retryableStatusCodes: [Status.UNAVAILABLE, Status.DEADLINE_EXCEEDED],
};

// Configure in service config
const serviceConfig = {
  methodConfig: [
    {
      name: [{ service: 'user.v1.UserService' }],
      retryPolicy,
    },
  ],
};
```

### Load Balancing

```typescript
// Client-side load balancing
const client = new userProto.UserService(
  'dns:///users.example.com', // DNS with multiple IPs
  grpc.credentials.createInsecure(),
  { 'grpc.lb_policy_name': 'round_robin' }
);
```

## Security

### TLS/SSL

```typescript
// Server with TLS
const credentials = grpc.ServerCredentials.createSsl(
  fs.readFileSync('ca.pem'),
  [
    {
      cert_chain: fs.readFileSync('server-cert.pem'),
      private_key: fs.readFileSync('server-key.pem'),
    },
  ],
  true // Request client certificate
);

server.bindAsync('0.0.0.0:50051', credentials, callback);

// Client with TLS
const credentials = grpc.credentials.createSsl(
  fs.readFileSync('ca.pem'),
  fs.readFileSync('client-key.pem'),
  fs.readFileSync('client-cert.pem')
);

const client = new userProto.UserService('users.example.com:50051', credentials);
```

### Authentication

```typescript
// JWT authentication
const userService = {
  async GetUser(call, callback) {
    const token = call.metadata.get('authorization')[0]?.replace('Bearer ', '');

    try {
      const payload = jwt.verify(token, SECRET_KEY);
      const userId = payload.sub;

      // Authorized - proceed
      const user = await db.users.findById(call.request.id);
      callback(null, { user });
    } catch (error) {
      callback({
        code: Status.UNAUTHENTICATED,
        message: 'Invalid or expired token',
      });
    }
  },
};
```

## Best Practices

### 1. Use Proto3

Proto3 is simpler and has better support across languages.

### 2. Version Your APIs

```protobuf
package user.v1;

// Later
package user.v2;
```

### 3. One Message Per RPC

```protobuf
// Good
rpc CreateUser(CreateUserRequest) returns (CreateUserResponse);

message CreateUserRequest {
  string email = 1;
  string name = 2;
}

// Avoid
rpc CreateUser(User) returns (User);
```

### 4. Use Standard Google Types

```protobuf
import "google/protobuf/timestamp.proto";
import "google/protobuf/duration.proto";
import "google/protobuf/empty.proto";
import "google/protobuf/wrappers.proto"; // For nullable primitives
```

### 5. Pagination Pattern

```protobuf
message ListUsersRequest {
  int32 page_size = 1;        // Max items to return
  string page_token = 2;       // Cursor for next page
}

message ListUsersResponse {
  repeated User users = 1;
  string next_page_token = 2;  // Cursor for next page
}
```

### 6. Error Handling in Response

Include errors in response message, not just gRPC status:

```protobuf
message CreateUserResponse {
  User user = 1;
  repeated ValidationError errors = 2;
}
```

### 7. Document with Comments

```protobuf
// UserService provides user management operations.
service UserService {
  // GetUser retrieves a user by ID.
  //
  // Returns NOT_FOUND if user doesn't exist.
  rpc GetUser(GetUserRequest) returns (GetUserResponse);
}

// User represents a user in the system.
message User {
  // Unique identifier for the user.
  string id = 1;

  // User's email address. Must be unique.
  string email = 2;
}
```

### 8. Use Enums Carefully

Always include zero value:

```protobuf
enum Status {
  STATUS_UNSPECIFIED = 0;  // Required
  STATUS_ACTIVE = 1;
  STATUS_INACTIVE = 2;
}
```

### 9. Never Reuse Field Numbers

Mark deleted fields as reserved:

```protobuf
message User {
  reserved 2, 3;  // Old fields
  reserved "old_name";

  string id = 1;
  string email = 4;
}
```

### 10. Backward Compatibility

- Add new fields (don't remove)
- Make fields optional
- Use defaults carefully
- Version breaking changes

## Testing

```typescript
import { createServer, Server } from 'http';
import * as grpc from '@grpc/grpc-js';

describe('UserService', () => {
  let server: grpc.Server;
  let client: any;

  beforeAll((done) => {
    server = new grpc.Server();
    server.addService(userProto.UserService.service, userService);
    server.bindAsync('0.0.0.0:0', grpc.ServerCredentials.createInsecure(), (err, port) => {
      server.start();
      client = new userProto.UserService(
        `localhost:${port}`,
        grpc.credentials.createInsecure()
      );
      done();
    });
  });

  afterAll(() => {
    server.forceShutdown();
  });

  it('should get user by id', (done) => {
    client.GetUser({ id: '123' }, (err, response) => {
      expect(err).toBeNull();
      expect(response.user.id).toBe('123');
      done();
    });
  });

  it('should return NOT_FOUND for missing user', (done) => {
    client.GetUser({ id: '999' }, (err, response) => {
      expect(err.code).toBe(grpc.status.NOT_FOUND);
      done();
    });
  });
});
```
