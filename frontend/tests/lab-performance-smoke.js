// Run against a local Vite preview on port 4175 with playwright-cli run-code.
// Single synthetic Chromium lab sample; not field Core Web Vitals data.
async page => {
  await page.unrouteAll();
  const json = value => ({status: 200, contentType: 'application/json', body: JSON.stringify(value)});
  await page.route('**/api/auth/me', route => route.fulfill(json({id: 3, name: 'Test Admin', email: 'admin@example.invalid', role: 'admin', department: null, district: 'Prayagraj'})));
  await page.route('**/api/auth/config', route => route.fulfill(json({demo_enabled: false})));
  await page.route('**/api/dashboard', route => route.fulfill(json({
    stats: {total: 1, new_count: 1, in_progress: 0, escalated: 0, resolved: 0, urgent_open: 1, overdue: 0, avg_resolution_hours: null, resolution_rate: 0, on_time_rate: 0},
    by_category: [{name: 'Water Supply', value: 1}], by_department: [{name: 'Water Supply', open: 1, resolved: 0, total: 1}], by_district: [{name: 'Prayagraj', value: 1}],
    monthly: [{month: '2026-11', total: 1, urgent: 1}], attention: [], activity: [],
  })));
  await page.setViewportSize({width: 1440, height: 900});
  await page.addInitScript(() => {
    window.__lab = {lcp: 0, cls: 0};
    new PerformanceObserver(list => {for (const item of list.getEntries()) window.__lab.lcp = item.startTime;}).observe({type: 'largest-contentful-paint', buffered: true});
    new PerformanceObserver(list => {for (const item of list.getEntries()) if (!item.hadRecentInput) window.__lab.cls += item.value;}).observe({type: 'layout-shift', buffered: true});
  });
  await page.goto('http://127.0.0.1:4175/');
  await page.locator('main .page-stack').waitFor();
  await page.waitForTimeout(1500);
  return await page.evaluate(() => ({
    fcpMs: Math.round(performance.getEntriesByType('paint').find(item => item.name === 'first-contentful-paint')?.startTime || 0),
    lcpMs: Math.round(window.__lab.lcp),
    cls: Number(window.__lab.cls.toFixed(4)),
    route: location.pathname,
    viewport: innerWidth,
  }));
}
