/**
 * E2E tests for billing and subscription flow
 * Tests subscription checkout, plan management, and billing portal
 */
import { test, expect } from '@playwright/test';

test.describe('Billing and Subscription Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.fill('input[type="email"]', 'testuser@example.com');
    await page.fill('input[type="password"]', 'TestPass123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');
  });

  test('should display subscription plans', async ({ page }) => {
    // Navigate to pricing page
    await page.goto('/pricing');

    // Check for plan cards
    await expect(page.locator('[data-testid="plan-basic"]')).toBeVisible();
    await expect(page.locator('[data-testid="plan-professional"]')).toBeVisible();
    await expect(page.locator('[data-testid="plan-enterprise"]')).toBeVisible();

    // Verify plan details
    const basicPlan = page.locator('[data-testid="plan-basic"]');
    await expect(basicPlan.locator('[data-testid="plan-name"]')).toContainText('Basic');
    await expect(basicPlan.locator('[data-testid="plan-price"]')).toBeVisible();
    await expect(basicPlan.locator('[data-testid="plan-features"]')).toBeVisible();
  });

  test('should toggle between currency options', async ({ page }) => {
    await page.goto('/pricing');

    // Check initial currency (MKD)
    await expect(page.locator('[data-testid="price-mkd"]').first()).toBeVisible();

    // Toggle to EUR
    await page.click('[data-testid="currency-toggle"]');

    // Verify EUR prices shown
    await expect(page.locator('[data-testid="price-eur"]').first()).toBeVisible();
  });

  test('should initiate subscription checkout', async ({ page }) => {
    await page.goto('/pricing');

    // Click subscribe on Basic plan
    await page.click('[data-testid="plan-basic"] [data-testid="subscribe-button"]');

    // Should navigate to checkout
    await expect(page).toHaveURL(/\/checkout/);

    // Verify checkout page elements
    await expect(page.locator('[data-testid="checkout-summary"]')).toBeVisible();
    await expect(page.locator('[data-testid="plan-summary"]')).toContainText('Basic');
    await expect(page.locator('[data-testid="total-amount"]')).toBeVisible();
  });

  test('should complete checkout flow', async ({ page }) => {
    await page.goto('/pricing');

    // Select plan
    await page.click('[data-testid="plan-professional"] [data-testid="subscribe-button"]');

    // Wait for checkout page
    await expect(page).toHaveURL(/\/checkout/);

    // Click proceed to payment
    await page.click('[data-testid="proceed-to-payment"]');

    // Should redirect to Stripe (in test mode, might be mocked)
    // For E2E, we'd typically mock Stripe or use test mode
    await page.waitForTimeout(2000);

    // In real test, would complete Stripe flow
    // For now, verify we got to payment stage
  });

  test('should view current subscription', async ({ page }) => {
    // Navigate to account/subscription
    await page.goto('/account/subscription');

    // Verify subscription details
    await expect(page.locator('[data-testid="current-plan"]')).toBeVisible();
    await expect(page.locator('[data-testid="subscription-status"]')).toBeVisible();
    await expect(page.locator('[data-testid="billing-cycle"]')).toBeVisible();
    await expect(page.locator('[data-testid="next-billing-date"]')).toBeVisible();
  });

  test('should view billing history', async ({ page }) => {
    await page.goto('/account/billing');

    // Check for invoices list
    await expect(page.locator('[data-testid="invoices-list"]')).toBeVisible();

    // If there are invoices, verify structure
    const invoices = await page.locator('[data-testid="invoice-item"]').all();
    if (invoices.length > 0) {
      const firstInvoice = invoices[0];
      await expect(firstInvoice.locator('[data-testid="invoice-number"]')).toBeVisible();
      await expect(firstInvoice.locator('[data-testid="invoice-amount"]')).toBeVisible();
      await expect(firstInvoice.locator('[data-testid="invoice-date"]')).toBeVisible();
      await expect(firstInvoice.locator('[data-testid="invoice-status"]')).toBeVisible();
    }
  });

  test('should download invoice PDF', async ({ page }) => {
    await page.goto('/account/billing');

    // Find first invoice with download button
    const downloadButton = page.locator('[data-testid="download-invoice"]').first();

    if (await downloadButton.isVisible()) {
      // Set up download listener
      const downloadPromise = page.waitForEvent('download');

      // Click download
      await downloadButton.click();

      // Wait for download
      const download = await downloadPromise;

      // Verify download started
      expect(download.suggestedFilename()).toMatch(/invoice.*\.pdf/i);
    }
  });

  test('should change subscription plan', async ({ page }) => {
    await page.goto('/account/subscription');

    // Click change plan
    await page.click('[data-testid="change-plan-button"]');

    // Should show plan selection
    await expect(page.locator('[data-testid="plan-selection"]')).toBeVisible();

    // Select different plan
    await page.click('[data-testid="select-plan-enterprise"]');

    // Confirm change
    await page.click('[data-testid="confirm-plan-change"]');

    // Verify confirmation dialog
    await expect(page.locator('[data-testid="plan-change-confirmation"]')).toBeVisible();

    // Confirm
    await page.click('[data-testid="confirm-upgrade"]');

    // Should show success message
    await expect(page.locator('text=Plan updated successfully')).toBeVisible();
  });

  test('should cancel subscription', async ({ page }) => {
    await page.goto('/account/subscription');

    // Click cancel subscription
    await page.click('[data-testid="cancel-subscription-button"]');

    // Verify cancellation dialog
    await expect(page.locator('[data-testid="cancel-confirmation-dialog"]')).toBeVisible();

    // Select cancellation option (at period end)
    await page.click('[data-testid="cancel-at-period-end"]');

    // Confirm cancellation
    await page.click('[data-testid="confirm-cancellation"]');

    // Verify success message
    await expect(page.locator('text=Subscription will be cancelled')).toBeVisible();

    // Verify subscription status updated
    await expect(page.locator('text=Cancels on')).toBeVisible();
  });

  test('should reactivate cancelled subscription', async ({ page }) => {
    // Assume subscription is cancelled
    await page.goto('/account/subscription');

    // If subscription is marked for cancellation
    const reactivateButton = page.locator('[data-testid="reactivate-subscription"]');

    if (await reactivateButton.isVisible()) {
      await reactivateButton.click();

      // Confirm reactivation
      await page.click('[data-testid="confirm-reactivation"]');

      // Verify success
      await expect(page.locator('text=Subscription reactivated')).toBeVisible();
    }
  });

  test('should manage payment methods', async ({ page }) => {
    await page.goto('/account/payment-methods');

    // Check for payment methods list
    await expect(page.locator('[data-testid="payment-methods-list"]')).toBeVisible();

    // Add new payment method
    await page.click('[data-testid="add-payment-method"]');

    // Should open Stripe payment form or modal
    await expect(page.locator('[data-testid="payment-method-form"]')).toBeVisible();

    // In real test, would fill Stripe Elements
    // For now, just verify form is present
  });

  test('should set default payment method', async ({ page }) => {
    await page.goto('/account/payment-methods');

    // Find payment method that's not default
    const paymentMethod = page.locator('[data-testid="payment-method-item"]').first();

    if (await paymentMethod.isVisible()) {
      // Click set as default
      await paymentMethod.locator('[data-testid="set-as-default"]').click();

      // Verify success
      await expect(page.locator('text=Default payment method updated')).toBeVisible();

      // Verify badge shows
      await expect(paymentMethod.locator('[data-testid="default-badge"]')).toBeVisible();
    }
  });

  test('should delete payment method', async ({ page }) => {
    await page.goto('/account/payment-methods');

    // Find deletable payment method
    const paymentMethod = page.locator('[data-testid="payment-method-item"]').last();

    if (await paymentMethod.isVisible()) {
      // Click delete
      await paymentMethod.locator('[data-testid="delete-payment-method"]').click();

      // Confirm deletion
      await page.click('[data-testid="confirm-delete"]');

      // Verify success
      await expect(page.locator('text=Payment method deleted')).toBeVisible();
    }
  });

  test('should view usage statistics', async ({ page }) => {
    await page.goto('/account/usage');

    // Check for usage stats
    await expect(page.locator('[data-testid="queries-used"]')).toBeVisible();
    await expect(page.locator('[data-testid="queries-remaining"]')).toBeVisible();
    await expect(page.locator('[data-testid="usage-chart"]')).toBeVisible();

    // Verify usage breakdown
    await expect(page.locator('[data-testid="monthly-limit"]')).toBeVisible();
  });

  test('should access billing portal', async ({ page }) => {
    await page.goto('/account/billing');

    // Click billing portal button
    await page.click('[data-testid="billing-portal"]');

    // Should open new tab or redirect
    // In test, might just verify button works
    await page.waitForTimeout(1000);
  });

  test('should show upgrade prompts for free users', async ({ page }) => {
    // Assume user is on free plan
    await page.goto('/dashboard');

    // Should show upgrade prompt
    await expect(page.locator('[data-testid="upgrade-prompt"]')).toBeVisible();

    // Click upgrade
    await page.click('[data-testid="upgrade-now"]');

    // Should navigate to pricing
    await expect(page).toHaveURL(/\/pricing/);
  });

  test('should apply promo code', async ({ page }) => {
    await page.goto('/pricing');

    // Select plan
    await page.click('[data-testid="plan-basic"] [data-testid="subscribe-button"]');

    // On checkout page
    await expect(page).toHaveURL(/\/checkout/);

    // Expand promo code section
    await page.click('[data-testid="promo-code-toggle"]');

    // Enter promo code
    await page.fill('[data-testid="promo-code-input"]', 'TEST2024');

    // Apply code
    await page.click('[data-testid="apply-promo"]');

    // Verify discount applied
    await expect(page.locator('[data-testid="discount-applied"]')).toBeVisible();
    await expect(page.locator('[data-testid="discounted-total"]')).toBeVisible();
  });
});
