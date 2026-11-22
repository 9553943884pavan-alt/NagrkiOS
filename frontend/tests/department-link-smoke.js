// Run against the local Vite server on port 5175 with playwright-cli run-code.
// Synthetic administrator and department data only.
async page => {
  await page.unrouteAll();
  const json = value => ({status: 200, contentType: 'application/json', body: JSON.stringify(value)});
  await page.route('**/api/auth/me', route => route.fulfill(json({id: 3, name: 'Test Admin', email: 'admin@example.invalid', role: 'admin', department: null, district: 'Prayagraj'})));
  await page.route('**/api/auth/config', route => route.fulfill(json({demo_enabled: true})));
  await page.route('**/api/departments', route => route.fulfill(json([{name: 'Water Supply', short: 'WS', total: 1, open: 1, resolved: 0, escalated: 0, overdue: 0, avg_resolution_hours: null, resolution_rate: 0}])));
  await page.route('**/api/meta', route => route.fulfill(json({districts: ['Prayagraj'], departments: [{name: 'Water Supply'}], categories: [], statuses: [], priorities: [], is_demo: true, data_disclaimer: ''})));
  await page.route('**/api/complaints?*', route => route.fulfill(json({items: [], total: 0, page: 1, page_size: 12, pages: 1})));
  await page.goto('http://127.0.0.1:5175/departments');
  const search = page.getByRole('textbox', {name: 'Find a department'});
  await search.waitFor();
  const link = page.getByRole('link', {name: 'View Water Supply grievances'});
  await link.focus();
  await page.keyboard.press('Enter');
  await page.waitForURL('**/cases?department=Water%20Supply');
  return {searchNamed: true, nativeLinkKeyboardNavigation: true};
}
