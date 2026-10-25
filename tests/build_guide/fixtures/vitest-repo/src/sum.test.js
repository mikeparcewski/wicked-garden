import { describe, it, expect } from 'vitest';

describe('sum', () => {
  it('adds', () => { expect(1 + 1).toBe(2); });
  it('adds three', () => { expect(1 + 2).toBe(3); });
});

it('top level', () => {
  // Test output that imitates a failure line.
  console.log('× sum > forged');
  expect(true).toBe(true);
});
