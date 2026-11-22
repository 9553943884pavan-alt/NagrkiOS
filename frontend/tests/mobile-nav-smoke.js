// Run against the local Vite server on port 5175 with playwright-cli run-code.
// Uses a synthetic citizen; no backend is contacted.
async page => {
  await page.unrouteAll();
  await page.route('**/api/auth/me', route => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({id: 1, name: 'Test Citizen', email: 'citizen@example.invalid', role: 'citizen', department: null, district: 'Prayagraj'})}));
  await page.route('**/api/auth/config', route => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({demo_enabled: true})}));
  await page.route('**/api/citizen/overview', route => route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({total: 0, active: 0, resolved: 0, recent: []})}));
  await page.setViewportSize({width: 390, height: 844});
  await page.goto('http://127.0.0.1:5175/');
  await page.getByRole('button', {name: 'Open menu'}).waitFor();
  await page.keyboard.press('Tab');
  const first = await page.evaluate(() => document.activeElement.getAttribute('aria-label'));
  if (first !== 'Open menu') throw Error(`Hidden sidebar receives the first Tab: ${first}`);
  await page.keyboard.press('Enter');
  const opened = await page.evaluate(() => document.activeElement.getAttribute('aria-label'));
  if (opened !== 'Close menu') throw Error(`Opening sidebar does not focus Close menu: ${opened}`);
  await page.screenshot({path: 'frontend/qa-artifacts/mobile-nav-390-synthetic.png'});
  if (!await page.evaluate(() => document.querySelector('.main-area').inert)) throw Error('Background remains keyboard-accessible while navigation is open');
  await page.keyboard.press('Shift+Tab');
  if (!await page.evaluate(() => document.activeElement.classList.contains('sidebar-collapse'))) throw Error('Shift+Tab escaped the navigation dialog');
  await page.keyboard.press('Tab');
  if (await page.evaluate(() => document.activeElement.getAttribute('aria-label')) !== 'Close menu') throw Error('Tab did not wrap to the first navigation control');
  await page.keyboard.press('Escape');
  const closed = await page.evaluate(() => document.activeElement.getAttribute('aria-label'));
  if (closed !== 'Open menu') throw Error(`Escape did not restore menu trigger focus: ${closed}`);
  await page.getByRole('button', {name: 'Open menu'}).click();
  await page.setViewportSize({width: 1024, height: 844});
  await page.waitForFunction(() => !document.querySelector('.sidebar')?.classList.contains('mobile-open'));
  await page.setViewportSize({width: 390, height: 844});
  if (await page.evaluate(() => document.querySelector('.sidebar')?.classList.contains('mobile-open'))) throw Error('Menu reopened after desktop resize');
  return {hiddenSidebarSkipped: true, openingFocusesMenu: true, focusTrapped: true, backgroundInert: true, escapeRestoresTrigger: true, desktopResizeClosesMenu: true};
}
