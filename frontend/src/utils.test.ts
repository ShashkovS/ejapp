import { expect, test } from 'vitest';

// A trivial example test (replace with meaningful UI logic tests as needed)
function sum(a: number, b: number) {
  return a + b;
}

test('sum adds numbers correctly', () => {
  expect(sum(2, 3)).toBe(5);
});
