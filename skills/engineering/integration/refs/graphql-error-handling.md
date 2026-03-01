# GraphQL API Design Guide: Error Handling

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

