# GraphQL API Design Guide: Query Examples

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

