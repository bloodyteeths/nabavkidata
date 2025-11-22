/**
 * E2E tests for personalized dashboard
 * Tests dashboard features, recommendations, and personalization
 */
import { test, expect } from '@playwright/test';

test.describe('Personalized Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.fill('input[type="email"]', 'testuser@example.com');
    await page.fill('input[type="password"]', 'TestPass123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');
  });

  test('should display dashboard with key sections', async ({ page }) => {
    // Check for main dashboard sections
    await expect(page.locator('[data-testid="dashboard-header"]')).toBeVisible();
    await expect(page.locator('[data-testid="recommendations-section"]')).toBeVisible();
    await expect(page.locator('[data-testid="recent-tenders-section"]')).toBeVisible();
    await expect(page.locator('[data-testid="saved-searches-section"]')).toBeVisible();
  });

  test('should show personalized recommendations', async ({ page }) => {
    // Wait for recommendations to load
    await page.waitForSelector('[data-testid="recommendation-item"]');

    // Verify recommendations are displayed
    const recommendations = await page.locator('[data-testid="recommendation-item"]').all();
    expect(recommendations.length).toBeGreaterThan(0);

    // Check recommendation cards have required elements
    const firstRec = recommendations[0];
    await expect(firstRec.locator('[data-testid="tender-title"]')).toBeVisible();
    await expect(firstRec.locator('[data-testid="tender-budget"]')).toBeVisible();
    await expect(firstRec.locator('[data-testid="relevance-score"]')).toBeVisible();
  });

  test('should display user statistics', async ({ page }) => {
    // Check for stats widgets
    await expect(page.locator('[data-testid="stat-saved-searches"]')).toBeVisible();
    await expect(page.locator('[data-testid="stat-active-alerts"]')).toBeVisible();
    await expect(page.locator('[data-testid="stat-total-views"]')).toBeVisible();
  });

  test('should show recent activity', async ({ page }) => {
    // Check for activity feed
    await expect(page.locator('[data-testid="activity-feed"]')).toBeVisible();

    // Verify activity items
    const activities = await page.locator('[data-testid="activity-item"]').all();
    if (activities.length > 0) {
      const firstActivity = activities[0];
      await expect(firstActivity.locator('[data-testid="activity-type"]')).toBeVisible();
      await expect(firstActivity.locator('[data-testid="activity-time"]')).toBeVisible();
    }
  });

  test('should manage saved searches from dashboard', async ({ page }) => {
    // Navigate to saved searches section
    await page.click('[data-testid="view-all-searches"]');

    // Verify on saved searches page
    await expect(page.locator('h1')).toContainText('Saved Searches');

    // Create new saved search
    await page.click('[data-testid="new-saved-search"]');
    await page.fill('[data-testid="search-name"]', 'My Infrastructure Search');
    await page.fill('[data-testid="search-query"]', 'infrastructure');
    await page.click('[data-testid="save-search"]');

    // Verify search was saved
    await expect(page.locator('text=My Infrastructure Search')).toBeVisible();
  });

  test('should view and manage alerts', async ({ page }) => {
    // Navigate to alerts
    await page.click('[data-testid="view-all-alerts"]');

    // Verify on alerts page
    await expect(page.locator('h1')).toContainText('Alerts');

    // Create new alert
    await page.click('[data-testid="new-alert"]');
    await page.fill('[data-testid="alert-name"]', 'High Value Tenders');
    await page.fill('[data-testid="alert-min-budget"]', '500000');
    await page.selectOption('[data-testid="alert-frequency"]', 'daily');
    await page.click('[data-testid="save-alert"]');

    // Verify alert was created
    await expect(page.locator('text=High Value Tenders')).toBeVisible();
  });

  test('should update user preferences', async ({ page }) => {
    // Navigate to preferences
    await page.click('[data-testid="user-menu"]');
    await page.click('text=Preferences');

    // Update preferences
    await page.click('[data-testid="category-infrastructure"]');
    await page.click('[data-testid="category-technology"]');
    await page.fill('[data-testid="pref-min-budget"]', '100000');
    await page.fill('[data-testid="pref-max-budget"]', '5000000');

    // Save preferences
    await page.click('[data-testid="save-preferences"]');

    // Verify success message
    await expect(page.locator('text=Preferences updated')).toBeVisible();

    // Return to dashboard
    await page.goto('/dashboard');

    // Recommendations should reflect new preferences
    await page.waitForSelector('[data-testid="recommendation-item"]');
  });

  test('should display quick actions', async ({ page }) => {
    // Check for quick action buttons
    await expect(page.locator('[data-testid="quick-action-search"]')).toBeVisible();
    await expect(page.locator('[data-testid="quick-action-alerts"]')).toBeVisible();
    await expect(page.locator('[data-testid="quick-action-saved"]')).toBeVisible();

    // Click quick search
    await page.click('[data-testid="quick-action-search"]');

    // Should navigate to search
    await expect(page).toHaveURL(/\/tenders\/search/);
  });

  test('should show subscription status', async ({ page }) => {
    // Check for subscription widget
    await expect(page.locator('[data-testid="subscription-status"]')).toBeVisible();

    // Verify subscription details
    await expect(page.locator('[data-testid="current-plan"]')).toBeVisible();
    await expect(page.locator('[data-testid="subscription-expires"]')).toBeVisible();
  });

  test('should navigate between dashboard sections', async ({ page }) => {
    // Click on different sections
    await page.click('[data-testid="nav-overview"]');
    await expect(page.locator('[data-testid="overview-section"]')).toBeVisible();

    await page.click('[data-testid="nav-recommendations"]');
    await expect(page.locator('[data-testid="recommendations-section"]')).toBeVisible();

    await page.click('[data-testid="nav-activity"]');
    await expect(page.locator('[data-testid="activity-section"]')).toBeVisible();
  });

  test('should filter recommendations by category', async ({ page }) => {
    // Open filter dropdown
    await page.click('[data-testid="filter-recommendations"]');

    // Select category
    await page.click('[data-testid="filter-cat-construction"]');

    // Wait for filtered results
    await page.waitForTimeout(1000);

    // Verify filtered recommendations
    const recommendations = await page.locator('[data-testid="recommendation-item"]').all();
    for (const rec of recommendations) {
      const category = await rec.locator('[data-testid="tender-category"]').textContent();
      expect(category).toContain('Construction');
    }
  });

  test('should bookmark tender from recommendations', async ({ page }) => {
    // Wait for recommendations
    await page.waitForSelector('[data-testid="recommendation-item"]');

    // Click bookmark on first recommendation
    await page.click('[data-testid="bookmark-button"]:first-of-type');

    // Verify bookmark success
    await expect(page.locator('text=Tender saved')).toBeVisible();

    // Navigate to bookmarks
    await page.click('[data-testid="view-bookmarks"]');

    // Verify tender is bookmarked
    await expect(page.locator('[data-testid="bookmarked-tender"]')).toBeVisible();
  });

  test('should execute saved search from dashboard', async ({ page }) => {
    // Assume there's a saved search
    const savedSearch = page.locator('[data-testid="saved-search-item"]').first();

    if (await savedSearch.isVisible()) {
      // Click execute
      await savedSearch.locator('[data-testid="execute-search"]').click();

      // Should navigate to search results
      await expect(page).toHaveURL(/\/tenders\/search/);
      await expect(page.locator('[data-testid="search-results"]')).toBeVisible();
    }
  });

  test('should view notification center', async ({ page }) => {
    // Click notifications icon
    await page.click('[data-testid="notifications-icon"]');

    // Verify notifications panel opens
    await expect(page.locator('[data-testid="notifications-panel"]')).toBeVisible();

    // Check for notifications list
    await expect(page.locator('[data-testid="notifications-list"]')).toBeVisible();
  });

  test('should refresh dashboard data', async ({ page }) => {
    // Click refresh button
    await page.click('[data-testid="refresh-dashboard"]');

    // Wait for loading indicator
    await expect(page.locator('[data-testid="loading-indicator"]')).toBeVisible();

    // Wait for data to reload
    await page.waitForSelector('[data-testid="recommendation-item"]');

    // Verify data is displayed
    const recommendations = await page.locator('[data-testid="recommendation-item"]').all();
    expect(recommendations.length).toBeGreaterThan(0);
  });
});
