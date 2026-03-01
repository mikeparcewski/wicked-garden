# GraphQL API Design Guide: Schema Design Patterns

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

