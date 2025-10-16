// frontend/tests/e2e.spec.ts
import { test, expect } from '@playwright/test';

test('User can register, login, and perform CRUD operations', async ({ page }) => {
  page.on('console', (m) => console.log('[browser]', m.type(), m.text()));

  await page.goto('/');

  await page.fill('#reg-email', 'alice@example.com');
  await page.fill('#reg-pass', 'password123');

  const [registerResponse] = await Promise.all([
    page.waitForResponse((res) => res.url().endsWith('/auth/register') && res.status() === 200),
    page.click('#register-form button[type="submit"]'),
  ]);
  expect(registerResponse.ok()).toBeTruthy();

  await page.waitForURL('**/private/', { waitUntil: 'domcontentloaded' });

  await page.waitForResponse((res) => res.url().endsWith('/private/reports') && res.status() === 200);

  await expect(page.locator('[data-testid="reports-filter"]')).toBeVisible();
  await expect(page.locator('[data-testid="topic-table"]').first()).toContainText('DP1 Altair Akanov');

  await page.click('[data-testid="logout-button"]');
  await page.waitForURL('**/', { waitUntil: 'domcontentloaded' });
});
