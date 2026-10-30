// Pure copy/render/controller tests. No browser, screenshot or visual validation.
const headerMenuCases = require('./header-menus.cjs');
const viewControllerCases = require('./view-controllers.cjs');
const flowAndPagingCases = require('./flow-and-paging.cjs');
const settingsCases = require('./settings.cjs');
const teamCases = require('./teams.cjs');
const homeAndVisitorCases = require('./home-and-visitors.cjs');
const inviteCases = require('./invites.cjs');
const historyCases = require('./history.cjs');
const redirectCase = require('./redirect.cjs');

(async () => {
  await headerMenuCases();
  await viewControllerCases();
  await flowAndPagingCases();
  await settingsCases();
  await teamCases();
  await homeAndVisitorCases();
  await inviteCases();
  await historyCases();
  await redirectCase('https://account.tenon.asia/api/auth/oauth2/authorize?state=fresh');
  await redirectCase('https://evil.example/authorize');
  await redirectCase('', true);
  console.log('Fixed transition destination, timeout, retry and safe return tests passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
