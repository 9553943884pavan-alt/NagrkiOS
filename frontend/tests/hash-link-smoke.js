// Run against local Vite with playwright-cli run-code; every API response is mocked.
async page => {
  await page.unrouteAll();
  const base = 'http://127.0.0.1:5175/';
  const seen = [];
  await page.route('**/api/auth/me', route => route.fulfill({status: 401, contentType: 'application/json', body: '{"detail":"Not signed in"}'}));
  await page.route('**/api/auth/config', route => route.fulfill({status: 200, contentType: 'application/json', body: '{"demo_enabled":false,"registration_available":true}'}));
  for (const path of ['reset-password', 'verify-email', 'accept-invitation']) {
    await page.route(`**/api/auth/${path}`, route => {
      seen.push({path, body: route.request().postDataJSON()});
      return route.fulfill({status: 200, contentType: 'application/json', body: '{"message":"Mock success"}'});
    });
  }
  await page.goto(base);
  await page.getByRole('button', {name: 'Forgot password?'}).click();
  for (const [kind, heading, action, path] of [
    ['reset', 'Choose a new password', 'Change password', 'reset-password'],
    ['verify', 'Verify your email', 'Verify email', 'verify-email'],
    ['invite', 'Accept staff invitation', 'Activate account', 'accept-invitation'],
  ]) {
    const token = `synthetic-${kind}-token-0001`;
    await page.goto(`${base}#${kind}=${token}`);
    await page.getByRole('heading', {name: heading}).waitFor();
    await page.getByLabel('Password', {exact: true}).fill('synthetic passphrase 123');
    if (kind !== 'verify') await page.getByLabel('Confirm password').fill('synthetic passphrase 123');
    await page.getByRole('button', {name: action}).click();
    await page.getByRole('heading', {name: 'Sign in to NagrikOS'}).waitFor();
    const submitted = seen.at(-1);
    if (submitted?.path !== path || submitted.body?.token !== token) throw Error(`Wrong ${kind} token submitted`);
  }
  if (seen.length !== 3) throw Error(`Expected three mocked account actions, got ${seen.length}`);
  await page.goto(`${base}#reset=synthetic-reset-token-removed`);
  await page.getByRole('heading', {name: 'Choose a new password'}).waitFor();
  await page.evaluate(() => {window.location.hash = '';});
  await page.getByRole('heading', {name: 'Sign in to NagrikOS'}).waitFor();

  let release;
  await page.route('**/api/auth/reset-password', async route => {
    await new Promise(resolve => {release = resolve;});
    return route.fulfill({status: 200, contentType: 'application/json', body: '{"message":"Mock late success"}'});
  });
  await page.goto(`${base}#reset=synthetic-old-reset-token`);
  await page.getByRole('heading', {name: 'Choose a new password'}).waitFor();
  await page.getByLabel('Password', {exact: true}).fill('synthetic passphrase 123');
  await page.getByLabel('Confirm password').fill('synthetic passphrase 123');
  await page.getByRole('button', {name: 'Change password'}).click();
  await page.waitForFunction(() => document.querySelector('button[type="submit"]')?.textContent?.includes('Please wait'));
  if (!release) throw Error('Expected mocked reset request');
  await page.goto(`${base}#verify=synthetic-new-verify-token`);
  await page.getByRole('heading', {name: 'Verify your email'}).waitFor();
  release();
  await page.waitForTimeout(100);
  await page.getByRole('heading', {name: 'Verify your email'}).waitFor();
  return {sameTabReset: true, sameTabVerify: true, sameTabInvite: true, freshTokenUsed: true, hashRemovalClosesTokenForm: true, lateResponseKeepsNewLink: true, mockedRequests: seen.length + 1};
}
