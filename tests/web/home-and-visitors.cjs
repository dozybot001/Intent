const {assert, context, fs, path, root, vm} = require('./harness.cjs');

async function homeAndVisitorCases() {
  await vm.runInContext(`(async () => {
    const flush = async () => { for (let index = 0; index < 12; index++) await Promise.resolve(); };
    window.IntHubI18n.setLanguage('zh-CN');
    const saved = {fetchJson, loadProject};
    const calls = [];
    let reply = () => ({});
    fetchJson = async (url, options = {}) => {
      calls.push({url, gate: options.gate});
      const answer = reply(url, options);
      if (answer instanceof Error) throw answer;
      return answer;
    };
    const iso = new Date().toISOString();
    const row = (id, extra = {}) => ({id, name: id, full_name: id, created_at: iso, revision: null, last_synced_at: iso, visibility: 'private', permission: 'admin', team: null, ...extra});
    const overviewOf = (id, permission, extra = {}) => ({
      project: {id, name: id, full_name: 'acme/' + id, created_at: iso, repository_url: null, visibility: 'public', permission, owner: {type: 'team', id: 't1', slug: 'acme', name: 'Acme'}, ...extra},
      history: {project_id: id, revision: 'a'.repeat(64), last_synced_at: iso},
      active_intents: [], other_intents: [], active_decisions: [], deprecated_decisions: [], recent_snaps: [],
    });
    const reset = () => {
      Object.assign(state, {projects: [], currentProjectId: null, _loadedProjectId: null, overview: null, handoff: null, page: 'project', visitor: false, account: null, activeTab: 'overview', _home: null, _homeError: ''});
      el.shell.classList.remove('is-site');
      el.detailContent.innerHTML = '';
      el.siteContent.innerHTML = '';
      el.authGate.classList.add('is-hidden');
      el.shell.inert = false;
      window.location.pathname = '/';
      window.location.search = '';
      calls.length = 0;
      routes.length = 0;
    };
    state.config = {authRequired: true, authMode: 'tenon', apiBaseUrl: '', defaultProjectId: null};
    state.account = {id: 'me', display_name: 'Ana'};
    const settingsTab = document.getElementById('settings-tab');
    const tabQuery = el.tabBar.querySelector;
    el.tabBar.querySelector = (selector) => selector.includes('settings') ? settingsTab : null;

    // / with 2 or more projects: the home page, one list in the server's order, no project opened.
    reset();
    state.account = {id: 'me', display_name: 'Ana'};
    const homeRows = [
      row('acme-app', {full_name: 'acme/app', active_intents: 2, blocked_intents: 1, visibility: 'public'}),
      row('notes', {active_intents: 0, blocked_intents: 0, last_synced_at: null}),
    ];
    let opened = [];
    loadProject = async (id, options) => { opened.push(id); state.currentProjectId = id; };
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows} : url === '/api/v1/home' ? {projects: homeRows} : {};
    await loadProjects(readRoute());
    assert.deepEqual(opened, []);
    assert.equal(state.page, 'home');
    assert.equal(el.shell.classList.contains('is-site'), true);
    assert.equal(document.title, '项目列表 · IntHub');
    assert.equal(routeUrl(), '/');
    let page = el.siteContent.innerHTML;
    assert.ok(page.indexOf('acme/app') < page.indexOf('notes'));
    assert.ok(page.includes('href="/?project=acme-app" data-route') && page.includes('class="page-title">项目列表</h1>'));
    assert.ok(page.includes('2 个进行中') && page.includes('status-dot') && page.includes('1 个被阻塞') && page.includes('公开') && page.includes('私有') && page.includes('刚刚同步') && page.includes('未同步'));
    assert.equal((page.match(/个被阻塞/g) || []).length, 1, 'no zero-blocked pill');

    // The picker: All projects first, then the full names.
    assert.equal(el.projectPickerLabel.textContent, '全部项目');
    let picker = el.projectPickerDropdown.innerHTML;
    assert.ok(picker.indexOf('href="/" data-route') < picker.indexOf('acme/app'));
    assert.ok(picker.includes('aria-selected="true"') && picker.includes('全部项目'));
    assert.equal((picker.match(/role="option"/g) || []).length, 3);
    assert.equal(el.projectPickerTrigger.disabled, false);

    // A default project, one project, none: / opens the project, or the setup guide.
    reset();
    state.account = {id: 'me', display_name: 'Ana'};
    state.config.defaultProjectId = 'notes';
    opened = [];
    await loadProjects(readRoute());
    assert.deepEqual(opened, ['notes']);
    assert.equal(state.page, 'project');
    assert.ok(!el.projectPickerDropdown.innerHTML.includes('data-route'), 'with a default project there is no home page to link to');
    state.config.defaultProjectId = null;
    reset();
    opened = [];
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows.slice(0, 1)} : {};
    await loadProjects(readRoute());
    assert.deepEqual(opened, ['acme-app']);
    assert.equal(state.page, 'project');
    reset();
    reply = () => ({projects: []});
    await loadProjects(readRoute());
    assert.equal(state.page, 'project');
    assert.ok(el.detailContent.innerHTML.includes('setup-guide'));

    // /account/tokens shipped for a day: it is just / now, and the address follows.
    reset();
    window.location.pathname = '/account/tokens';
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows} : url === '/api/v1/home' ? {projects: homeRows} : {};
    await loadProjects(readRoute());
    assert.equal(state.page, 'home');
    assert.equal(routes.join(), 'replace');
    assert.equal(routeUrl(), '/');

    // A hidden project is treated as not found, without the gate: / takes over.
    reset();
    window.location.search = '?project=hidden';
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows} : url === '/api/v1/home' ? {projects: homeRows} : new ApiRequestError('gone', 404, 'PROJECT_NOT_FOUND');
    await loadProjects(readRoute());
    assert.equal(state.page, 'home');
    assert.equal(calls.find((call) => call.url.endsWith('/hidden/overview')).gate, false);
    assert.equal(el.statusLine.textContent, '这个项目不存在，或者你无权查看。');

    // A signed-in non-member keeps the public project open, as a passing entry, with no Settings tab.
    reset();
    loadProject = saved.loadProject;
    state.account = {id: 'me', display_name: 'Ana'};
    window.location.search = '?project=pub';
    const publicOverview = overviewOf('pub', 'public');
    const handoff = {intents: []};
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows} : url.endsWith('/overview') ? publicOverview : url.endsWith('/handoff') ? handoff : {};
    state.activeTab = 'settings';
    await loadProjects(readRoute());
    assert.equal(state.currentProjectId, 'pub');
    assert.equal(state.page, 'project');
    assert.equal(state.activeTab, 'overview', 'Settings is not reachable by URL either');
    assert.deepEqual(state.projects.map((project) => [project.id, Boolean(project.transient)].join()), ['acme-app,false', 'notes,false', 'pub,true']);
    assert.equal(el.projectPickerLabel.textContent, 'acme/pub');
    assert.equal(canManageProject(), false);
    assert.equal(settingsTab.classList.contains('is-hidden'), true);
    assert.equal(hasHomePage(), true, 'a passing entry does not count as one of my projects');
    assert.ok(el.detailContent.innerHTML.includes('Acme') && !el.detailContent.innerHTML.includes('href="/teams/acme"'), 'a non-member gets no link to the team');
    assert.ok(el.detailContent.innerHTML.includes('visibility-pill'));
    // Moving on drops it.
    reply = (url) => url.endsWith('/overview') ? overviewOf('acme-app', 'admin', {visibility: 'private'}) : url.endsWith('/handoff') ? handoff : {};
    await loadProject('acme-app');
    assert.deepEqual(state.projects.map((project) => project.id), ['acme-app', 'notes']);
    assert.equal(canManageProject(), true);
    assert.equal(settingsTab.classList.contains('is-hidden'), false);
    assert.ok(el.detailContent.innerHTML.includes('href="/teams/acme" data-route'), 'a member can follow the owner to the team');

    // A visitor: /api/v1/auth/me says 401 quietly, and the overview answers. No project list, no tokens, no gate.
    reset();
    loadProject = saved.loadProject;
    window.location.search = '?project=pub';
    window.history.replaceState = window.history.replaceState;
    globalThis.fetch = async () => ({ok: true, json: async () => ({...state.config})});
    const authRequired = new ApiRequestError('Sign in', 401, 'AUTH_REQUIRED');
    reply = (url) => url === '/api/v1/auth/me' ? authRequired : url.endsWith('/overview') ? publicOverview : url.endsWith('/handoff') ? handoff : new Error('unexpected ' + url);
    await init(false);
    assert.equal(state.visitor, true);
    assert.equal(el.authGate.classList.contains('is-hidden'), true);
    assert.deepEqual(calls.map((call) => call.url), ['/api/v1/auth/me', '/api/v1/projects/pub/overview', '/api/v1/projects/pub/overview', '/api/v1/projects/pub/handoff']);
    assert.equal(calls[0].gate, false);
    assert.equal(calls[1].gate, false);
    assert.equal(el.accountControl.classList.contains('is-hidden'), true);
    assert.equal(el.signInButton.classList.contains('is-hidden'), false);
    assert.equal(el.projectPickerTrigger.disabled, true);
    assert.equal(el.projectPicker.classList.contains('is-static'), true);
    assert.equal(el.projectPickerLabel.textContent, 'acme/pub');
    assert.equal(canManageProject(), false);
    assert.equal(hasHomePage(), false);
    assert.equal(settingsTab.classList.contains('is-hidden'), true);

    // Sign in opens the gate over the project, keeping it; Back returns to it.
    el.signInButton.events.get('click')[0]();
    assert.equal(el.authGate.classList.contains('is-hidden'), false);
    assert.equal(el.authDismiss.classList.contains('is-hidden'), false);
    assert.equal(state.visitor, true);
    assert.notEqual(el.detailContent.innerHTML, '');
    assert.equal(el.shell.inert, true);
    el.authDismiss.events.get('click')[0]();
    assert.equal(el.authGate.classList.contains('is-hidden'), true);
    assert.equal(el.authDismiss.classList.contains('is-hidden'), true);
    assert.equal(el.shell.inert, false);
    assert.equal(document.activeElement, el.signInButton);

    // Refresh reloads the project and leaves the project list alone.
    calls.length = 0;
    await el.refreshBtn.events.get('click')[0]();
    assert.ok(!calls.some((call) => call.url === '/api/v1/projects'));
    assert.ok(calls.some((call) => call.url === '/api/v1/projects/pub/overview'));

    // An empty public project says so; nobody is told to run the CLI.
    const emptyOverview = {...publicOverview, history: {project_id: 'pub', revision: null}};
    reply = (url) => url.endsWith('/overview') ? emptyOverview : url.endsWith('/handoff') ? handoff : {};
    await loadProject('pub');
    assert.ok(el.detailContent.innerHTML.includes('这个项目还没有发布任何内容。'));
    assert.ok(!el.detailContent.innerHTML.includes('setup-guide') && !el.detailContent.innerHTML.includes('itt push'));
    assert.equal(el.shell.classList.contains('is-empty'), true);

    // Whoever manages an empty project still reaches its Settings: the guide links there, and the way back works.
    reset();
    state.currentProjectId = 'pub';
    state.projects = [row('pub'), row('other')];
    const managedEmpty = {...overviewOf('pub', 'admin'), history: {project_id: 'pub', revision: null}};
    reply = (url) => url.endsWith('/overview') ? managedEmpty : url.endsWith('/handoff') ? handoff : {};
    await loadProject('pub');
    assert.ok(el.detailContent.innerHTML.includes('setup-guide'));
    assert.ok(el.detailContent.innerHTML.includes('href="/?project=pub&amp;tab=settings" data-route'));
    switchTab('settings');
    assert.equal(el.shell.classList.contains('is-empty'), false);
    assert.ok(el.detailContent.innerHTML.includes('settings-layout') && el.detailContent.innerHTML.includes('data-rename-form'));
    switchTab('overview');
    assert.equal(el.shell.classList.contains('is-empty'), true);
    assert.ok(el.detailContent.innerHTML.includes('setup-guide'));
    state.activeTab = 'settings';
    await loadProject('pub');
    assert.ok(el.detailContent.innerHTML.includes('settings-layout'), 'the URL can name it too');
    state.activeTab = 'overview';
    reply = (url) => url.endsWith('/overview') ? {...managedEmpty, project: {...managedEmpty.project, permission: 'write'}} : url.endsWith('/handoff') ? handoff : {};
    await loadProject('pub');
    assert.ok(el.detailContent.innerHTML.includes('setup-guide') && !el.detailContent.innerHTML.includes('tab=settings'), 'a member pushes; only an admin manages');

    // Without a public project the gate takes over, as it did.
    reset();
    window.location.search = '?project=secret';
    reply = (url) => authRequired;
    await init(false);
    assert.equal(state.visitor, false);
    assert.equal(el.authGate.classList.contains('is-hidden'), false);
    assert.equal(el.authDismiss.classList.contains('is-hidden'), true);
    const loginLink = document.getElementById('login-link');
    loginLink.dataset.loginMethod = 'github';
    loginLink.querySelector = () => document.getElementById('login-link-part');
    el.tenonLogin.querySelectorAll = () => [loginLink];
    for (const [pathname, search, returnTo] of [['/settings', '', '%2Fsettings'], ['/invite', '?token=abc', '%2Finvite%3Ftoken%3Dabc']]) {
      reset();
      window.location.pathname = pathname;
      window.location.search = search;
      reply = (url) => authRequired;
      await init(false);
      assert.equal(el.authGate.classList.contains('is-hidden'), false);
      assert.deepEqual(calls.map((call) => call.url), ['/api/v1/auth/me']);
      assert.equal(loginLink.href, '/auth/redirect?method=github&return_to=' + returnTo);
    }
    el.tenonLogin.querySelectorAll = () => [];

    // Site pages on a Tenon hub load the list but no project; on a local hub those paths are project routes.
    reset();
    state.account = {id: 'me', display_name: 'Ana'};
    opened = [];
    loadProject = async (id) => { opened.push(id); };
    window.location.pathname = '/account';
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows} : {};
    await loadProjects(readRoute());
    assert.deepEqual(opened, []);
    assert.equal(state.currentProjectId, null);
    assert.equal(el.projectPickerLabel.textContent, '全部项目');
    state.config = {authRequired: false, authMode: 'none', apiBaseUrl: '', defaultProjectId: null};
    reset();
    window.location.pathname = '/account';
    reply = (url) => url === '/api/v1/projects' ? {projects: homeRows.slice(0, 1)} : {};
    await loadProjects(readRoute());
    assert.deepEqual(opened, ['acme-app']);
    assert.equal(state.page, 'project');

    // Back and forward reach the same pages.
    state.config = {authRequired: true, authMode: 'tenon', apiBaseUrl: '', defaultProjectId: null};
    reset();
    state.account = {id: 'me', display_name: 'Ana'};
    state.projects = homeRows;
    reply = (url) => url === '/api/v1/home' ? {projects: homeRows} : url === '/api/v1/teams/acme' ? {team: {id: 't1', slug: 'acme', name: 'Acme'}, role: 'member', members: [], invites: [], projects: []} : {tokens: [], teams: []};
    window.location.pathname = '/settings/teams';
    await applyRoute(readRoute());
    assert.equal(state._dialog, 'settings');
    assert.equal(state._pane, 'teams');
    window.location.pathname = '/teams/acme';
    await applyRoute(readRoute());
    assert.equal(state._dialog, null, 'leaving for a page closes the dialog');
    assert.equal(el.settingsDialog.open, false);
    assert.equal(state.page, 'team');
    window.location.pathname = '/';
    await applyRoute(readRoute());
    assert.equal(state.page, 'home');
    opened = [];
    window.location.search = '?project=notes';
    await applyRoute(readRoute());
    assert.equal(state.page, 'project');
    assert.deepEqual(opened, ['notes']);

    fetchJson = saved.fetchJson;
    loadProject = saved.loadProject;
    el.tabBar.querySelector = tabQuery;
    delete globalThis.fetch;
    reset();
    state.config = {authMode: 'tenon', apiBaseUrl: '', productVersion: '6.0.1'};
  })()`, context);
  console.log('Home page, picker, passing public projects, visitor mode, gate fallbacks and route dispatch tests passed.');
}

module.exports = homeAndVisitorCases;
