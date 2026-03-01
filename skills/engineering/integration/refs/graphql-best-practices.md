# GraphQL API Design Guide: Best Practices

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
