(async () => {
  const { chromium } = await import('playwright');

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  // Navigate to ReactBits homepage
  await page.goto('https://reactbits.dev/');

  // Wait for page to load
  await page.waitForTimeout(3000);

  // Take screenshot of homepage
  await page.screenshot({ path: 'playwright-screenshots/reactbits-home.png', fullPage: true });

  console.log('Screenshot saved: playwright-screenshots/reactbits-home.png');

  await browser.close();
})();