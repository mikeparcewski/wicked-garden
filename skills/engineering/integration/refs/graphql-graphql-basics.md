# GraphQL API Design Guide: GraphQL Basics

## GraphQL Basics

### What is GraphQL?

- Query language for APIs
- Strong type system
- Client specifies exactly what data it needs
- Single endpoint (typically `/graphql`)
- Introspection and tooling

### When to Use GraphQL

**Good Fit**:
- Complex data relationships
- Multiple client types (web, mobile, desktop)
- Over-fetching/under-fetching problems
- Need for flexible queries
- Developer experience priority

**Poor Fit**:
- Simple CRUD operations
- File uploads/downloads
- Real-time requirements (use subscriptions carefully)
- Caching is critical (more complex than REST)

## Schema Definition

### Type System

```graphql
# Scalar Types
String
Int
Float
Boolean
ID

# Custom Scalar
scalar DateTime
scalar JSON
scalar Upload

# Object Type
type User {
  id: ID!
  email: String!
  name: String
  createdAt: DateTime!
  posts: [Post!]!
}

# Non-nullable (!)
name: String!    # Required
names: [String!]! # Required array of required strings

# Lists
tags: [String]      # Nullable array, nullable elements
tags: [String]!     # Required array, nullable elements
tags: [String!]!    # Required array, required elements
```

### Queries

```graphql
type Query {
  # Get single resource
  user(id: ID!): User

  # Get collection
  users(
    limit: Int = 20
    offset: Int = 0
    filter: UserFilter
    sort: UserSort
  ): UserConnection!

  # Search
  searchUsers(query: String!): [User!]!

  # Complex query
  currentUser: User
}

# Input types for filtering
input UserFilter {
  email: String
  name: String
  createdAfter: DateTime
  role: UserRole
}

enum UserSort {
  NAME_ASC
  NAME_DESC
  CREATED_AT_ASC
  CREATED_AT_DESC
}

# Connection pattern for pagination
type UserConnection {
  edges: [UserEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type UserEdge {
  node: User!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}
```

### Mutations

```graphql
type Mutation {
  # Create
  createUser(input: CreateUserInput!): CreateUserPayload!

  # Update
  updateUser(id: ID!, input: UpdateUserInput!): UpdateUserPayload!

  # Delete
  deleteUser(id: ID!): DeleteUserPayload!

  # Complex operation
  publishPost(id: ID!): PublishPostPayload!
}

# Input type
input CreateUserInput {
  email: String!
  name: String!
  password: String!
  role: UserRole = USER
}

# Payload type (includes errors)
type CreateUserPayload {
  user: User
  errors: [UserError!]
  success: Boolean!
}

type UserError {
  field: String
  message: String!
  code: String!
}

enum UserRole {
  ADMIN
  USER
  GUEST
}
```

### Subscriptions

```graphql
type Subscription {
  # Subscribe to new posts
  postCreated(authorId: ID): Post!

  # Subscribe to updates
  postUpdated(id: ID!): Post!

  # Real-time notifications
  notificationReceived: Notification!
}

type Notification {
  id: ID!
  type: NotificationType!
  message: String!
  createdAt: DateTime!
}

enum NotificationType {
  COMMENT
  LIKE
  MENTION
}
```

