/**
 * E2E tests for authentication flow
 * Tests login, registration, logout, and password reset
 */
import { test, expect, Page } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to home page before each test
    await page.goto('/');
  });

  test('should display login page', async ({ page }) => {
    await page.goto('/login');

    // Check for login form elements
    await expect(page.locator('h1')).toContainText('Login');
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('should successfully login with valid credentials', async ({ page }) => {
    await page.goto('/login');

    // Fill in login form
    await page.fill('input[type="email"]', 'testuser@example.com');
    await page.fill('input[type="password"]', 'TestPass123!');

    // Submit form
    await page.click('button[type="submit"]');

    // Wait for navigation to dashboard
    await page.waitForURL('/dashboard');

    // Verify user is logged in
    await expect(page.locator('[data-testid="user-menu"]')).toBeVisible();
    await expect(page.locator('text=Welcome')).toBeVisible();
  });

  test('should show error with invalid credentials', async ({ page }) => {
    await page.goto('/login');

    // Fill in with wrong credentials
    await page.fill('input[type="email"]', 'wrong@example.com');
    await page.fill('input[type="password"]', 'WrongPassword123!');

    // Submit form
    await page.click('button[type="submit"]');

    // Check for error message
    await expect(page.locator('[role="alert"]')).toContainText('Invalid credentials');
  });

  test('should successfully register new user', async ({ page }) => {
    await page.goto('/register');

    // Fill in registration form
    const timestamp = Date.now();
    await page.fill('input[name="fullName"]', 'Test User');
    await page.fill('input[name="email"]', `testuser${timestamp}@example.com`);
    await page.fill('input[name="password"]', 'TestPass123!');
    await page.fill('input[name="confirmPassword"]', 'TestPass123!');

    // Accept terms
    await page.check('input[name="terms"]');

    // Submit form
    await page.click('button[type="submit"]');

    // Verify success message
    await expect(page.locator('text=Registration successful')).toBeVisible();
    await expect(page.locator('text=Check your email')).toBeVisible();
  });

  test('should validate registration form fields', async ({ page }) => {
    await page.goto('/register');

    // Try to submit empty form
    await page.click('button[type="submit"]');

    // Check for validation errors
    await expect(page.locator('text=Email is required')).toBeVisible();
    await expect(page.locator('text=Password is required')).toBeVisible();
  });

  test('should validate password strength', async ({ page }) => {
    await page.goto('/register');

    // Fill in weak password
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'weak');
    await page.fill('input[name="confirmPassword"]', 'weak');

    await page.click('button[type="submit"]');

    // Check for password strength error
    await expect(page.locator('text=Password must be at least 8 characters')).toBeVisible();
  });

  test('should validate password confirmation', async ({ page }) => {
    await page.goto('/register');

    // Fill in mismatched passwords
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'TestPass123!');
    await page.fill('input[name="confirmPassword"]', 'DifferentPass123!');

    await page.click('button[type="submit"]');

    // Check for mismatch error
    await expect(page.locator('text=Passwords do not match')).toBeVisible();
  });

  test('should successfully logout', async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.fill('input[type="email"]', 'testuser@example.com');
    await page.fill('input[type="password"]', 'TestPass123!');
    await page.click('button[type="submit"]');

    // Wait for dashboard
    await page.waitForURL('/dashboard');

    // Click user menu
    await page.click('[data-testid="user-menu"]');

    // Click logout
    await page.click('text=Logout');

    // Verify redirected to home/login
    await page.waitForURL('/');

    // Verify user menu is not visible
    await expect(page.locator('[data-testid="user-menu"]')).not.toBeVisible();
  });

  test('should handle password reset flow', async ({ page }) => {
    await page.goto('/forgot-password');

    // Fill in email
    await page.fill('input[type="email"]', 'testuser@example.com');

    // Submit form
    await page.click('button[type="submit"]');

    // Verify success message
    await expect(page.locator('text=Password reset email sent')).toBeVisible();
  });

  test('should redirect unauthenticated users to login', async ({ page }) => {
    // Try to access protected page
    await page.goto('/dashboard');

    // Should redirect to login
    await page.waitForURL('/login');
  });

  test('should persist login after page reload', async ({ page, context }) => {
    // Login
    await page.goto('/login');
    await page.fill('input[type="email"]', 'testuser@example.com');
    await page.fill('input[type="password"]', 'TestPass123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');

    // Reload page
    await page.reload();

    // Should still be logged in
    await expect(page.locator('[data-testid="user-menu"]')).toBeVisible();
  });

  test('should handle session expiration', async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('input[type="email"]', 'testuser@example.com');
    await page.fill('input[type="password"]', 'TestPass123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');

    // Clear storage to simulate token expiration
    await page.context().clearCookies();
    await page.evaluate(() => localStorage.clear());

    // Try to access protected page
    await page.goto('/dashboard');

    // Should redirect to login
    await page.waitForURL('/login');
  });
});
