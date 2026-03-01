# Error Handling Guide: Best Practices

## Best Practices

### 1. Use Specific Error Codes

```typescript
// Good
throw new ValidationError([
  { field: 'email', code: 'INVALID_FORMAT', message: '...' }
]);

// Bad
throw new Error('Validation failed');
```

### 2. Include Request ID

Always include request ID for tracing:
```typescript
res.status(500).json({
  error: {
    message: 'Internal error',
    request_id: req.id  // Client can provide this to support
  }
});
```

### 3. Don't Expose Sensitive Details

```typescript
// Bad - exposes database structure
{
  "error": "ER_DUP_ENTRY: Duplicate entry 'user@example.com' for key 'users.email_unique'"
}

// Good - sanitized message
{
  "error": {
    "code": "CONFLICT",
    "message": "User with this email already exists"
  }
}
```

### 4. Distinguish Client vs Server Errors

```typescript
if (error.status >= 400 && error.status < 500) {
  // Client error - safe to show details
  return error.message;
} else {
  // Server error - hide details
  return 'An unexpected error occurred';
}
```

### 5. Provide Actionable Messages

```typescript
// Bad
{ "error": "Invalid input" }

// Good
{
  "error": {
    "message": "Email address is required and must be in valid format",
    "field": "email",
    "example": "user@example.com"
  }
}
```

### 6. Handle Async Errors

Always catch async errors:
```typescript
// Good
app.get('/users', asyncHandler(async (req, res) => {
  const users = await userService.findAll();
  res.json({ users });
}));

// Bad - unhandled promise rejection
app.get('/users', async (req, res) => {
  const users = await userService.findAll();
  res.json({ users });
});
```

### 7. Centralized Error Handling

Use middleware for consistent error responses:
```typescript
app.use(errorHandler);
```

### 8. Log Appropriately

```typescript
// Error severity levels
logger.error('Critical error', error);  // Requires immediate attention
logger.warn('Recoverable error', error); // Should be monitored
logger.info('Expected error', error);    // Part of normal flow
```

### 9. Graceful Degradation

```typescript
try {
  const recommendations = await recommendationService.get(userId);
  return recommendations;
} catch (error) {
  // Log error but don't fail the request
  logger.warn('Recommendations unavailable', error);
  return []; // Return empty array as fallback
}
```

### 10. Test Error Scenarios

```typescript
describe('User creation', () => {
  it('should return 409 for duplicate email', async () => {
    await createUser({ email: 'test@example.com' });

    const response = await request(app)
      .post('/users')
      .send({ email: 'test@example.com' });

    expect(response.status).toBe(409);
    expect(response.body.error.code).toBe('CONFLICT');
  });
});
```
