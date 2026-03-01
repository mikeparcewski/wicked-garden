# gRPC API Design Guide: Testing

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
