// Run against the local Vite server with:
// playwright-cli run-code --filename=frontend/tests/cases-smoke.js
// All account and case data here is synthetic; no backend is contacted.
async page => {
  const json = body => ({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
  const user = {id: 7, name: 'Test Officer', email: 'officer@example.invalid', role: 'officer', department: 'Water', district: 'Prayagraj'};
  const complaint = {id: 1, ticket_no: 'NG-TEST-1', title: 'Water supply interrupted', category: 'Water', department: 'Water', district: 'Prayagraj', priority: 'critical', status: 'new', created_at: '2026-11-01T00:00:00Z'};
  let slowRequests = 0;
  let fastRequests = 0;
  await page.route('**/api/auth/me', route => route.fulfill(json(user)));
  await page.route('**/api/auth/config', route => route.fulfill(json({demo_enabled: false})));
  await page.route('**/api/meta', route => route.fulfill(json({districts: ['Prayagraj'], departments: [], categories: [], statuses: [], priorities: [], is_demo: false, data_disclaimer: ''})));
  await page.route('**/api/complaints?*', async route => {
    const requestUrl = route.request().url();
    if (requestUrl.includes('search=slow')) { slowRequests++; await page.waitForTimeout(350); }
    if (requestUrl.includes('search=fast')) fastRequests++;
    const item = requestUrl.includes('search=slow') ? {...complaint, ticket_no: 'NG-SLOW'}
      : requestUrl.includes('search=fast') ? {...complaint, ticket_no: 'NG-FAST'} : complaint;
    await route.fulfill(json({items: [item], total: 1, page: 1, page_size: 12, pages: 1}));
  });

  await page.goto('http://127.0.0.1:5173/cases?priority=critical&search=water');
  await page.getByRole('button', {name: 'All cases'}).waitFor();
  if (await page.getByRole('button', {name: 'New grievance'}).count() !== 0) throw Error('Officer sees a grievance action that redirects home');
  const caseLink = page.getByRole('link', {name: 'Open NG-TEST-1: Water supply interrupted'});
  await caseLink.waitFor();
  const search = page.getByRole('textbox', {name: 'Search tickets'});
  await search.fill('slow');
  await page.getByRole('button', {name: 'Search', exact: true}).click();
  await search.fill('fast');
  await page.getByRole('button', {name: 'Search', exact: true}).click();
  await page.getByRole('link', {name: 'Open NG-FAST: Water supply interrupted'}).waitFor();
  await page.waitForTimeout(450);
  if (!slowRequests || !fastRequests) throw Error('Both search requests were not observed');
  if (await page.getByRole('link', {name: 'Open NG-SLOW: Water supply interrupted'}).count() !== 0) throw Error('Stale search response replaced the latest result');
  await page.getByRole('button', {name: 'All cases'}).click();
  if (await page.evaluate(() => location.search) !== '') throw Error('All cases did not clear every filter');
  await caseLink.waitFor();
  await caseLink.focus();
  await page.keyboard.press('Enter');
  await page.waitForURL('**/cases/1');
  return {officerActionHidden: true, allFiltersCleared: true, staleResponseIgnored: true, keyboardLinkNavigated: true};
}
