// Run against the local Vite server on port 5175 with playwright-cli run-code.
// No authentication or account action is performed; API responses are synthetic.
async page => {
  await page.unrouteAll();
  await page.route('**/api/auth/me', route => route.fulfill({status: 401, contentType: 'application/json', body: '{"detail":"Not signed in"}'}));
  await page.route('**/api/auth/config', route => route.fulfill({status: 200, contentType: 'application/json', body: '{"demo_enabled":false,"registration_available":true}'}));
  const widths = [320, 375, 390, 768, 1024, 1440, 1920];
  const screens = [
    {name: 'login', url: '/', heading: 'Sign in to NagrikOS'},
    {name: 'signup', url: '/', action: 'Create citizen account', heading: 'Create a citizen account'},
    {name: 'forgot', url: '/', action: 'Forgot password?', heading: 'Reset your password'},
    {name: 'reset', url: '/#reset=synthetic-token', heading: 'Choose a new password'},
    {name: 'verify', url: '/#verify=synthetic-token', heading: 'Verify your email'},
    {name: 'invite', url: '/#invite=synthetic-token', heading: 'Accept staff invitation'},
  ];
  const results = [];
  const accessibility = [];
  for (const screen of screens) {
    for (const width of widths) {
      await page.setViewportSize({width, height: 900});
      await page.goto('http://127.0.0.1:5175' + screen.url);
      await page.locator('.login-form-panel h2').waitFor();
      if (screen.action) await page.getByRole('button', {name: screen.action}).click();
      await page.getByRole('heading', {name: screen.heading}).waitFor();
      await page.waitForTimeout(80);
      const sizes = await page.evaluate(() => ({viewport: innerWidth, document: document.documentElement.scrollWidth}));
      results.push({screen: screen.name, width, ...sizes});
      if (width === 390) {
        await page.addScriptTag({path: 'frontend/node_modules/axe-core/axe.min.js'});
        const violations = await page.evaluate(async () => {
          const report = await window.axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}});
          return report.violations.map(item => ({id: item.id, impact: item.impact, count: item.nodes.length, targets: item.nodes.slice(0, 3).map(node => node.target.join(' '))}));
        });
        accessibility.push({screen: screen.name, violations});
      }
    }
  }
  return {checked: results.length, overflow: results.filter(r => r.document > r.viewport), accessibility: accessibility.filter(r => r.violations.length)};
}
