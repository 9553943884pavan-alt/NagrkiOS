// Run against a local Vite server on port 5175 with playwright-cli run-code.
// Every API response is synthetic; this test does not submit or change data.
async page => {
  await page.unrouteAll();
  const base = 'http://127.0.0.1:5175';
  const widths = [320, 375, 390, 768, 1024, 1440, 1920];
  const users = {
    citizen: {id: 1, name: 'Test Citizen', email: 'citizen@example.invalid', role: 'citizen', department: null, district: 'Prayagraj'},
    officer: {id: 2, name: 'Test Officer', email: 'officer@example.invalid', role: 'officer', department: 'Water Supply', district: 'Prayagraj'},
    admin: {id: 3, name: 'Test Admin', email: 'admin@example.invalid', role: 'admin', department: null, district: 'Prayagraj'},
  };
  const issue = {id: 7, ticket_no: 'NG-TEST-7', title: 'Water supply interrupted', description: 'Synthetic water supply issue for layout testing.', district: 'Prayagraj', category: 'Water Supply', department: 'Water Supply', priority: 'high', urgency_score: 80, confidence: .8, estimated_hours: 24, rationale: 'Synthetic rationale', language: 'en', tags: [], status: 'new', channel: 'web', citizen_id: 1, assigned_to: 2, assigned_name: 'Test Officer', attachment_path: null, attachment_description: null, created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z', due_at: '2026-11-30T00:00:00Z', resolved_at: null, requires_human_review: false, history: [], notes: []};
  const meta = {districts: ['Prayagraj'], departments: [{name: 'Water Supply', short: 'WS', color: '#287d72'}], categories: [{name: 'Water Supply', department: 'Water Supply', sla_hours: 24}], statuses: ['new', 'in_progress', 'resolved'], priorities: ['low', 'medium', 'high', 'critical'], is_demo: true, data_disclaimer: 'Synthetic test data'};
  const dashboard = {stats: {total: 1, new_count: 1, in_progress: 0, escalated: 0, resolved: 0, urgent_open: 1, overdue: 0, avg_resolution_hours: null, resolution_rate: 0, on_time_rate: 0}, by_category: [{name: 'Water Supply', value: 1}], by_department: [{name: 'Water Supply', open: 1, resolved: 0, total: 1}], by_district: [{name: 'Prayagraj', value: 1}], monthly: [{month: '2026-11', total: 1, urgent: 1}], attention: [issue], activity: []};
  let role = 'citizen';
  await page.route('**/api/**', route => {
    const path = '/api' + route.request().url().split('/api')[1].split('?')[0];
    const value = path === '/api/auth/me' ? users[role]
      : path === '/api/auth/config' ? {demo_enabled: true, registration_available: true}
      : path === '/api/auth/security' ? {mfa_enabled: false, mfa_pending: false, session_idle_minutes: 30}
      : path === '/api/meta' ? meta
      : path === '/api/citizen/overview' ? {total: 1, active: 1, resolved: 0, recent: [issue]}
      : path === '/api/officer/overview' ? {department: 'Water Supply', stats: dashboard.stats, my_cases: [issue], queue: [issue], monthly: []}
      : path === '/api/dashboard' ? dashboard
      : path === '/api/departments' ? [{name: 'Water Supply', short: 'WS', total: 1, open: 1, resolved: 0, escalated: 0, overdue: 0, avg_resolution_hours: null, resolution_rate: 0}]
      : path === '/api/insights' ? {clusters: [], category_trends: [{category: 'Water Supply', month: '2026-11', count: 1}], district_risk: [{name: 'Prayagraj', open: 1, escalated: 0, total: 1}], disclaimer: 'Synthetic test data'}
      : path === '/api/users/officers' ? [users.officer]
      : path === '/api/complaints/7' ? issue
      : path === '/api/complaints' ? {items: [issue], total: 1, page: 1, page_size: 12, pages: 1}
      : {};
    return route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(value)});
  });
  const routes = {
    citizen: ['/', '/cases', '/cases/7', '/new', '/settings'],
    officer: ['/', '/cases', '/cases/7', '/settings'],
    admin: ['/', '/cases', '/cases/7', '/new', '/insights', '/departments', '/settings'],
  };
  const results = [];
  const accessibility = [];
  for (const [kind, paths] of Object.entries(routes)) {
    role = kind;
    for (const path of paths) {
      for (const width of widths) {
        await page.setViewportSize({width, height: 900});
        await page.goto(base + path);
        await page.locator('main .page-stack').waitFor();
        await page.waitForTimeout(250);
        const result = await page.evaluate(() => ({viewport: innerWidth, document: document.documentElement.scrollWidth, main: document.querySelector('main')?.scrollWidth, body: document.body.scrollWidth}));
        results.push({role: kind, path, width, ...result});
        if (kind === 'admin' && path === '/' && width === 1440) await page.screenshot({path: 'frontend/qa-artifacts/admin-overview-1440-synthetic.png', fullPage: true});
        if (width === 390) {
          await page.addScriptTag({path: 'frontend/node_modules/axe-core/axe.min.js'});
          const violations = await page.evaluate(async () => {
            const report = await window.axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}});
            return report.violations.map(item => ({id: item.id, impact: item.impact, count: item.nodes.length, targets: item.nodes.slice(0, 3).map(node => node.target.join(' '))}));
          });
          accessibility.push({role: kind, path, violations});
        }
      }
    }
  }
  return {checked: results.length, overflow: results.filter(r => r.document > r.viewport), accessibility: accessibility.filter(r => r.violations.length)};
}
