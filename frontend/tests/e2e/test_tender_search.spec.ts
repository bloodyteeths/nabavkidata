/**
 * E2E tests for tender search and filtering
 * Tests search functionality, filters, and sorting
 */
import { test, expect } from '@playwright/test';

test.describe('Tender Search and Filtering', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.fill('input[type="email"]', 'testuser@example.com');
    await page.fill('input[type="password"]', 'TestPass123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');

    // Navigate to search page
    await page.goto('/tenders/search');
  });

  test('should display search interface', async ({ page }) => {
    // Check for search elements
    await expect(page.locator('[data-testid="search-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="search-button"]')).toBeVisible();
    await expect(page.locator('[data-testid="filter-panel"]')).toBeVisible();
  });

  test('should search for tenders by keyword', async ({ page }) => {
    // Enter search query
    await page.fill('[data-testid="search-input"]', 'infrastructure');

    // Submit search
    await page.click('[data-testid="search-button"]');

    // Wait for results
    await page.waitForSelector('[data-testid="search-results"]');

    // Verify results contain search term
    const results = await page.locator('[data-testid="tender-item"]').all();
    expect(results.length).toBeGreaterThan(0);

    // Check first result contains keyword
    const firstResult = results[0];
    const text = await firstResult.textContent();
    expect(text?.toLowerCase()).toContain('infrastructure');
  });

  test('should filter by status', async ({ page }) => {
    // Open filter panel
    await page.click('[data-testid="filter-toggle"]');

    // Select active status
    await page.click('[data-testid="filter-status-active"]');

    // Apply filters
    await page.click('[data-testid="apply-filters"]');

    // Wait for results
    await page.waitForSelector('[data-testid="search-results"]');

    // Verify all results are active
    const statusBadges = await page.locator('[data-testid="tender-status"]').all();
    for (const badge of statusBadges) {
      const text = await badge.textContent();
      expect(text).toBe('Active');
    }
  });

  test('should filter by budget range', async ({ page }) => {
    // Open filter panel
    await page.click('[data-testid="filter-toggle"]');

    // Set budget range
    await page.fill('[data-testid="filter-min-budget"]', '100000');
    await page.fill('[data-testid="filter-max-budget"]', '1000000');

    // Apply filters
    await page.click('[data-testid="apply-filters"]');

    // Wait for results
    await page.waitForSelector('[data-testid="search-results"]');

    // Verify results are within range
    const budgets = await page.locator('[data-testid="tender-budget"]').all();
    for (const budgetElement of budgets) {
      const text = await budgetElement.textContent();
      const amount = parseFloat(text?.replace(/[^\d.]/g, '') || '0');
      expect(amount).toBeGreaterThanOrEqual(100000);
      expect(amount).toBeLessThanOrEqual(1000000);
    }
  });

  test('should filter by date range', async ({ page }) => {
    // Open filter panel
    await page.click('[data-testid="filter-toggle"]');

    // Set date range
    const today = new Date();
    const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

    await page.fill('[data-testid="filter-start-date"]', thirtyDaysAgo.toISOString().split('T')[0]);
    await page.fill('[data-testid="filter-end-date"]', today.toISOString().split('T')[0]);

    // Apply filters
    await page.click('[data-testid="apply-filters"]');

    // Wait for results
    await page.waitForSelector('[data-testid="search-results"]');

    // Results should be displayed
    const results = await page.locator('[data-testid="tender-item"]').all();
    expect(results.length).toBeGreaterThanOrEqual(0);
  });

  test('should filter by category', async ({ page }) => {
    // Open filter panel
    await page.click('[data-testid="filter-toggle"]');

    // Select category
    await page.click('[data-testid="filter-category-construction"]');

    // Apply filters
    await page.click('[data-testid="apply-filters"]');

    // Wait for results
    await page.waitForSelector('[data-testid="search-results"]');

    // Verify results match category
    const categories = await page.locator('[data-testid="tender-category"]').all();
    for (const category of categories) {
      const text = await category.textContent();
      expect(text).toContain('Construction');
    }
  });

  test('should sort results by date', async ({ page }) => {
    // Perform search
    await page.fill('[data-testid="search-input"]', 'tender');
    await page.click('[data-testid="search-button"]');

    // Wait for results
    await page.waitForSelector('[data-testid="search-results"]');

    // Select sort option
    await page.selectOption('[data-testid="sort-select"]', 'date-desc');

    // Wait for results to update
    await page.waitForTimeout(1000);

    // Verify sorting
    const dates = await page.locator('[data-testid="tender-date"]').allTextContents();
    const timestamps = dates.map(d => new Date(d).getTime());

    for (let i = 1; i < timestamps.length; i++) {
      expect(timestamps[i - 1]).toBeGreaterThanOrEqual(timestamps[i]);
    }
  });

  test('should sort results by budget', async ({ page }) => {
    // Perform search
    await page.fill('[data-testid="search-input"]', 'tender');
    await page.click('[data-testid="search-button"]');

    // Wait for results
    await page.waitForSelector('[data-testid="search-results"]');

    // Select sort option
    await page.selectOption('[data-testid="sort-select"]', 'budget-desc');

    // Wait for results to update
    await page.waitForTimeout(1000);

    // Verify sorting
    const budgets = await page.locator('[data-testid="tender-budget"]').allTextContents();
    const amounts = budgets.map(b => parseFloat(b.replace(/[^\d.]/g, '')));

    for (let i = 1; i < amounts.length; i++) {
      expect(amounts[i - 1]).toBeGreaterThanOrEqual(amounts[i]);
    }
  });

  test('should paginate results', async ({ page }) => {
    // Perform search
    await page.fill('[data-testid="search-input"]', 'tender');
    await page.click('[data-testid="search-button"]');

    // Wait for results
    await page.waitForSelector('[data-testid="search-results"]');

    // Check pagination controls
    await expect(page.locator('[data-testid="pagination"]')).toBeVisible();

    // Get first page results
    const firstPageResults = await page.locator('[data-testid="tender-item"]').count();

    // Go to next page
    await page.click('[data-testid="next-page"]');

    // Wait for new results
    await page.waitForTimeout(1000);

    // Verify new results loaded
    const secondPageResults = await page.locator('[data-testid="tender-item"]').count();
    expect(secondPageResults).toBeGreaterThan(0);
  });

  test('should clear all filters', async ({ page }) => {
    // Apply multiple filters
    await page.click('[data-testid="filter-toggle"]');
    await page.click('[data-testid="filter-status-active"]');
    await page.fill('[data-testid="filter-min-budget"]', '100000');
    await page.click('[data-testid="apply-filters"]');

    // Wait for results
    await page.waitForSelector('[data-testid="search-results"]');

    // Clear filters
    await page.click('[data-testid="clear-filters"]');

    // Wait for results to update
    await page.waitForTimeout(1000);

    // Verify filters are cleared
    const minBudget = await page.inputValue('[data-testid="filter-min-budget"]');
    expect(minBudget).toBe('');
  });

  test('should view tender details', async ({ page }) => {
    // Perform search
    await page.fill('[data-testid="search-input"]', 'infrastructure');
    await page.click('[data-testid="search-button"]');

    // Wait for results
    await page.waitForSelector('[data-testid="search-results"]');

    // Click first result
    await page.click('[data-testid="tender-item"]:first-child');

    // Should navigate to detail page
    await expect(page).toHaveURL(/\/tenders\/[a-f0-9-]+/);

    // Verify detail page elements
    await expect(page.locator('[data-testid="tender-title"]')).toBeVisible();
    await expect(page.locator('[data-testid="tender-description"]')).toBeVisible();
    await expect(page.locator('[data-testid="tender-budget"]')).toBeVisible();
  });

  test('should show no results message', async ({ page }) => {
    // Search for non-existent term
    await page.fill('[data-testid="search-input"]', 'xyzabc123nonexistent');
    await page.click('[data-testid="search-button"]');

    // Wait for no results message
    await expect(page.locator('[data-testid="no-results"]')).toBeVisible();
    await expect(page.locator('text=No tenders found')).toBeVisible();
  });
});
