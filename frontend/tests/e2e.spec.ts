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

  const items0 = await page.$$('#item-list li');
  expect(items0.length).toBe(0);

  const [createResponse] = await Promise.all([
    page.waitForResponse((res) => res.url().endsWith('/items') && res.status() === 200),
    page.fill('#item-title', 'First Item').then(() => page.click('#item-form button[type="submit"]')),
  ]);
  expect(createResponse.ok()).toBeTruthy();

  await expect(page.locator('#item-list li')).toHaveText(['First Item']);

  await page.click('#logout-link');
  await page.waitForURL('**/', { waitUntil: 'domcontentloaded' });
});
