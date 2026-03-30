/**
 * E2E tests for category filter on tenders page
 * Tests that Стоки/Услуги/Работи filters actually work end-to-end
 *
 * Run:  npx playwright test tests/e2e/test_category_filter.spec.ts --project=chromium --reporter=list
 */
import { test, expect, type Page, type Response } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'https://www.nabavkidata.com';
const API_URL = process.env.PLAYWRIGHT_API_URL || 'https://api.nabavkidata.com';
const TEST_EMAIL = 'playwright-test@nabavkidata.com';
const TEST_PASS = 'TestPass123!';

// Helper: wait for tenders API response
async function waitForTendersApi(page: Page): Promise<Response> {
  return page.waitForResponse(
    (resp) => resp.url().includes('/api/tenders') && !resp.url().includes('/stats') && !resp.url().includes('/by-id') && resp.status() === 200,
    { timeout: 20000 }
  );
}

// Helper: wait for tenders to finish loading (cards visible)
async function waitForTendersLoaded(page: Page) {
  await page.locator('a[href*="/tenders/"]').first().waitFor({ state: 'visible', timeout: 20000 });
  await page.waitForTimeout(500);
}

// Helper: login via the UI login form
async function login(page: Page) {
  await page.goto(`${BASE_URL}/auth/login`, { waitUntil: 'networkidle' });

  const emailField = page.locator('#email');
  await emailField.waitFor({ state: 'visible', timeout: 10000 });

  await emailField.click();
  await emailField.press('Meta+a');
  await emailField.type(TEST_EMAIL, { delay: 30 });

  const passwordField = page.locator('#password');
  await passwordField.click();
  await passwordField.press('Meta+a');
  await passwordField.type(TEST_PASS, { delay: 30 });

  await page.locator('button[type="submit"]').click();

  await page.waitForURL((url) => !url.pathname.includes('/auth/login'), { timeout: 20000 });
  await page.waitForTimeout(1000);
}

// Helper: open category dropdown and select a value
async function selectCategory(page: Page, category: string) {
  const label = page.locator('label', { hasText: 'Категорија' });
  const container = label.locator('..');
  const trigger = container.locator('[role="combobox"]');
  await trigger.click();
  await page.waitForSelector('[role="option"]', { timeout: 5000 });
  await page.locator('[role="option"]', { hasText: category }).click();
}

// Helper: select category and wait for results to settle
async function selectCategoryAndWait(page: Page, category: string) {
  await selectCategory(page, category);
  // Wait for debounced API call + response + render
  // The page debounces at 300ms, plus network latency
  await page.waitForTimeout(2000);
  await waitForTendersLoaded(page);
}

// Helper: get the result count shown on the page
async function getResultCount(page: Page): Promise<number> {
  // Match patterns like "863 отворени тендери", "475 тендери", "887 резултати"
  const countLocator = page.locator('text=/\\d[\\d,.]* .*тендери/i').first();
  await countLocator.waitFor({ state: 'visible', timeout: 10000 });
  const text = await countLocator.textContent();
  if (!text) return 0;
  const match = text.match(/([\d,.]+)/);
  if (!match) return 0;
  return parseInt(match[1].replace(/[,.]/g, ''), 10);
}

// ============================================================================
// API TESTS — backend verification (no browser needed)
// ============================================================================

test.describe('API - Category Filter', () => {
  test('returns results for each category', async ({ request }) => {
    for (const category of ['Стоки', 'Услуги', 'Работи']) {
      const response = await request.get(`${API_URL}/api/tenders`, {
        params: { category, status: 'open', page_size: 3 },
      });
      expect(response.status()).toBe(200);
      const data = await response.json();

      console.log(`  ${category}: ${data.total} total, ${data.items?.length} returned`);
      expect(data.total).toBeGreaterThan(0);
      expect(data.items?.length).toBeGreaterThan(0);

      for (const item of data.items) {
        expect(item.category).toBe(category);
      }
    }
  });

  test('no category returns more results than filtered', async ({ request }) => {
    const allResp = await request.get(`${API_URL}/api/tenders`, {
      params: { status: 'open', page_size: 1 },
    });
    const stokiResp = await request.get(`${API_URL}/api/tenders`, {
      params: { category: 'Стоки', status: 'open', page_size: 1 },
    });
    const allTotal = (await allResp.json()).total;
    const stokiTotal = (await stokiResp.json()).total;
    console.log(`  All: ${allTotal}, Стоки: ${stokiTotal}`);
    expect(allTotal).toBeGreaterThan(stokiTotal);
  });

  test('each category has distinct count', async ({ request }) => {
    const totals: Record<string, number> = {};
    for (const cat of ['Стоки', 'Услуги', 'Работи']) {
      const resp = await request.get(`${API_URL}/api/tenders`, {
        params: { category: cat, status: 'open', page_size: 1 },
      });
      totals[cat] = (await resp.json()).total;
    }
    console.log(`  Стоки=${totals['Стоки']}, Услуги=${totals['Услуги']}, Работи=${totals['Работи']}`);
    expect(totals['Стоки']).not.toBe(totals['Услуги']);
    expect(totals['Услуги']).not.toBe(totals['Работи']);
    expect(totals['Стоки']).toBeGreaterThan(totals['Работи']);
  });

  test('invalid category returns 0', async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/tenders`, {
      params: { category: 'FakeCategory', status: 'open', page_size: 1 },
    });
    expect(resp.status()).toBe(200);
    expect((await resp.json()).total).toBe(0);
  });

  test('category + search combo works', async ({ request }) => {
    const resp = await request.get(`${API_URL}/api/tenders`, {
      params: { category: 'Стоки', search: 'медицинска', status: 'open', page_size: 5 },
    });
    const data = await resp.json();
    console.log(`  Стоки + "медицинска": ${data.total} results`);
    for (const item of data.items || []) {
      expect(item.category).toBe('Стоки');
    }
  });

  test('category with all statuses returns more', async ({ request }) => {
    const openResp = await request.get(`${API_URL}/api/tenders`, {
      params: { category: 'Стоки', status: 'open', page_size: 1 },
    });
    const allResp = await request.get(`${API_URL}/api/tenders`, {
      params: { category: 'Стоки', page_size: 1 },
    });
    const openTotal = (await openResp.json()).total;
    const allTotal = (await allResp.json()).total;
    console.log(`  Стоки open: ${openTotal}, all: ${allTotal}`);
    expect(allTotal).toBeGreaterThan(openTotal);
  });
});

// ============================================================================
// UI TESTS — full browser e2e with login
// Filters apply immediately on selection (no Apply button)
// ============================================================================

test.describe.configure({ mode: 'serial' });

test.describe('UI - Category Filter', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto(`${BASE_URL}/tenders`, { waitUntil: 'domcontentloaded' });
    await waitForTendersLoaded(page);
  });

  test('page loads with category dropdown visible', async ({ page }) => {
    await expect(page.locator('label', { hasText: 'Категорија' })).toBeVisible();

    const tenderLinks = page.locator('a[href*="/tenders/"]');
    const count = await tenderLinks.count();
    console.log(`  Loaded with ${count} tender links`);
    expect(count).toBeGreaterThan(0);
  });

  test('dropdown shows category options', async ({ page }) => {
    const label = page.locator('label', { hasText: 'Категорија' });
    const container = label.locator('..');
    const trigger = container.locator('[role="combobox"]');
    await trigger.click();
    await page.waitForSelector('[role="option"]', { timeout: 5000 });

    for (const opt of ['Стоки', 'Услуги', 'Работи']) {
      await expect(page.locator('[role="option"]', { hasText: opt })).toBeVisible();
    }
    await page.keyboard.press('Escape');
  });

  test('selecting Стоки reduces result count (proves filtering works)', async ({ page }) => {
    const initialCount = await getResultCount(page);
    console.log(`  Initial results: ${initialCount}`);

    await selectCategoryAndWait(page, 'Стоки');
    const filteredCount = await getResultCount(page);
    console.log(`  After Стоки: ${filteredCount} results`);

    // Category filter must reduce results significantly
    // (Стоки is ~55% of tenders, so filtered should be clearly less than all)
    expect(filteredCount).toBeGreaterThan(0);
    expect(filteredCount).toBeLessThan(initialCount);
    // Стоки should be at most 80% of total (usually ~55%)
    expect(filteredCount).toBeLessThan(initialCount * 0.85);
  });

  test('selecting Услуги returns results', async ({ page }) => {
    await selectCategoryAndWait(page, 'Услуги');
    const count = await getResultCount(page);
    console.log(`  Услуги: ${count} results`);
    expect(count).toBeGreaterThan(0);
  });

  test('selecting Работи returns results', async ({ page }) => {
    await selectCategoryAndWait(page, 'Работи');
    const count = await getResultCount(page);
    console.log(`  Работи: ${count} results`);
    expect(count).toBeGreaterThan(0);
  });

  test('each category shows different result count', async ({ page }) => {
    const totals: Record<string, number> = {};

    for (const cat of ['Стоки', 'Услуги', 'Работи']) {
      await selectCategoryAndWait(page, cat);
      totals[cat] = await getResultCount(page);
    }
    console.log(`  Стоки=${totals['Стоки']}, Услуги=${totals['Услуги']}, Работи=${totals['Работи']}`);
    // At least two categories should have different counts
    const counts = Object.values(totals);
    const uniqueCounts = new Set(counts);
    expect(uniqueCounts.size).toBeGreaterThanOrEqual(2);
  });

  test('reset clears category and shows more results', async ({ page }) => {
    await selectCategoryAndWait(page, 'Стоки');
    const filteredCount = await getResultCount(page);

    // Click reset
    await page.locator('button', { hasText: 'Ресетирај' }).click();
    await page.waitForTimeout(2000);
    await waitForTendersLoaded(page);
    const resetCount = await getResultCount(page);

    console.log(`  Filtered: ${filteredCount}, Reset: ${resetCount}`);
    expect(resetCount).toBeGreaterThan(filteredCount);
  });

  test('category filter updates URL', async ({ page }) => {
    await selectCategoryAndWait(page, 'Услуги');
    await page.waitForTimeout(500);

    const url = page.url();
    console.log(`  URL: ${url}`);
    expect(decodeURIComponent(url)).toContain('category');
  });

  test('direct URL with category param loads filtered results', async ({ page }) => {
    await page.goto(`${BASE_URL}/tenders?category=%D0%A1%D1%82%D0%BE%D0%BA%D0%B8&status=open`, { waitUntil: 'domcontentloaded' });
    await waitForTendersLoaded(page);

    const count = await getResultCount(page);
    console.log(`  Direct URL Стоки: ${count} results`);
    expect(count).toBeGreaterThan(0);
    // Should be filtered (less than all open)
    expect(count).toBeLessThan(893);
  });

  test('switching categories updates results each time', async ({ page }) => {
    const results: Record<string, number> = {};

    for (const cat of ['Стоки', 'Услуги', 'Работи']) {
      await selectCategoryAndWait(page, cat);
      results[cat] = await getResultCount(page);
    }

    console.log(`  Стоки=${results['Стоки']}, Услуги=${results['Услуги']}, Работи=${results['Работи']}`);

    // All categories should return results
    expect(results['Стоки']).toBeGreaterThan(0);
    expect(results['Услуги']).toBeGreaterThan(0);
    expect(results['Работи']).toBeGreaterThan(0);

    // At least two should have different counts
    const counts = Object.values(results);
    const uniqueCounts = new Set(counts);
    expect(uniqueCounts.size).toBeGreaterThanOrEqual(2);
  });
});
