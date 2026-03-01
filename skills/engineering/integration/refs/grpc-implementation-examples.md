# gRPC API Design Guide: Implementation Examples

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

