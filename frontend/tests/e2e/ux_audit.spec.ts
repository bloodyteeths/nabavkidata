/**
 * UX Audit: Simulate a user who wants to participate in tenders.
 * Tests navigation clarity, filter usability, information visibility, and mobile experience.
 * Runs against production (nabavkidata.com).
 */
import { test, expect, Page } from '@playwright/test';

const BASE = 'https://nabavkidata.com';

// Helper: take a labeled screenshot
async function snap(page: Page, name: string) {
  await page.screenshot({ path: `test-results/ux-audit-${name}.png`, fullPage: false });
}

test.describe('UX Audit — New User Journey', () => {

  test.describe.configure({ timeout: 90000 });

  test('1. Landing page → clear value proposition and CTA', async ({ page }) => {
    await page.goto(BASE);
    await page.waitForLoadState('networkidle');
    await snap(page, '01-landing');

    // Should have a visible heading or hero
    const heading = page.locator('h1').first();
    await expect(heading).toBeVisible();
    const headingText = await heading.textContent();
    console.log(`[LANDING] H1: "${headingText}"`);

    // Should have a clear CTA button (register or browse tenders)
    const ctaButtons = page.locator('a[href*="tenders"], a[href*="register"], button:has-text("тендер"), button:has-text("Регистрирај"), a:has-text("Пробај")');
    const ctaCount = await ctaButtons.count();
    console.log(`[LANDING] CTA buttons found: ${ctaCount}`);

    // Check if pricing is NOT prominently displayed (per outreach rules)
    const pricingVisible = await page.locator('text=1,990').isVisible().catch(() => false);
    console.log(`[LANDING] Pricing visible on landing: ${pricingVisible}`);
  });

  test('2. Tenders page — filters auto-apply, status tabs work', async ({ page }) => {
    await page.goto(`${BASE}/tenders`);
    await page.waitForLoadState('networkidle');
    await snap(page, '02-tenders-initial');

    // Status tabs should be visible
    const openTab = page.locator('button:has-text("Отворени")');
    const awardedTab = page.locator('button:has-text("Доделени")');
    const allTab = page.locator('button:has-text("Сите")');

    const hasOpenTab = await openTab.isVisible().catch(() => false);
    const hasAwardedTab = await awardedTab.isVisible().catch(() => false);
    const hasAllTab = await allTab.isVisible().catch(() => false);
    console.log(`[FILTERS] Status tabs visible — Open: ${hasOpenTab}, Awarded: ${hasAwardedTab}, All: ${hasAllTab}`);

    // Check "Open" tab is active by default (should have primary color)
    if (hasOpenTab) {
      const openTabClasses = await openTab.getAttribute('class') || '';
      console.log(`[FILTERS] Open tab active: ${openTabClasses.includes('bg-primary')}`);
    }

    // Get initial result count text
    const resultText = page.locator('text=/\\d+.*тендер/i').first();
    const initialText = await resultText.textContent().catch(() => 'NOT FOUND');
    console.log(`[FILTERS] Initial result text: "${initialText}"`);

    // Click "Доделени" tab — should auto-apply filter
    if (hasAwardedTab) {
      await awardedTab.click();
      await page.waitForTimeout(1500); // wait for debounce + API
      await snap(page, '02b-tenders-awarded');

      const afterText = await resultText.textContent().catch(() => 'NOT FOUND');
      console.log(`[FILTERS] After clicking Awarded: "${afterText}"`);

      // Check URL updated
      const url = page.url();
      console.log(`[FILTERS] URL after awarded click: ${url}`);
    }

    // Search box — should be prominent
    const searchBox = page.locator('input[placeholder*="Пребарај"], input[placeholder*="пребарај"], input[type="search"]').first();
    const searchVisible = await searchBox.isVisible().catch(() => false);
    console.log(`[FILTERS] Search box visible: ${searchVisible}`);

    // Type a search term and verify auto-apply
    if (searchVisible) {
      await searchBox.fill('медицинска опрема');
      await page.waitForTimeout(1500); // debounce
      await snap(page, '02c-tenders-search');

      const searchResultText = await resultText.textContent().catch(() => 'NOT FOUND');
      console.log(`[FILTERS] After search "медицинска опрема": "${searchResultText}"`);
    }

    // Check NO "Apply" button exists (should be auto-apply)
    const applyButton = page.locator('button:has-text("Примени"), button:has-text("Apply")');
    const hasApplyButton = await applyButton.isVisible().catch(() => false);
    console.log(`[FILTERS] ❌ Apply button still exists: ${hasApplyButton}`);
  });

  test('3. Tender cards — show price, winner, clean layout', async ({ page }) => {
    await page.goto(`${BASE}/tenders?status=awarded`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    await snap(page, '03-awarded-tenders');

    // Check first few tender cards
    const cards = page.locator('[class*="card"], [class*="Card"]');
    const cardCount = await cards.count();
    console.log(`[CARDS] Total cards on page: ${cardCount}`);

    // Check first card for price visibility
    for (let i = 0; i < Math.min(3, cardCount); i++) {
      const card = cards.nth(i);
      const cardText = await card.textContent() || '';

      const hasPrice = cardText.includes('МКД') || cardText.includes('MKD') || cardText.includes('Нема податок');
      const hasWinner = cardText.includes('Добитник') || cardText.includes('Trophy') || cardText.match(/winner/i);
      const hasInstitution = cardText.length > 50; // rough check that it has meaningful content

      console.log(`[CARD ${i}] Has price: ${hasPrice} | Text preview: "${cardText.substring(0, 120)}..."`);
    }

    // Check for "Нема податок" (no data) display — proves always-show-price works
    const noDataBadge = page.locator('text=Нема податок');
    const noDataCount = await noDataBadge.count();
    console.log(`[CARDS] "Нема податок" instances: ${noDataCount} (0 is fine if all have prices)`);
  });

  test('4. Tender detail page — price above fold, clear info', async ({ page }) => {
    // Go to awarded tenders and click the first one
    await page.goto(`${BASE}/tenders?status=awarded`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Click first "Детали" button
    const detailsLink = page.locator('a:has-text("Детали")').first();
    if (await detailsLink.isVisible().catch(() => false)) {
      await detailsLink.click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);
      await snap(page, '04-tender-detail');

      const url = page.url();
      console.log(`[DETAIL] Navigated to: ${url}`);

      // Check price is visible above fold (within viewport)
      const priceElement = page.locator('text=/\\d+[\\.,]\\d+.*МКД|Нема податок|Буџет|Договор/').first();
      const priceVisible = await priceElement.isVisible().catch(() => false);
      console.log(`[DETAIL] Price visible above fold: ${priceVisible}`);

      // Check key metrics strip exists
      const metricsStrip = page.locator('.flex.flex-wrap.gap-4.p-4.rounded-lg.border');
      const metricsVisible = await metricsStrip.isVisible().catch(() => false);
      console.log(`[DETAIL] Metrics strip visible: ${metricsVisible}`);

      // Check "Similar Awarded Tenders" link exists
      const similarLink = page.locator('text=Слични доделени тендери');
      const hasSimilarLink = await similarLink.isVisible().catch(() => false);
      console.log(`[DETAIL] "Similar awarded tenders" link: ${hasSimilarLink}`);

      // Check tabs exist (Детали, Документи, etc.)
      const tabsList = page.locator('[role="tablist"]');
      const hasTabsList = await tabsList.isVisible().catch(() => false);
      console.log(`[DETAIL] Tabs visible: ${hasTabsList}`);

      if (hasTabsList) {
        const tabTexts = await tabsList.textContent();
        console.log(`[DETAIL] Tab labels: "${tabTexts}"`);
      }
    } else {
      console.log('[DETAIL] No "Детали" link found — might need auth');
    }
  });

  test('5. Navigation — simple sidebar with 3 primary items', async ({ page }) => {
    await page.goto(`${BASE}/tenders`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Check sidebar exists (desktop)
    await page.setViewportSize({ width: 1280, height: 720 });
    await snap(page, '05-navigation-desktop');

    const sidebar = page.locator('aside');
    const sidebarVisible = await sidebar.isVisible().catch(() => false);
    console.log(`[NAV] Sidebar visible: ${sidebarVisible}`);

    // Count primary nav items (Главно group)
    const navLinks = sidebar.locator('a[href]');
    const navCount = await navLinks.count();
    console.log(`[NAV] Total sidebar links: ${navCount}`);

    // Log all nav item texts
    for (let i = 0; i < navCount; i++) {
      const text = await navLinks.nth(i).textContent();
      const href = await navLinks.nth(i).getAttribute('href');
      console.log(`[NAV]   ${i}: "${text?.trim()}" → ${href}`);
    }

    // Check "Повеќе" collapsible group
    const moreGroup = page.locator('button:has-text("Повеќе")');
    const hasMoreGroup = await moreGroup.isVisible().catch(() => false);
    console.log(`[NAV] "Повеќе" collapsible group: ${hasMoreGroup}`);

    // Check removed items are gone
    const produkti = page.locator('a:has-text("Производи")');
    const poraki = page.locator('a:has-text("Пораки")');
    console.log(`[NAV] ❌ "Производи" still present: ${await produkti.isVisible().catch(() => false)}`);
    console.log(`[NAV] ❌ "Пораки" still present: ${await poraki.isVisible().catch(() => false)}`);
  });

  test('6. Mobile experience — responsive layout, no overflow', async ({ page }) => {
    // iPhone viewport
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`${BASE}/tenders`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    await snap(page, '06-mobile-tenders');

    // Sidebar should be hidden, hamburger visible
    const sidebar = page.locator('aside');
    const sidebarHidden = !(await sidebar.isVisible().catch(() => true));
    console.log(`[MOBILE] Sidebar hidden: ${sidebarHidden}`);

    const hamburger = page.locator('button:has(svg.lucide-menu), button:has(svg)').first();
    console.log(`[MOBILE] Hamburger button exists: ${await hamburger.isVisible().catch(() => false)}`);

    // Check no horizontal overflow
    const hasOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    console.log(`[MOBILE] ❌ Horizontal overflow: ${hasOverflow}`);

    // Status tabs should still be visible
    const tabs = page.locator('button:has-text("Отворени")');
    console.log(`[MOBILE] Status tabs visible: ${await tabs.isVisible().catch(() => false)}`);

    // Search box should be visible
    const search = page.locator('input[placeholder*="Пребарај"], input[placeholder*="пребарај"]').first();
    console.log(`[MOBILE] Search visible: ${await search.isVisible().catch(() => false)}`);

    // Tender cards should be readable
    const cards = page.locator('[class*="card"]');
    const mobileCardCount = await cards.count();
    console.log(`[MOBILE] Cards rendered: ${mobileCardCount}`);

    await snap(page, '06b-mobile-scroll');
  });

  test('7. User flow: "I sell medical supplies, find me open tenders"', async ({ page }) => {
    console.log('\n=== USER STORY: Medical supplies vendor looking for tenders ===\n');

    // Step 1: Land on tenders page
    await page.goto(`${BASE}/tenders`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Step 2: Should see open tenders by default
    const openTab = page.locator('button:has-text("Отворени")');
    if (await openTab.isVisible().catch(() => false)) {
      const classes = await openTab.getAttribute('class') || '';
      console.log(`[STORY] Step 1: Open tenders tab active: ${classes.includes('primary')}`);
    }

    // Step 3: Search for medical supplies
    const searchBox = page.locator('input[placeholder*="Пребарај"], input[placeholder*="пребарај"]').first();
    if (await searchBox.isVisible()) {
      await searchBox.fill('медицински материјали');
      await page.waitForTimeout(2000); // debounce + API
      await snap(page, '07a-medical-search');

      // Check results appeared
      const resultCount = page.locator('text=/\\d+.*тендер|резултат/i').first();
      const countText = await resultCount.textContent().catch(() => 'NOT FOUND');
      console.log(`[STORY] Step 2: Search results: "${countText}"`);
    }

    // Step 4: Check if category filter helps narrow down
    const categoryFilter = page.locator('button:has-text("Стоки"), select:has-text("Стоки"), [role="combobox"]').first();
    const hasCategoryFilter = await categoryFilter.isVisible().catch(() => false);
    console.log(`[STORY] Step 3: Category filter visible: ${hasCategoryFilter}`);

    // Step 5: Click first result
    const firstDetail = page.locator('a:has-text("Детали")').first();
    if (await firstDetail.isVisible().catch(() => false)) {
      await firstDetail.click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);
      await snap(page, '07b-medical-detail');

      // Check we can see price + deadline
      const pageText = await page.textContent('body') || '';
      console.log(`[STORY] Step 4: Detail page has price: ${pageText.includes('МКД') || pageText.includes('Нема податок')}`);
      console.log(`[STORY] Step 4: Detail page has deadline: ${pageText.includes('Краен рок') || pageText.includes('рок')}`);
      console.log(`[STORY] Step 4: Detail page has institution: ${pageText.includes('Институција') || pageText.includes('институциј')}`);

      // Check documents tab
      const docsTab = page.locator('button:has-text("Документи"), [role="tab"]:has-text("Документи")');
      if (await docsTab.isVisible().catch(() => false)) {
        await docsTab.click();
        await page.waitForTimeout(1500);
        await snap(page, '07c-medical-documents');
        console.log(`[STORY] Step 5: Documents tab accessible`);
      }

      // Can we go back easily?
      const backButton = page.locator('a:has-text("Назад"), button:has-text("Назад"), a[href="/tenders"]').first();
      console.log(`[STORY] Step 6: Back button visible: ${await backButton.isVisible().catch(() => false)}`);
    }

    console.log('\n=== END USER STORY ===\n');
  });

  test('8. Alerts page — can user set up tender alerts?', async ({ page }) => {
    await page.goto(`${BASE}/alerts`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
    await snap(page, '08-alerts-page');

    const pageText = await page.textContent('body') || '';
    // Check if alerts page loads (may require auth)
    const hasAlertContent = pageText.includes('Алерт') || pageText.includes('alert') || pageText.includes('Нотификации');
    const requiresLogin = pageText.includes('Најави') || pageText.includes('логирај') || pageText.includes('login');
    console.log(`[ALERTS] Page has alert content: ${hasAlertContent}`);
    console.log(`[ALERTS] Requires login: ${requiresLogin}`);
  });

  test('9. Overall page load speed', async ({ page }) => {
    const pages = [
      { name: 'Landing', url: BASE },
      { name: 'Tenders', url: `${BASE}/tenders` },
      { name: 'Alerts', url: `${BASE}/alerts` },
    ];

    for (const p of pages) {
      const start = Date.now();
      await page.goto(p.url);
      await page.waitForLoadState('networkidle');
      const elapsed = Date.now() - start;
      console.log(`[PERF] ${p.name}: ${elapsed}ms`);
    }
  });

  test('10. Accessibility quick check', async ({ page }) => {
    await page.goto(`${BASE}/tenders`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Check for alt text on images
    const images = page.locator('img');
    const imgCount = await images.count();
    let missingAlt = 0;
    for (let i = 0; i < imgCount; i++) {
      const alt = await images.nth(i).getAttribute('alt');
      if (!alt) missingAlt++;
    }
    console.log(`[A11Y] Images: ${imgCount}, Missing alt: ${missingAlt}`);

    // Check for proper heading hierarchy
    const h1Count = await page.locator('h1').count();
    const h2Count = await page.locator('h2').count();
    console.log(`[A11Y] H1 count: ${h1Count}, H2 count: ${h2Count}`);

    // Check buttons have accessible text
    const buttons = page.locator('button');
    const btnCount = await buttons.count();
    let emptyButtons = 0;
    for (let i = 0; i < Math.min(btnCount, 20); i++) {
      const text = await buttons.nth(i).textContent();
      const ariaLabel = await buttons.nth(i).getAttribute('aria-label');
      if (!text?.trim() && !ariaLabel) emptyButtons++;
    }
    console.log(`[A11Y] Buttons: ${btnCount}, Without accessible text: ${emptyButtons}`);

    // Check contrast: is body text readable?
    const bodyFontSize = await page.evaluate(() => {
      const el = document.querySelector('body');
      return el ? getComputedStyle(el).fontSize : 'unknown';
    });
    console.log(`[A11Y] Body font size: ${bodyFontSize}`);
  });
});
