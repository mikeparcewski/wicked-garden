# GraphQL API Design Guide

Comprehensive guide to designing GraphQL APIs with schemas, resolvers, and best practices.

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

## Query Examples

### Basic Query

```graphql
query GetUser {
  user(id: "123") {
    id
    name
    email
  }
}

# Response
{
  "data": {
    "user": {
      "id": "123",
      "name": "Alice",
      "email": "alice@example.com"
    }
  }
}
```

### Nested Query

```graphql
query GetUserWithPosts {
  user(id: "123") {
    id
    name
    posts {
      id
      title
      comments {
        id
        content
        author {
          name
        }
      }
    }
  }
}
```

### Query with Variables

```graphql
query GetUsers($limit: Int!, $filter: UserFilter) {
  users(limit: $limit, filter: $filter) {
    edges {
      node {
        id
        name
        email
      }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}

# Variables
{
  "limit": 10,
  "filter": {
    "role": "ADMIN"
  }
}
```

### Fragments

```graphql
fragment UserFields on User {
  id
  name
  email
  createdAt
}

query GetUsers {
  currentUser {
    ...UserFields
  }
  users(limit: 5) {
    edges {
      node {
        ...UserFields
      }
    }
  }
}
```

### Aliases

```graphql
query GetMultipleUsers {
  admin: user(id: "1") {
    id
    name
  }
  guest: user(id: "2") {
    id
    name
  }
}

# Response
{
  "data": {
    "admin": { "id": "1", "name": "Admin User" },
    "guest": { "id": "2", "name": "Guest User" }
  }
}
```

## Mutation Examples

### Create Resource

```graphql
mutation CreateUser($input: CreateUserInput!) {
  createUser(input: $input) {
    success
    user {
      id
      name
      email
    }
    errors {
      field
      message
      code
    }
  }
}

# Variables
{
  "input": {
    "name": "Bob",
    "email": "bob@example.com",
    "password": "secret123"
  }
}

# Success Response
{
  "data": {
    "createUser": {
      "success": true,
      "user": {
        "id": "456",
        "name": "Bob",
        "email": "bob@example.com"
      },
      "errors": []
    }
  }
}

# Error Response
{
  "data": {
    "createUser": {
      "success": false,
      "user": null,
      "errors": [
        {
          "field": "email",
          "message": "Email already exists",
          "code": "DUPLICATE_EMAIL"
        }
      ]
    }
  }
}
```

### Update Resource

```graphql
mutation UpdateUser($id: ID!, $input: UpdateUserInput!) {
  updateUser(id: $id, input: $input) {
    success
    user {
      id
      name
      email
    }
  }
}

# Variables
{
  "id": "456",
  "input": {
    "name": "Robert"
  }
}
```

### Delete Resource

```graphql
mutation DeleteUser($id: ID!) {
  deleteUser(id: $id) {
    success
    deletedId: ID
  }
}
```

## Schema Design Patterns

### Connection Pattern (Relay-style Pagination)

```graphql
type Query {
  posts(
    first: Int
    after: String
    last: Int
    before: String
  ): PostConnection!
}

type PostConnection {
  edges: [PostEdge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}

type PostEdge {
  node: Post!
  cursor: String!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}

# Usage
query GetPosts($first: Int!, $after: String) {
  posts(first: $first, after: $after) {
    edges {
      node {
        id
        title
      }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

### Node Interface (Global ID)

```graphql
interface Node {
  id: ID!
}

type User implements Node {
  id: ID!
  name: String!
}

type Post implements Node {
  id: ID!
  title: String!
}

type Query {
  node(id: ID!): Node
  nodes(ids: [ID!]!): [Node]!
}

# Usage - fetch any object by ID
query GetNode {
  node(id: "UG9zdDoxMjM=") {
    id
    ... on Post {
      title
      author {
        name
      }
    }
  }
}
```

### Union Types

```graphql
union SearchResult = User | Post | Comment

type Query {
  search(query: String!): [SearchResult!]!
}

# Usage
query Search {
  search(query: "graphql") {
    __typename
    ... on User {
      name
      email
    }
    ... on Post {
      title
      content
    }
    ... on Comment {
      content
      author {
        name
      }
    }
  }
}
```

### Interface Types

```graphql
interface Content {
  id: ID!
  title: String!
  createdAt: DateTime!
  author: User!
}

type Post implements Content {
  id: ID!
  title: String!
  createdAt: DateTime!
  author: User!
  content: String!
  tags: [String!]!
}

type Video implements Content {
  id: ID!
  title: String!
  createdAt: DateTime!
  author: User!
  url: String!
  duration: Int!
}

type Query {
  contentFeed: [Content!]!
}
```

## Resolver Implementation

### Basic Resolver (TypeScript)

```typescript
// Type definitions
type User = {
  id: string;
  email: string;
  name: string;
};

type Context = {
  userId?: string;
  db: Database;
};

// Resolvers
const resolvers = {
  Query: {
    user: async (
      parent: unknown,
      args: { id: string },
      context: Context
    ): Promise<User | null> => {
      return await context.db.users.findById(args.id);
    },

    users: async (
      parent: unknown,
      args: { limit: number; offset: number },
      context: Context
    ): Promise<User[]> => {
      return await context.db.users.findMany({
        limit: args.limit,
        offset: args.offset,
      });
    },

    currentUser: async (
      parent: unknown,
      args: {},
      context: Context
    ): Promise<User | null> => {
      if (!context.userId) return null;
      return await context.db.users.findById(context.userId);
    },
  },

  Mutation: {
    createUser: async (
      parent: unknown,
      args: { input: CreateUserInput },
      context: Context
    ): Promise<CreateUserPayload> => {
      try {
        const user = await context.db.users.create(args.input);
        return {
          success: true,
          user,
          errors: [],
        };
      } catch (error) {
        return {
          success: false,
          user: null,
          errors: [
            {
              field: null,
              message: error.message,
              code: 'CREATE_FAILED',
            },
          ],
        };
      }
    },
  },

  User: {
    // Field resolver for nested data
    posts: async (
      parent: User,
      args: {},
      context: Context
    ): Promise<Post[]> => {
      return await context.db.posts.findByAuthorId(parent.id);
    },
  },
};
```

### DataLoader (Solving N+1 Problem)

```typescript
import DataLoader from 'dataloader';

// Create loader
const userLoader = new DataLoader<string, User>(async (ids) => {
  const users = await db.users.findByIds(ids);
  // Return in same order as requested IDs
  return ids.map((id) => users.find((u) => u.id === id));
});

// Use in resolver
const resolvers = {
  Post: {
    author: async (parent: Post, args: {}, context: Context): Promise<User> => {
      // Batches and caches requests
      return await context.loaders.user.load(parent.authorId);
    },
  },
};

// Context setup
const context = ({ req }) => ({
  userId: req.userId,
  db: database,
  loaders: {
    user: new DataLoader((ids) => batchLoadUsers(ids)),
    post: new DataLoader((ids) => batchLoadPosts(ids)),
  },
});
```

## Error Handling

### Field-Level Errors

```graphql
type CreateUserPayload {
  success: Boolean!
  user: User
  errors: [UserError!]!
}

type UserError {
  field: String    # Which input field caused error
  message: String!
  code: String!    # Machine-readable error code
}
```

### Top-Level Errors

```json
{
  "errors": [
    {
      "message": "Unauthorized",
      "extensions": {
        "code": "UNAUTHENTICATED",
        "timestamp": "2025-01-24T10:00:00Z"
      },
      "path": ["currentUser"]
    }
  ],
  "data": {
    "currentUser": null
  }
}
```

### Custom Error Codes

```typescript
class AuthenticationError extends Error {
  constructor(message: string) {
    super(message);
    this.extensions = {
      code: 'UNAUTHENTICATED',
    };
  }
}

class ValidationError extends Error {
  constructor(message: string, field: string) {
    super(message);
    this.extensions = {
      code: 'VALIDATION_ERROR',
      field,
    };
  }
}

// In resolver
if (!context.userId) {
  throw new AuthenticationError('Must be logged in');
}
```

## Security

### Authentication

```typescript
const resolvers = {
  Query: {
    currentUser: async (parent, args, context) => {
      // Check authentication
      if (!context.userId) {
        throw new AuthenticationError('Not authenticated');
      }
      return await db.users.findById(context.userId);
    },
  },
};

// Context from request
const context = ({ req }) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  const userId = verifyToken(token);
  return { userId, db };
};
```

### Authorization

```typescript
const resolvers = {
  Mutation: {
    deletePost: async (parent, args: { id: string }, context) => {
      const post = await db.posts.findById(args.id);

      // Check authorization
      if (post.authorId !== context.userId) {
        throw new ForbiddenError('Not authorized to delete this post');
      }

      await db.posts.delete(args.id);
      return { success: true };
    },
  },
};
```

### Query Depth Limiting

```typescript
import { createComplexityLimitRule } from 'graphql-validation-complexity';

const complexityLimit = createComplexityLimitRule(1000, {
  scalarCost: 1,
  objectCost: 5,
  listFactor: 10,
});

const server = new ApolloServer({
  schema,
  validationRules: [complexityLimit],
});
```

### Query Cost Analysis

```typescript
const costAnalysis = {
  Query: {
    users: { complexity: ({ args }) => args.limit * 5 },
    posts: { complexity: ({ args }) => args.limit * 10 },
  },
  User: {
    posts: { complexity: 10 },
  },
};
```

## Performance Optimization

### DataLoader (Batching)

Batch multiple requests into single database query.

### Query Complexity Analysis

Prevent expensive queries:
```typescript
// Too complex - would make 1000s of queries
query ExpensiveQuery {
  users(limit: 100) {
    posts(limit: 100) {
      comments(limit: 100) {
        author {
          posts(limit: 100) {
            # ...
          }
        }
      }
    }
  }
}
```

### Persisted Queries

Pre-register queries, send only hash:
```graphql
# Client sends
{ "id": "abc123", "variables": { "limit": 10 } }

# Instead of full query
```

### Caching

```typescript
// Field-level cache hints
type User {
  id: ID!
  name: String! @cacheControl(maxAge: 3600)
  email: String! @cacheControl(maxAge: 0) # Private
}

// HTTP caching
res.set('Cache-Control', 'public, max-age=3600');
```

## Best Practices

### 1. Schema-First Design

Design schema before implementation. It's your API contract.

### 2. Nullable by Default

Make fields nullable unless they're truly required. Prevents breaking changes.

```graphql
# Good
type User {
  name: String  # Can add later without breaking
}

# Risky
type User {
  name: String! # Can't make nullable later
}
```

### 3. Use Enums

```graphql
enum UserRole {
  ADMIN
  USER
  GUEST
}

# Better than String
```

### 4. Input Types for Mutations

```graphql
# Good
input CreateUserInput {
  name: String!
  email: String!
}

mutation {
  createUser(input: CreateUserInput!): User
}

# Avoid
mutation {
  createUser(name: String!, email: String!): User
}
```

### 5. Pagination for Lists

Always paginate collections. Use Connection pattern.

### 6. Descriptive Names

```graphql
# Good
type Query {
  user(id: ID!): User
  userByEmail(email: String!): User
}

# Avoid
type Query {
  get(id: ID!): User
  fetch(email: String!): User
}
```

### 7. Document Your Schema

```graphql
"""
Represents a user in the system.
"""
type User {
  """
  Unique identifier for the user.
  """
  id: ID!

  """
  User's email address. Must be unique.
  """
  email: String!
}
```

### 8. Versioning

Evolve schema without breaking changes:
- Add new fields (nullable)
- Deprecate old fields
- Never remove fields abruptly

```graphql
type User {
  oldField: String @deprecated(reason: "Use newField instead")
  newField: String
}
```

### 9. Error Handling in Payload

Return errors as part of mutation payload, not just top-level errors.

### 10. Testing

Test resolvers thoroughly, including error cases.

```typescript
describe('User resolver', () => {
  it('returns user by id', async () => {
    const result = await resolvers.Query.user(
      null,
      { id: '123' },
      { db: mockDb }
    );
    expect(result).toEqual({ id: '123', name: 'Alice' });
  });

  it('throws when user not found', async () => {
    await expect(
      resolvers.Query.user(null, { id: '999' }, { db: mockDb })
    ).rejects.toThrow('User not found');
  });
});
```
