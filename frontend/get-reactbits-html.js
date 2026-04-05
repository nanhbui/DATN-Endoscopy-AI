(async () => {
  const { chromium } = await import('playwright');
  const { writeFileSync } = await import('node:fs');

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('https://reactbits.dev/', { waitUntil: 'networkidle' });
  const html = await page.content();
  writeFileSync('reactbits-home.html', html);
  console.log('HTML saved');
  await browser.close();
})();
