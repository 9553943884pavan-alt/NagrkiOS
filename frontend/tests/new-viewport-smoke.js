// Start Vite with `npm run dev -- --port 5174`, then run:
// playwright-cli run-code --filename=frontend/tests/new-viewport-smoke.js
// Uses synthetic API responses; it never submits a grievance.
async page => {
  const json = value => ({status: 200, contentType: 'application/json', body: JSON.stringify(value)});
  await page.route('**/api/auth/me', route => route.fulfill(json({
    id: 77, name: 'Test Citizen', email: 'citizen@example.invalid', role: 'citizen',
    department: null, district: 'Prayagraj'
  })));
  await page.route('**/api/auth/config', route => route.fulfill(json({demo_enabled: true})));
  await page.route('**/api/meta', route => route.fulfill(json({
    districts: ['Prayagraj'], departments: [], categories: [], is_demo: true
  })));
  const widths = [320, 390, 768, 1024];
  const measurements = [];
  for (const width of widths) {
    await page.setViewportSize({width, height: 900});
    await page.goto('http://127.0.0.1:5174/new');
    await page.getByRole('heading', {name: 'Lodge a new grievance'}).waitFor();
    const result = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
      voiceRight: Math.ceil(document.querySelector('.voice-actions').getBoundingClientRect().right)
    }));
    measurements.push(result);
    if (result.document > result.viewport) throw Error(`New grievance overflows at ${width}px: ${JSON.stringify(result)}`);
  }
  return measurements;
}
