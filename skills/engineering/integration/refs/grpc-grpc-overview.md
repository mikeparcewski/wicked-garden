# gRPC API Design Guide: gRPC Overview

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

