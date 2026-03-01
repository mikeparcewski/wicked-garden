# gRPC API Design Guide: Metadata (Headers)

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

