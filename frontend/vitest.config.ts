// frontend/vitest.config.ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['src/**/*.test.ts'],
    exclude: [
      'node_modules',
      'dist',
      'e2e/**',
      'tests/**', // your Playwright tests live here
      '**/*.e2e.*',
      '**/playwright.*',
    ],
  },
});
